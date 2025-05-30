import streamlit as st
from datetime import datetime, timedelta, date # MODIFIED: Added 'date'
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
APP_VERSION = "5.6 JSON Date Fix" # Updated version

DEFAULT_GAME_DURATIONS = {
    "☕ Short (15 mins)": timedelta(minutes=15),
    "⚡ Quick Blast (30 mins)": timedelta(minutes=30),
    "🕒 Standard (1 hour)": timedelta(hours=1),
    "☀️ Half Day (4 hours)": timedelta(hours=4),
    "🗓️ Full Day (8 hours)": timedelta(hours=8),
    "💼 Week (Office Hours)": timedelta(days=5),
}

DEFAULT_STATE_KEYS = {
    "game_started": False,
    "players": [],
    "pending_players": [],
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

def _serialize(state):
    result = {}
    for k, v in state.items():
        if isinstance(v, datetime):  # Handles datetime.datetime objects
            result[k] = v.isoformat()
        elif isinstance(v, date):    # HANDLES datetime.date objects
            result[k] = v.isoformat()
        elif k == "history":
            result[k] = []
            for entry in v:
                if isinstance(entry, dict):
                    e = entry.copy()
                    time_val = e.get("time")
                    if isinstance(time_val, datetime): 
                        e["time"] = time_val.isoformat()
                    elif isinstance(time_val, date):   
                        e["time"] = time_val.isoformat()
                    result[k].append(e)
        else:
            result[k] = v
    return result

def _deserialize(data):
    result = data.copy()
    for k, v_loaded_str in data.items(): # Renamed v to v_loaded_str for clarity in this loop
        if k == "history":
            result[k] = []
            if isinstance(v_loaded_str, list): # Ensure history from file is a list
                for entry in v_loaded_str:
                    new_entry = entry.copy() # Work on a copy
                    if isinstance(new_entry, dict) and isinstance(new_entry.get("time"), str):
                        try: 
                            new_entry["time"] = datetime.fromisoformat(new_entry["time"])
                        except ValueError: 
                            pass # Keep as string if not valid isoformat
                    result[k].append(new_entry)
            # else: history is not a list, result[k] remains []
        elif isinstance(v_loaded_str, str):
            try: 
                result[k] = datetime.fromisoformat(v_loaded_str)
            except ValueError: 
                # Not an isoformat string, keep original string (already in result[k] via data.copy())
                pass 
        # else: value is not a string, keep original (e.g. number, bool, list, dict not handled as history)
    
    # Ensure specific structural integrity after general deserialization
    if not isinstance(result.get("players"), list):
        result["players"] = [] 
    if not isinstance(result.get("history"), list): # Double check history, though loop above tries
        result["history"] = []
    # game_end_time should be datetime or None after the loop
    # current_holder should be string or None

    return result


def save_to_drive(game_id, state):
    if not game_id:
        st.error("Attempted to save game with no ID!")
        return
    try:
        json_data = json.dumps(_serialize(dict(state)), indent=2) # Ensure state is a dict copy
    except TypeError as e:
        st.error(f"Failed to serialize game state to JSON: {e}")
        # Optionally, log the problematic state for debugging, careful with sensitive data
        # print(f"Problematic state: {_serialize(dict(state))}")
        raise # Re-raise the error to see it in Streamlit logs
    
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
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    try:
        loaded_data = json.loads(fh.getvalue().decode())
        return _deserialize(loaded_data)
    except json.JSONDecodeError:
        st.error(f"Error decoding game data for game ID: {game_id}. The file might be corrupted.")
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
        if st.session_state.get("game_id") != gid_from_url or not st.session_state.get("game_started"):
            st.session_state["game_id"] = gid_from_url
            state = load_from_drive(gid_from_url)
            if state:
                for k_loaded, v_loaded in state.items():
                    st.session_state[k_loaded] = v_loaded
                st.session_state["game_id"] = gid_from_url # Ensure this is set from URL
                st.session_state["game_started"] = True # Mark as started
            else:
                st.warning(f"Could not find or load game: {gid_from_url}. It may no longer exist or there was an error loading.")
                st.session_state["game_id"] = None # Clear bad game_id
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
            st.session_state["pending_players"] = []
            st.session_state["current_holder"] = random.choice(st.session_state["players"])
            st.session_state["game_end_time"] = datetime.now() + DEFAULT_GAME_DURATIONS[selected_duration_label]
            st.session_state["history"] = [{"event": "Game Started", "player": st.session_state["current_holder"], "time": datetime.now()}]
            st.session_state["game_started"] = True
            
            save_to_drive(st.session_state["game_id"], st.session_state)
            st.rerun()

# --- Game Play ---
if st.session_state.get("game_started") and st.session_state.get("game_id"):
    # Ensure players list is valid
    if not isinstance(st.session_state.get("players"), list) or not st.session_state.get("players"):
        st.error("Player list is invalid or empty. Please restart the game.")
        st.session_state["game_started"] = False # Stop game if players list is bad
        # Optionally st.rerun() here if you want the error to be the only thing on screen.
    
    # Ensure game_end_time is a datetime object
    elif not isinstance(st.session_state.get("game_end_time"), datetime):
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
            
            current_players_list = st.session_state.get("players", []) # Default to []
            if not isinstance(current_players_list, list): # Defensive check
                current_players_list = []

            if st.session_state.get("current_holder") not in current_players_list:
                st.error("Error: Current bomb holder is not a valid player or player list is corrupted. Please restart.")
            else:
                with st.form("pass_form"):
                    current_bomb_holder = st.session_state["current_holder"]
                    available_players_to_pass = [p for p in current_players_list if p != current_bomb_holder]
                    
                    if not available_players_to_pass:
                        st.warning("No other players to pass the bomb to!")
                        pass_button_disabled = True
                        next_player_selected = None
                    else:
                        next_player_selected = st.selectbox("Pass to:", available_players_to_pass, key="pass_to_select")
                        pass_button_disabled = False

                    ticket_number = st.text_input("Ticket number", key="ticket_input")
                    # Ensure ticket_date uses datetime.date which is fine for the widget
                    ticket_date_val = st.date_input("Ticket creation date", value="today", max_value=datetime.now().date(), key="ticket_date_input")
                    
                    submitted_pass_bomb = st.form_submit_button("Pass This Bomb!", disabled=pass_button_disabled)

                    if submitted_pass_bomb and next_player_selected and ticket_date_val:
                        days_ticket_age = (datetime.now().date() - ticket_date_val).days
                        st.session_state["history"].append({
                            "from": current_bomb_holder,
                            "to": next_player_selected,
                            "ticket": ticket_number,
                            "days_old": days_ticket_age,
                            "time": datetime.now()
                        })
                        st.session_state["current_holder"] = next_player_selected
                        save_to_drive(st.session_state["game_id"], st.session_state)
                        st.success(f"Ticket was {days_ticket_age} days old. Bomb passed to {next_player_selected}!")
                        st.rerun()

        st.markdown("---")
        st.subheader("📜 Bomb Pass History")
        current_history = st.session_state.get("history", [])
        if not isinstance(current_history, list): current_history = [] # Defensive

        if current_history:
            for record in reversed(current_history):
                if isinstance(record, dict) and isinstance(record.get("time"), datetime):
                    time_str = record["time"].strftime("%Y-%m-%d %H:%M:%S")
                    if record.get("event") == "Game Started":
                         st.markdown(f"- Game started, bomb initially with `{record.get('player', 'N/A')}` at {time_str}")
                    else:
                        st.markdown(f"- `{record.get('from', 'N/A')}` ➡️ `{record.get('to', 'N/A')}` – Ticket: `{record.get('ticket', 'N/A')}`, **{record.get('days_old', 'N/A')}d**, at {time_str}")
                else:
                    st.markdown(f"- Invalid history record: {record}")
        else:
            st.caption("No passes yet.")

# --- Sidebar ---
with st.sidebar:
    st.header("Game Controls")
    if st.session_state.get("game_id"):
        st.markdown(f"Game ID: `{st.session_state['game_id']}`")
        # Simple copy-to-clipboard for game ID - needs a proper base URL
        # This part is tricky and depends on your deployment environment.
        # st.experimental_get_query_params() might be useful for parts of the URL.
        # For now, just displaying the ID is safest.
        # You can construct the full URL manually: e.g., https://your-app-url.streamlit.app/?game_id={st.session_state['game_id']}
        st.caption("To share, copy the current browser URL or construct it with the Game ID.")


    if st.button("🔁 Restart Game / New Game", key="restart_game_button_sidebar"):
        for key, default_value in DEFAULT_STATE_KEYS.items():
            st.session_state[key] = default_value
        st.query_params.clear()
        st.rerun()

# --- Footer ---
st.markdown("<br><hr><center><sub>Made for ASMPT · Powered by Streamlit & Matcha</sub></center>", unsafe_allow_html=True)

# --- Live Refresh (if game is active) ---
if st.session_state.get("game_started") and st.session_state.get("game_id") and isinstance(st.session_state.get("game_end_time"), datetime):
    if st.session_state["game_end_time"] > datetime.now():
        time.sleep(1)
        st.rerun()
