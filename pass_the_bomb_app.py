import streamlit as st
from datetime import datetime, timedelta, date # Ensure 'date' is imported
import random
import json
import time
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import io

# --- CONFIG ---
st.set_page_config(page_title="Pass the Bomb", layout="centered", initial_sidebar_state="collapsed")
LOGO_PATH = "asmpt_logo.png"
APP_VERSION = "5.7 Selective Save" # Updated version

DEFAULT_GAME_DURATIONS = {
    "☕ Short (15 mins)": timedelta(minutes=15),
    "⚡ Quick Blast (30 mins)": timedelta(minutes=30),
    "🕒 Standard (1 hour)": timedelta(hours=1),
    "☀️ Half Day (4 hours)": timedelta(hours=4),
    "🗓️ Full Day (8 hours)": timedelta(hours=8),
    "💼 Week (Office Hours)": timedelta(days=5),
}

DEFAULT_STATE_KEYS = { # These are the keys defining the core game state to be saved/loaded
    "game_started": False,
    "players": [],
    "pending_players": [], # Note: pending_players will be empty once game starts, but good to define
    "current_holder": None,
    "game_end_time": None,
    "history": [],
    "game_id": None,
}

# --- Google Drive Setup ---
@st.cache_resource
def init_drive_service():
    creds = st.secrets["gcp_service_account"]
    folder_id = st.secrets["google_drive_folder_id"]
    credentials = service_account.Credentials.from_service_account_info(creds, scopes=["https://www.googleapis.com/auth/drive"])
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    return service, folder_id

drive_service, DRIVE_FOLDER_ID = init_drive_service()

# --- Drive Helpers ---
def find_file(service, name, folder_id):
    q = f"name='{name}' and '{folder_id}' in parents and trashed=false"
    r = service.files().list(q=q, fields="files(id)").execute()
    files = r.get("files", [])
    return files[0]["id"] if files else None

def _serialize(session_data): # session_data is st.session_state
    data_to_save = {}
    for key_to_save in DEFAULT_STATE_KEYS: # Iterate only over defined game state keys
        if key_to_save in session_data:
            value = session_data[key_to_save]
            
            if isinstance(value, datetime): # Handles datetime.datetime
                data_to_save[key_to_save] = value.isoformat()
            elif isinstance(value, date):   # Handles datetime.date
                data_to_save[key_to_save] = value.isoformat()
            elif key_to_save == "history":
                serialized_history = []
                if isinstance(value, list):
                    for entry in value:
                        if isinstance(entry, dict):
                            e = entry.copy()
                            time_val = e.get("time")
                            if isinstance(time_val, datetime):
                                e["time"] = time_val.isoformat()
                            elif isinstance(time_val, date): # Just in case
                                e["time"] = time_val.isoformat()
                            serialized_history.append(e)
                        # else: could append raw entry if history items aren't always dicts
                data_to_save[key_to_save] = serialized_history
            else: # For other types like bool, string, list of strings, int
                data_to_save[key_to_save] = value
    return data_to_save

def _deserialize(data_from_file):
    deserialized_state = {}
    for k, v_loaded in data_from_file.items():
        # Ensure we only process keys that are expected (part of DEFAULT_STATE_KEYS)
        # or handle them generally if the file might contain more.
        # For now, assuming data_from_file only contains what _serialize saved.
        
        if k == "history":
            deserialized_history = []
            if isinstance(v_loaded, list):
                for entry in v_loaded:
                    new_entry = {}
                    if isinstance(entry, dict): # Ensure entry is a dict
                        new_entry = entry.copy()
                        time_str = new_entry.get("time")
                        if isinstance(time_str, str):
                            try:
                                new_entry["time"] = datetime.fromisoformat(time_str)
                            except ValueError:
                                pass # Keep as string if not valid isoformat
                    deserialized_history.append(new_entry)
            deserialized_state[k] = deserialized_history
        elif isinstance(v_loaded, str):
            try:
                # Attempt to convert strings back to datetime if they are ISO format
                # This will handle both datetime and date strings from isoformat()
                deserialized_state[k] = datetime.fromisoformat(v_loaded)
            except ValueError:
                deserialized_state[k] = v_loaded # Keep as string if not ISO datetime
        else:
            deserialized_state[k] = v_loaded

    # Ensure all default keys are present in the final state, even if not in file
    for default_k, default_v in DEFAULT_STATE_KEYS.items():
        if default_k not in deserialized_state:
            deserialized_state[default_k] = default_v
        # Specific type checks for critical fields after loading
        if default_k == "players" and not isinstance(deserialized_state.get("players"), list):
            deserialized_state["players"] = []
        if default_k == "history" and not isinstance(deserialized_state.get("history"), list):
            deserialized_state["history"] = []

    return deserialized_state


