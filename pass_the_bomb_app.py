import streamlit as st
from datetime import datetime, timedelta
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
APP_VERSION = "5.4 Smoother Join" # Updated version

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
    "defer_load_after_create": False
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
        if isinstance(v, datetime): result[k] = v.isoformat()
        elif k == "history":
            result[k] = []
            for entry in v:
                if isinstance(entry, dict):
                    e = entry.copy()
                    if isinstance(e.get("time"), datetime):
                        e["time"] = e["time"].isoformat()
                    result[k].append(e)
        elif k != "defer_load_after_create": # Don't save this transient flag
            result[k] = v
    return result

def _deserialize(data):
    result = data.copy()
    for k, v in data.items():
        if k == "history":
            result[k] = []
            for entry in v: # Ensure entry is a dict before accessing "time"
                if isinstance(entry, dict) and isinstance(entry.get("time"), str):
                    try: entry["time"] = datetime.fromisoformat(entry["time"])
                    except: pass # Keep as string if not valid isoformat
                result[k].append(entry)
        elif isinstance(v, str):
            try: result[k] = datetime.fromisoformat(v)
            except: pass # Keep as string if not valid isoformat
    return result

def save_to_drive(game_id, state):
    if not game_id:
        st.error("Attempted to save game with no ID!")
        return
    json_data = json.dumps(_serialize(state), indent=2)
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
        return _deserialize(json.loads(fh.getvalue().decode()))
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
# Get query_params at the beginning of the script run
current_query_params = st.query_params 

for k, v_default in DEFAULT_STATE_KEYS.items():
    if k not in st.session_state:
        st.session_state[k] = v_default

if st.session_state.get("defer_load_after_create"): # Use .get for safety
    st.session_state["defer_load_after_create"] = False
    st.stop()

# --- Load Existing Game if game_id in URL ---
# This block runs only if a game is not already started in the current session.
if not st.session_state.get("game_started"): # Use .get for safety
    gid_from_url = current_query_params.get("game_id")
    if gid_from_url:
        # Attempt to load only if not already loaded to prevent loops on error
        if st.session_state.get("game_id") != gid_from_url:
            st.session_state["game_id"] = gid_from_url # Tentatively set game_id
            state = load_from_drive(gid_from_url)
            if state:
                # Successfully loaded state, now update session_state fully
                for k_loaded, v_loaded in state.items():
                    st.session_state[k_loaded] = v_loaded
                # Crucially, ensure game_id from URL is the one used and mark game as started
                st.session_state["game_id"] = gid_from_url
                st.session_state["game_started"] = True
                # NO st.rerun() HERE. Allow script to continue to "Game Play" section.
            else:
                st.warning(f"Could not find or load game: {gid_from_url}. It may no longer exist or there was an error loading.")
                # Clear game_id if loading failed to allow starting a new game or trying another ID
                st.session_state["game_id"] = None
                st.session_state["game_started"] = False
                # Optionally, clear the game_id from st.query_params if it's invalid
                # st.query_params.clear() # Or st.query_params.pop("game_id", None) if you want to keep others
                # For now, just warn and let user decide next steps (e.g. refresh, new game)

# --- New Game UI ---
if not st.session_state.get("game_started"):
    st.subheader("🎮 Setup New Game")
    with st.form("add_players_form", clear_on_submit=True):
        new_player_name = st.text_input("Enter player name", key="new_player_name_input")
        add_player_submitted = st.form_submit_button("➕ Add Player")
        if add_player_submitted and new_player_name.strip():
            if new_player_name.strip() not in st.session_state["pending_players"]:
                st.session_state["pending_players"].append(new_player_name.strip())
                st.rerun() # Rerun to update display of pending players immediately

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
            
            # Update query params to reflect the new game ID in the URL
            st.query_params["game_id"] = new_game_id
            
            st.session_state["players"] = list(st.session_state["pending_players"]) # Finalize players
            st.session_state["pending_players"] = [] # Clear pending list
            st.session_state["current_holder"] = random.choice(st.session_state["players"])
            st.session_state["game_end_time"] = datetime.now() + DEFAULT_GAME_DURATIONS[selected_duration_label]
            st.session_state["history"] = [{"event": "Game Started", "player": st.session_state["current_holder"], "time": datetime.now()}]
            st.session_state["game_started"] = True
            
            save_to_drive(st.session_state["game_id"], st.session_state)
            st.session_state["defer_load_after_create"] = True # Flag to stop and allow URL to update
            st.rerun()

