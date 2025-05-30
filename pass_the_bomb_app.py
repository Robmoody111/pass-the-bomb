import streamlit as st
from datetime import datetime, timedelta
import random
import json
import time 

# Google Drive API imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
import io

st.set_page_config(page_title="Pass the Bomb", layout="centered", initial_sidebar_state="collapsed")

APP_VERSION = "4.6 Advanced Debug"
LOGO_PATH = "asmpt_logo.png"

# ... (DEFAULT_GAME_DURATIONS and format_timedelta remain the same) ...
DEFAULT_GAME_DURATIONS = {
    "☕ Short (15 mins)": timedelta(minutes=15),
    "⚡ Quick Blast (30 mins)": timedelta(minutes=30),
    "🕒 Standard (1 hour)": timedelta(hours=1)
}
def format_timedelta(td):
    if td is None or td.total_seconds() < 0: return "0 seconds"
    total_seconds = int(td.total_seconds())
    days, rem = divmod(total_seconds, 86400); hours, rem = divmod(rem, 3600); minutes, seconds = divmod(rem, 60)
    parts = []
    if days: parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours: parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes: parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if total_seconds < 60 or not parts: parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    return ", ".join(parts) if parts else "0 seconds"


drive_service = None
DRIVE_FOLDER_ID = None

@st.cache_resource
def init_drive_service():
    st.write("--- Debug: Attempting init_drive_service() ---")
    gcp_creds_secret = st.secrets.get("gcp_service_account")
    folder_id_secret = st.secrets.get("google_drive_folder_id")

    temp_service = None
    temp_folder_id = None

    if not gcp_creds_secret:
        st.error("Debug: GCP service account secret NOT FOUND.")
    else:
        st.success("Debug: GCP service account secret FOUND.")
        if not isinstance(gcp_creds_secret, dict) and not hasattr(gcp_creds_secret, 'items'):
             st.error(f"Debug: gcp_service_account secret is not a dictionary. Type: {type(gcp_creds_secret)}")


    if not folder_id_secret:
        st.warning("Debug: Google Drive Folder ID secret NOT FOUND.")
    else:
        st.success(f"Debug: Google Drive Folder ID secret FOUND. Value: '{folder_id_secret}', Type: {type(folder_id_secret)}")
        temp_folder_id = str(folder_id_secret)

    if gcp_creds_secret and folder_id_secret:
        try:
            # Ensure gcp_creds_secret is a dict if it's a SecretsProxy object
            creds_json_dict = dict(gcp_creds_secret) if hasattr(gcp_creds_secret, 'items') else gcp_creds_secret
            
            creds = service_account.Credentials.from_service_account_info(
                creds_json_dict,
                scopes=['https://www.googleapis.com/auth/drive']
            )
            temp_service = build('drive', 'v3', credentials=creds, cache_discovery=False)
            st.success("Debug: Google Drive service built successfully!")
            # Test with a simple API call
            # about_info = temp_service.about().get(fields="user").execute()
            # st.info(f"Debug: Connected to Drive as: {about_info['user']['emailAddress']}")

        except Exception as e:
            st.error(f"Debug: Failed to initialize Google Drive service credentials or build: {e}")
            temp_service = None
            temp_folder_id = None # Ensure folder_id is also None if service fails
    
    st.write(f"--- Debug: init_drive_service() returning: service is {'SET' if temp_service else 'None'}, folder_id is {'SET' if temp_folder_id else 'None'} ---")
    return temp_service, temp_folder_id

drive_service, DRIVE_FOLDER_ID = init_drive_service()

# ... (generate_game_id, _serialize_state, _deserialize_state remain the same) ...
def generate_game_id(): return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=8))
def _serialize_state(state_dict):
    s_state = {}
    for k, v in state_dict.items():
        if isinstance(v, datetime): s_state[k] = v.isoformat()
        elif k == "history" and isinstance(v, list):
            s_state[k] = []
            for r in v:
                nr = r.copy();
                if nr.get("time") and isinstance(nr["time"], datetime): nr["time"] = nr["time"].isoformat()
                s_state[k].append(nr)
        elif k not in ["new_player_name_input"] and not k.startswith("remove_player_") and not k.startswith("rm_p_"):
            s_state[k] = v
    return s_state
def _deserialize_state(json_data):
    d_state = json_data.copy()
    for k, v in json_data.items():
        if isinstance(v, str):
            try: d_state[k] = datetime.fromisoformat(v); continue
            except (TypeError, ValueError): pass
        if k == "history" and isinstance(v, list):
            d_state[k] = []
            for r_dict in v:
                if isinstance(r_dict, dict):
                    nr = r_dict.copy();
                    if nr.get("time") and isinstance(nr["time"], str):
                        try: nr["time"] = datetime.fromisoformat(nr["time"])
                        except (TypeError, ValueError): pass
                    d_state[k].append(nr)
                else: st.warning(f"Skipping non-dict in '{k}': {r_dict}")
    return d_state