def save_to_drive(game_id, current_session_state):
    if not game_id:
        st.error("Attempted to save game with no ID!")
        return
    try:
        # Pass current_session_state to _serialize
        data_to_save = _serialize(current_session_state) 
        json_data = json.dumps(data_to_save, indent=2)
    except TypeError as e:
        st.error(f"Failed to serialize game state to JSON: {e}")
        # For debugging, print the structure that _serialize produced:
        # st.error(f"Problematic structure from _serialize: {data_to_save}") 
        raise 
    
    media = MediaIoBaseUpload(io.BytesIO(json_data.encode()), mimetype="application/json")
    file_meta = {"name": f"{game_id}.json", "parents": [DRIVE_FOLDER_ID]}
    existing_id = find_file(drive_service, f"{game_id}.json", DRIVE_FOLDER_ID)
    if existing_id:
        drive_service.files().update(fileId=existing_id, media_body=media).execute()
    else:
        drive_service.files().create(body=file_meta, media_body=media).execute()

def load_from_drive(game_id):
    if not game_id: return None
    file_id = find_file(drive_service, f"{game_id}.json", DRIVE_FOLDER_ID)
    if not file_id: return None
    req = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, req)
    done = False
    try:
        while not done:
            status, done = downloader.next_chunk()
    except Exception as e:
        st.error(f"Error downloading game file: {e}")
        return None
    fh.seek(0)
    try:
        loaded_data = json.loads(fh.getvalue().decode())
        return _deserialize(loaded_data)
    except json.JSONDecodeError:
        st.error(f"Error decoding game data for game ID: {game_id}. The file might be corrupted.")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred while loading game data: {e}")
        return None

# --- UI Layout ---
try: st.image(LOGO_PATH, width=180)
except: st.warning("Logo file 'asmpt_logo.png' not found. Please ensure it's in the same directory.")
st.title("💣 Pass the Bomb – ASMPT Edition")
st.caption(f"Version {APP_VERSION}")
st.markdown("### _Don't get caught holding the bomb when time runs out!_")
st.markdown("#### _The ultimate loser buys the Matcha Lattes! 🍵_")

# --- Session Init ---
current_query_params = st.query_params
for k, v_default in DEFAULT_STATE_KEYS.items():
    if k not in st.session_state:
        st.session_state[k] = v_default

# --- Load Existing Game if game_id in URL ---
if not st.session_state.get("game_started"):
    gid_from_url = current_query_params.get("game_id")
    if gid_from_url:
        # Load if game_id in session doesn't match URL, or if game isn't marked as started
        if st.session_state.get("game_id") != gid_from_url or not st.session_state.get("game_started"):
            # st.session_state["game_id"] = gid_from_url # Set game_id before loading
            loaded_state_from_drive = load_from_drive(gid_from_url)
            if loaded_state_from_drive:
                # Populate session_state with only the keys from loaded_state_from_drive
                # which should correspond to DEFAULT_STATE_KEYS due to _serialize and _deserialize logic
                for key_from_file, value_from_file in loaded_state_from_drive.items():
                    st.session_state[key_from_file] = value_from_file
                
                st.session_state["game_id"] = gid_from_url # Crucial: confirm game_id from URL
                st.session_state["game_started"] = True
            else:
                st.warning(f"Could not find or load game: {gid_from_url}. It may no longer exist or there was an error loading.")
                if st.session_state.get("game_id") == gid_from_url: # If attempted load failed for this id
                    st.session_state["game_id"] = None
                    st.session_state["game_started"] = False

# --- New Game UI ---
if not st.session_state.get("game_started"):
    st.subheader("🎮 Setup New Game")
    with st.form("add_players_form", clear_on_submit=True):
        new_player_name = st.text_input("Enter player name", key="new_player_name_input")
        add_player_submitted = st.form_submit_button("➕ Add Player")
        if add_player_submitted and new_player_name.strip():
            if new_player_name.strip() not in st.session_state["pending_players"]:
                st.session_state["pending_players"].append(new_player_name.strip())
                st.rerun()

    if st.session_state["pending_players"]:
        st.markdown("**Players to join:**")
        for p_name in st.session_state["pending_players"]:
            st.markdown(f"- {p_name}")

    selected_duration_label = st.selectbox("Game Duration", list(DEFAULT_GAME_DURATIONS.keys()), index=1, key="game_duration_select")

    if len(st.session_state["pending_players"]) < 2:
        st.info("Add at least 2 players to begin the game.")
    else:
        if st.button("✅ Start Game", key="start_game_button"):
            new_game_id = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=8))
            st.session_state["game_id"] = new_game_id
            st.query_params["game_id"] = new_game_id
            
            st.session_state["players"] = list(st.session_state["pending_players"])
            st.session_state["pending_players"] = [] # Clear pending players list
            st.session_state["current_holder"] = random.choice(st.session_state["players"])
            st.session_state["game_end_time"] = datetime.now() + DEFAULT_GAME_DURATIONS[selected_duration_label]
            st.session_state["history"] = [{"event": "Game Started", "player": st.session_state["current_holder"], "time": datetime.now()}]
            st.session_state["game_started"] = True
            
            save_to_drive(st.session_state["game_id"], st.session_state) # Pass full session_state
            st.rerun()