# --- Game Play ---
if st.session_state.get("game_started") and st.session_state.get("game_id"):
    # Ensure game_end_time is a datetime object
    if not isinstance(st.session_state.get("game_end_time"), datetime):
        st.error("Game end time is not set correctly. Please restart the game.")
        st.session_state["game_started"] = False # Stop game play
    else:
        time_now = datetime.now()
        game_time_left = st.session_state["game_end_time"] - time_now

        if game_time_left.total_seconds() <= 0:
            st.error("🏁 Game Over!")
            st.subheader(f"Final bomb holder: {st.session_state['current_holder']}")
            st.warning(f"**{st.session_state['current_holder']}** buys the Matcha Lattes! 🍵")
            # Consider saving one last time or marking as complete on Drive
            # save_to_drive(st.session_state["game_id"], st.session_state) # Already saved on pass
        else:
            st.subheader(f"💣 Bomb held by: {st.session_state['current_holder']}")
            st.metric("Time remaining:", str(game_time_left).split(".")[0])

            st.markdown("---")
            st.subheader("Pass the Bomb")
            
            # Ensure current_holder is valid before rendering form
            if st.session_state["current_holder"] not in st.session_state["players"]:
                st.error("Error: Current bomb holder is not a valid player. Game state might be corrupted. Please restart.")
            else:
                with st.form("pass_form"):
                    current_bomb_holder = st.session_state["current_holder"]
                    available_players_to_pass = [p for p in st.session_state["players"] if p != current_bomb_holder]
                    
                    if not available_players_to_pass:
                        st.warning("No other players to pass the bomb to!")
                        # This state should ideally not be reached if game started with >1 player
                        # and players aren't removed.
                        pass_button_disabled = True
                        next_player_selected = None
                    else:
                        next_player_selected = st.selectbox("Pass to:", available_players_to_pass, key="pass_to_select")
                        pass_button_disabled = False

                    ticket_number = st.text_input("Ticket number", key="ticket_input")
                    ticket_date = st.date_input("Ticket creation date", max_value=datetime.now().date(), key="ticket_date_input")

                    submitted_pass_bomb = st.form_submit_button("Pass This Bomb!", disabled=pass_button_disabled)

                    if submitted_pass_bomb and next_player_selected:
                        days_ticket_age = (datetime.now().date() - ticket_date).days
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
                        # time.sleep(0.5) # Brief pause for user to see success message
                        st.rerun() # Rerun to update display (bomb holder, history)

        st.markdown("---")
        st.subheader("📜 Bomb Pass History")
        if st.session_state.get("history"):
            for record in reversed(st.session_state["history"]):
                if isinstance(record.get("time"), datetime): # Check if time is datetime
                    time_str = record["time"].strftime("%Y-%m-%d %H:%M:%S")
                    if record.get("event") == "Game Started":
                         st.markdown(f"- Game started, bomb initially with `{record.get('player', 'N/A')}` at {time_str}")
                    else:
                        st.markdown(f"- `{record.get('from', 'N/A')}` ➡️ `{record.get('to', 'N/A')}` – Ticket: `{record.get('ticket', 'N/A')}`, **{record.get('days_old', 'N/A')}d**, at {time_str}")
                else: # Fallback for records without proper time
                    st.markdown(f"- {record}")
        else:
            st.caption("No passes yet.")

# --- Sidebar ---
with st.sidebar:
    st.header("Game Controls")
    if st.session_state.get("game_id"):
        st.markdown(f"Game ID: `{st.session_state['game_id']}`")
        # Simple copy-to-clipboard for game ID
        game_url = f"{st.get_option('server.baseUrlPath')}?game_id={st.session_state['game_id']}"
        st.markdown(f"Share link: `{game_url}` (You might need to manually construct the full URL if not deployed on Streamlit Cloud/Community)")


    if st.button("🔁 Restart Game / New Game", key="restart_game_button_sidebar"):
        # Preserve query_params if needed, or clear them
        # current_gid = st.session_state.get("game_id") # get current game_id before clearing
        
        # Clear all session state keys to default
        for key_to_clear in list(st.session_state.keys()):
            # Be careful not to delete keys Streamlit might use internally if not prefixed
            if key_to_clear in DEFAULT_STATE_KEYS or key_to_clear not in ('query_params'): # Example, adjust as needed
                 del st.session_state[key_to_clear]
        
        # Reset query params to remove game_id from URL if user wants a truly new game setup screen
        st.query_params.clear()
        st.rerun()

# --- Footer ---
st.markdown("<br><hr><center><sub>Made for ASMPT · Powered by Streamlit & Matcha</sub></center>", unsafe_allow_html=True)

# --- Live Refresh (if game is active) ---
if st.session_state.get("game_started") and st.session_state.get("game_id") and isinstance(st.session_state.get("game_end_time"), datetime):
    if st.session_state["game_end_time"] > datetime.now():
        time.sleep(1) # Refresh interval
        st.rerun()