def find_file_in_drive(service, file_name, folder_id):
    st.write(f"Debug: find_file_in_drive called for file: {file_name}, folder: {folder_id is not None}")
    if not service or not folder_id:
        st.warning(f"Debug: find_file_in_drive returning None early (service or folder_id missing). Service: {service is not None}, Folder ID: {folder_id}")
        return None
    query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
    try:
        st.write(f"Debug: Drive query: {query}")
        response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = response.get('files', [])
        if files:
            st.success(f"Debug: Found file {file_name} with ID {files[0]['id']}")
            return files[0]['id']
        else:
            st.info(f"Debug: File {file_name} not found in Drive.")
            return None
    except HttpError as e:
        st.error(f"Debug: API HttpError finding file {file_name}: {e}. Response content: {e.content}")
        return None
    except Exception as e:
        st.error(f"Debug: Unexpected error finding file {file_name}: {e}")
        return None

def load_game_state_from_backend(game_id):
    st.write(f"Debug: load_game_state_from_backend called for game_id: {game_id}")
    if not drive_service or not DRIVE_FOLDER_ID or not game_id:
        st.warning(f"Debug: Load returning None early. Drive Service: {drive_service is not None}, Folder ID: {DRIVE_FOLDER_ID is not None}, Game ID: {game_id}")
        return None
    file_name = f"{game_id}.json"
    try:
        file_id = find_file_in_drive(drive_service, file_name, DRIVE_FOLDER_ID)
        if file_id:
            st.write(f"Debug: Loading file_id {file_id} for game {game_id}")
            request = drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: status, done = downloader.next_chunk()
            game_state_json_str = fh.getvalue().decode('utf-8')
            st.success(f"Debug: Successfully downloaded game data for {game_id}")
            game_data_dict = json.loads(game_state_json_str)
            return _deserialize_state(game_data_dict)
        else:
            st.info(f"Debug: No file_id found by find_file_in_drive for {game_id}, load returns None.")
            return None # File not found by find_file_in_drive
    except HttpError as e:
        st.error(f"Debug: API HttpError loading game {game_id} from GDrive: {e}. Response content: {e.content}")
        return None
    except Exception as e:
        st.error(f"Debug: Unexpected error loading game {game_id} from GDrive: {e}")
        return None

def save_game_state_to_backend(game_id, state):
    st.write(f"Debug: save_game_state_to_backend called for game_id: {game_id}")
    if not drive_service or not DRIVE_FOLDER_ID or not game_id:
        st.warning(f"Debug: Save returning early. Drive Service: {drive_service is not None}, Folder ID: {DRIVE_FOLDER_ID is not None}, Game ID: {game_id}")
        return
    file_name = f"{game_id}.json"
    try:
        serializable_dict_state = _serialize_state(state.copy())
        if "oldest_ticket_days_to_beat" in serializable_dict_state:
            del serializable_dict_state["oldest_ticket_days_to_beat"]
        game_state_json_str = json.dumps(serializable_dict_state, indent=2)
        file_metadata = {'name': file_name, 'parents': [DRIVE_FOLDER_ID]}
        media = MediaIoBaseUpload(io.BytesIO(game_state_json_str.encode('utf-8')),
                                  mimetype='application/json', resumable=True)
        existing_file_id = find_file_in_drive(drive_service, file_name, DRIVE_FOLDER_ID)
        st.write(f"Debug: Attempting to save {file_name}. Existing file_id: {existing_file_id}")
        if existing_file_id:
            drive_service.files().update(fileId=existing_file_id, media_body=media).execute()
            st.success(f"Debug: Game state for {game_id} UPDATED in Drive.")
        else:
            drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            st.success(f"Debug: Game state for {game_id} CREATED in Drive.")
    except HttpError as e:
        st.error(f"Debug: API HttpError saving game {game_id} to GDrive: {e}. Response content: {e.content}")
    except Exception as e:
        st.error(f"Debug: Unexpected error saving game {game_id} to GDrive: {e}")

# ---------- Logo & Title (no changes) ----------
try: st.image(LOGO_PATH, width=150)
except Exception: st.warning(f"Logo ({LOGO_PATH}) not found.")
st.title(f"💣 Pass the Bomb - ASMPT Edition"); st.caption(f"Version: {APP_VERSION}")
st.markdown("### _Don't get caught holding the bomb when time runs out!_")
st.markdown("#### _The ultimate loser buys the Matcha Lattes!_ 🍵")

query_params = st.query_params 