# --- Game Play ---
if st.session_state.get("game_started") and st.session_state.get("game_id"):
    players_list_valid = isinstance(st.session_state.get("players"), list) and st.session_state.get("players")
    game_end_time_valid = isinstance(st.session_state.get("game_end_time"), datetime)

    if not players_list_valid:
        st.error("Player list is invalid or empty. Please restart the game.")
        st.session_state["game_started"] = False
    elif not game_end_time_valid:
        st.error("Game end time is not set correctly. Please restart the game.")
        st.session_state["game_started"] = False
    else:
        time_now = datetime.now()
        game_time_left = st.session_state["game_end_time"] - time_now

        if game_time_left.total_seconds() <= 0:
            st.error("🏁 Game Over!")
            st.subheader(f"Final bomb holder: {st.session_state.get('current_holder', 'N/A')}")
            st.warning(f"**{st.session_state.get('current_holder', 'N/A')}** buys the Matcha Lattes! 🍵")
        else:
            st.subheader(f"💣 Bomb held by: {st.session_state.get('current_holder', 'N/A')}")
            st.metric("Time remaining:", str(game_time_left).split(".")[0])
            st.markdown("---")
            st.subheader("Pass the Bomb")
            
            current_players_list_for_form = st.session_state.get("players", [])
            
            if st.session_state.get("current_holder") not in current_players_list_for_form:
                st.error("Error: Current bomb holder is not a valid player. Game state might be corrupted. Please restart.")
            else:
                with st.form("pass_form"): # Explicit key for the form
                    current_bomb_holder = st.session_state["current_holder"]
                    available_players_to_pass = [p for p in current_players_list_for_form if p != current_bomb_holder]
                    
                    next_player_selected = None # Initialize
                    pass_button_disabled = True # Initialize as disabled

                    if not available_players_to_pass:
                        st.warning("No other players to pass the bomb to!")
                    else:
                        next_player_selected = st.selectbox("Pass to:", available_players_to_pass, key="pass_to_select")
                        pass_button_disabled = False

                    ticket_number = st.text_input("Ticket number", key="ticket_input")
                    ticket_date_val = st.date_input("Ticket creation date", value="today", max_value=datetime.now().date(), key="ticket_date_input")
                    
                    # Give the submit button a unique key to see if it helps with state issues
                    submitted_pass_bomb = st.form_submit_button("Pass This Bomb!", disabled=pass_button_disabled, key="pass_bomb_submit_button")

                    if submitted_pass_bomb:
                        if next_player_selected and ticket_date_val: # Ensure values are not None
                            days_ticket_age = (datetime.now().date() - ticket_date_val).days
                            st.session_state["history"].append({
                                "from": current_bomb_holder,
                                "to": next_player_selected,
                                "ticket": ticket_number,
                                "days_old": days_ticket_age,
                                "time": datetime.now()
                            })
                            st.session_state["current_holder"] = next_player_selected
                            save_to_drive(st.session_state["game_id"], st.session_state) # Pass full session_state
                            st.success(f"Ticket was {days_ticket_age} days old. Bomb passed to {next_player_selected}!")
                            st.rerun()
                        else:
                            st.warning("Please ensure a player is selected and the date is set.")


        st.markdown("---")
        st.subheader("📜 Bomb Pass History")
        current_history = st.session_state.get("history", [])
        if not isinstance(current_history, list): current_history = []

        if current_history:
            for record in reversed(current_history):
                if isinstance(record, dict) and record.get("time") and isinstance(record.get("time"), datetime):
                    time_str = record["time"].strftime("%Y-%m-%d %H:%M:%S")
                    if record.get("event") == "Game Started":
                         st.markdown(f"- Game started, bomb initially with `{record.get('player', 'N/A')}` at {time_str}")
                    else:
                        st.markdown(f"- `{record.get('from', 'N/A')}` ➡️ `{record.get('to', 'N/A')}` – Ticket: `{record.get('ticket', 'N/A')}`, **{record.get('days_old', 'N/A')}d**, at {time_str}")
                else:
                    st.markdown(f"- Invalid history record format: {record}")
        else:
            st.caption("No passes yet.")

# --- Sidebar ---
with st.sidebar:
    st.header("Game Controls")
    if st.session_state.get("game_id"):
        st.markdown(f"Game ID: `{st.session_state['game_id']}`")
        st.caption("To share, copy the current browser URL.")

    if st.button("🔁 Restart Game / New Game", key="restart_game_button_sidebar"):
        for key, default_value in DEFAULT_STATE_KEYS.items():
            st.session_state[key] = default_value
        st.query_params.clear() # Clear the game_id from URL
        st.rerun()

# --- Footer ---
st.markdown("<br><hr><center><sub>Made for ASMPT · Powered by Streamlit & Matcha</sub></center>", unsafe_allow_html=True)

# --- Live Refresh (if game is active) ---
if st.session_state.get("game_started") and st.session_state.get("game_id") and isinstance(st.session_state.get("game_end_time"), datetime):
    if st.session_state["game_end_time"] > datetime.now():
        # Only sleep and rerun if no interaction is being processed (avoid interrupting forms)
        # This is a bit tricky to get right; a simpler periodic rerun is often used.
        # For now, the 1-second refresh is standard.
        time.sleep(1) 
        st.rerun()