# ---------- Manage Game ID and Load State ----------
# This block now runs after Drive service initialization attempt
if drive_service and DRIVE_FOLDER_ID: # Proceed only if Drive service is available
    current_game_id_from_url = query_params.get("game_id", None)
    if "game_loaded_from_backend" not in st.session_state:
        st.session_state.game_loaded_from_backend = False
        if current_game_id_from_url:
            st.write(f"Debug: URL has game_id: {current_game_id_from_url}. Attempting to load.")
            loaded_state = load_game_state_from_backend(current_game_id_from_url)
            if loaded_state:
                for k, v in loaded_state.items(): st.session_state[k] = v
                st.session_state.game_id = loaded_state.get("game_id", current_game_id_from_url)
                st.session_state.game_loaded_from_backend = True; st.toast(f"Loaded: {st.session_state.game_id}",icon="🔄")
                st.write(f"Debug: Successfully loaded state for game_id: {st.session_state.game_id}")
            else:
                st.warning(f"Could not load game: {current_game_id_from_url}. Starting new game setup.") # This is your current message
                st.write(f"Debug: load_game_state_from_backend returned None for {current_game_id_from_url}.")
                if "game_id" in query_params: del query_params["game_id"]
                st.session_state.game_id = None
        else: 
            st.write("Debug: No game_id in URL.")
            st.session_state.game_id = None
else: # Drive service not initialized
    st.write("Debug: Drive service or folder ID not available for loading game state.")
    if "game_id" in st.session_state: del st.session_state["game_id"] # Ensure clean state
    if "game_loaded_from_backend" not in st.session_state : st.session_state.game_loaded_from_backend = False


# ---------- Initialise Session State (no changes) ----------
default_state_keys = {"game_started": False, "players": [], "pending_players": [], "current_holder": None,
    "game_end_time": None, "history": [], "game_id": None}
for k, dv in default_state_keys.items():
    if k not in st.session_state: st.session_state[k] = dv

# ---------- Game Setup UI (no changes, but save calls check drive_service) ----------
if not st.session_state.game_started:
    st.subheader("🎮 Setup New Game")
    p_col1, p_col2 = st.columns(2)
    with p_col1:
        with st.form("add_players_form", clear_on_submit=True):
            name = st.text_input("Enter player name", key="new_player_name_input")
            add_p_submitted = st.form_submit_button("➕ Add Player")
            if add_p_submitted and name.strip():
                if name.strip() not in st.session_state.pending_players: st.session_state.pending_players.append(name.strip())
                else: st.warning(f"{name.strip()} already in list.")
    with p_col2:
        if st.session_state.pending_players:
            st.markdown("**Players to Add:**")
            for i, pn in enumerate(list(st.session_state.pending_players)):
                rc1,rc2=st.columns([.8,.2]); rc1.markdown(f"- {pn}")
                if rc2.button("❌",key=f"rm_p_{pn}_{i}",help=f"Remove {pn}"): st.session_state.pending_players.pop(i); st.rerun()
        else: st.markdown("_No players added._")
    gd_label = st.selectbox("Game duration:",options=list(DEFAULT_GAME_DURATIONS.keys()),index=1) # Changed default to 30 mins for quicker test
    if len(st.session_state.pending_players) < 2: st.info("Add at least 2 players.")
    else:
        if st.button("✅ Start Game",type="primary",use_container_width=True):
            if not (drive_service and DRIVE_FOLDER_ID): 
                st.error("Google Drive not configured. Cannot start game requiring persistence.")
            else:
                if not st.session_state.game_id: 
                    st.session_state.game_id=generate_game_id()
                    query_params["game_id"]=st.session_state.game_id
                    st.write(f"Debug: New game started with ID: {st.session_state.game_id}")
                else:
                    st.write(f"Debug: Starting game with existing ID: {st.session_state.game_id}")

                st.session_state.players=list(st.session_state.pending_players); st.session_state.pending_players=[]
                st.session_state.current_holder=random.choice(st.session_state.players)
                st.session_state.game_end_time=datetime.now()+DEFAULT_GAME_DURATIONS[gd_label]
                st.session_state.history=[]
                st.session_state.game_started=True; st.session_state.game_loaded_from_backend=True
                save_game_state_to_backend(st.session_state.game_id,st.session_state)
                st.balloons(); st.rerun()

# ---------- Game Interface UI (no changes, but save calls check drive_service) ----------
if st.session_state.game_started:
    now = datetime.now()
    time_left_game = (st.session_state.game_end_time - now) if isinstance(st.session_state.game_end_time, datetime) else timedelta(seconds=0)

    if time_left_game.total_seconds() <= 0:
        st.error(f"🏁 **GAME OVER!** 🏁"); st.subheader(f"Final bomb holder: **{st.session_state.current_holder}**")
        st.warning(f"**{st.session_state.current_holder}** buys Matcha Lattes! 🍵"); st.balloons()
        if drive_service and DRIVE_FOLDER_ID: save_game_state_to_backend(st.session_state.game_id, st.session_state)
    else: 
        st.subheader(f"💣 Bomb held by: {st.session_state.current_holder}")
        st.metric("Game Ends In:", format_timedelta(time_left_game)); st.markdown("---")
        st.subheader("↪️ Pass the Bomb")
        st.markdown("_Enter any ticket details to pass the bomb._")
        can_pass = False; pass_to_options = []
        if st.session_state.current_holder and st.session_state.current_holder in st.session_state.players and \
           isinstance(st.session_state.players, list) and len(st.session_state.players) >= 2:
             pass_to_options = [p for p in st.session_state.players if p != st.session_state.current_holder]
             if pass_to_options: can_pass = True
        if not can_pass: st.error("Cannot pass bomb: No valid players to pass to.")
        else:
            current_turn_identifier = len(st.session_state.get("history", []))
            dynamic_form_key = f"pass_form_turn_{current_turn_identifier}_{st.session_state.current_holder}"
            with st.form(dynamic_form_key):
                st.markdown(f"You are: **{st.session_state.current_holder}** (current bomb holder)")
                next_player = st.selectbox("Pass bomb to:", pass_to_options, index=0)
                ticket_number = st.text_input("Ticket Number/ID:", placeholder="e.g. INC123456")
                old_ticket_val = st.session_state.get("oldest_ticket_days_to_beat", 0) 
                d_val = datetime.now().date() - timedelta(days=max(0, int(old_ticket_val)) + 1)
                ticket_date = st.date_input("Ticket creation date:", max_value=datetime.now().date(), value=d_val)
                submit_pass_button_pressed = st.form_submit_button("Pass This Bomb!")
                if submit_pass_button_pressed:
                    if not (drive_service and DRIVE_FOLDER_ID):
                        st.error("Google Drive not configured. Cannot save pass action.")
                    elif not ticket_number.strip(): st.warning("⚠️ Enter ticket number.")
                    else:
                        days_old = (datetime.now().date() - ticket_date).days
                        if days_old < 0: st.error("Ticket date cannot be future!")
                        else:
                            st.session_state.history.append({
                                "from": st.session_state.current_holder, "to": next_player,
                                "ticket": ticket_number, "days_old": days_old, "time": now
                            })
                            st.session_state.current_holder = next_player
                            st.success(f"🎉 Bomb Passed to {next_player}! Ticket: {days_old}d old.")
                            save_game_state_to_backend(st.session_state.game_id, st.session_state)
                            st.rerun()
                                
    st.markdown("---"); st.subheader("📊 Game Stats & History")
    with st.expander("📜 Bomb Pass History", expanded=True):
        if not st.session_state.history: st.caption("_No passes yet._")
        else:
            for r in reversed(st.session_state.history):
                t_val=r.get('time');t_str=t_val.strftime('%Y-%m-%d %H:%M:%S') if isinstance(t_val,datetime) else str(t_val)
                st.markdown(f"-`{r.get('from','?')}`➡️`{r.get('to','?')}`(Tkt:`{r.get('ticket','?')}`–**{r.get('days_old','?')}d old**) at {t_str}")

# ---------- Sidebar Controls ----------
with st.sidebar:
    st.header("⚙️ Game Controls")
    if st.session_state.game_id: st.markdown(f"**Game ID:** `{st.session_state.game_id}`"); st.caption("Share URL to join.")
    else: st.caption("Start new game or use Game ID URL.")
    if st.session_state.game_started:
        st.subheader("Players:")
        if st.session_state.players:
            for p in st.session_state.players: st.markdown(f"- **{p}** {'💣' if p==st.session_state.current_holder else ''}")
        else: st.caption("_No players._")
        st.markdown("---")
        if st.button("⚠️ End Game Prematurely",type="secondary"):
            st.session_state.game_end_time=datetime.now()
            if drive_service and DRIVE_FOLDER_ID: save_game_state_to_backend(st.session_state.game_id,st.session_state)
            st.rerun()
    if st.button("🔄 Start New Setup / Restart App",type="primary"):
        current_q_params=st.query_params.to_dict()
        if "game_id" in current_q_params: del current_q_params["game_id"]; st.query_params.from_dict(current_q_params)
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.toast("App reset.",icon="🧹"); st.rerun()

# ---------- Footer ----------
st.markdown("<br><hr><center><sub>Made for ASMPT · Powered by Streamlit & Matcha</sub></center>", unsafe_allow_html=True)

# ---------- Live Timer Update (Still commented out) ----------
# if st.session_state.get("game_started", False) and isinstance(st.session_state.get("game_end_time"), datetime):
#     if drive_service and DRIVE_FOLDER_ID: 
#         if st.session_state.game_end_time > datetime.now():
#             time.sleep(1)
#             st.rerun()
