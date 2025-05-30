import streamlit as st
from datetime import datetime, timedelta
import random
import json
import time # For the live countdown timer

# Google Drive API imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
import io

# --- Call st.set_page_config() as the VERY FIRST Streamlit command ---
st.set_page_config(page_title="Pass the Bomb", layout="centered", initial_sidebar_state="collapsed")
# --- END st.set_page_config() ---

# ---------- App Constants & Configuration ----------
APP_VERSION = "5.1 Auto-Refresh Game State" # <<<<<<< Updated Version
LOGO_PATH = "asmpt_logo.png"

DEFAULT_GAME_DURATIONS = {
    "☕ Short (15 mins)": timedelta(minutes=15),
    "⚡ Quick Blast (30 mins)": timedelta(minutes=30),
    "🕒 Standard (1 hour)": timedelta(hours=1),
    "☀️ Half Day (4 hours)": timedelta(hours=4),
    "🗓️ Full Day (8 hours)": timedelta(hours=8),
    "💼 Week (Office Hours)": timedelta(days=5),
}

# Define default_state_keys globally for access in load logic
DEFAULT_STATE_KEYS = {"game_started": False, "players": [], "pending_players": [], "current_holder": None,
    "game_end_time": None, "history": [], "game_id": None}


# ---------- Google Drive Service Initialization ----------
drive_service = None
DRIVE_FOLDER_ID = None

@st.cache_resource
def init_drive_service():
    gcp_creds_secret = st.secrets.get("gcp_service_account")
    folder_id_secret = st.secrets.get("google_drive_folder_id")
    temp_service = None; temp_folder_id = None
    if not gcp_creds_secret: st.error("CRITICAL: GCP service account secret NOT FOUND.")
    elif not folder_id_secret: st.warning("CRITICAL: Google Drive Folder ID secret NOT FOUND.")
    else:
        try:
            creds_json_dict = dict(gcp_creds_secret) if hasattr(gcp_creds_secret, 'items') else gcp_creds_secret
            temp_folder_id = str(folder_id_secret)
            creds = service_account.Credentials.from_service_account_info(creds_json_dict, scopes=['https://www.googleapis.com/auth/drive'])
            temp_service = build('drive', 'v3', credentials=creds, cache_discovery=False)
        except Exception as e: st.error(f"Failed to initialize GDrive: {e}"); temp_service = None; temp_folder_id = None
    return temp_service, temp_folder_id

drive_service, DRIVE_FOLDER_ID = init_drive_service()

# ---------- Helper Functions (no changes) ----------
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
def generate_game_id(): return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=8))
def _serialize_state(state_dict):
    s_state = {};
    for k, v in state_dict.items():
        if isinstance(v, datetime): s_state[k] = v.isoformat()
        elif k == "history" and isinstance(v, list):
            s_state[k] = []
            for r in v: nr = r.copy();
                         if nr.get("time") and isinstance(nr["time"], datetime): nr["time"] = nr["time"].isoformat()
                         s_state[k].append(nr)
        elif k not in ["new_player_name_input"] and not k.startswith("remove_player_") and not k.startswith("rm_p_"): s_state[k] = v
    return s_state
def _deserialize_state(json_data):
    d_state = json_data.copy();
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

# --- Google Drive Persistence Functions (no changes) ---
def find_file_in_drive(service, file_name, folder_id):
    if not service or not folder_id: return None
    query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
    try:
        response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = response.get('files', [])
        return files[0]['id'] if files else None
    except HttpError as e:
        if e.resp.status != 404 : st.error(f"DRIVE API ERROR (find_file for {file_name}): {e.resp.status} - {e.content.decode()}")
        return None
    except Exception as e: st.error(f"UNEXPECTED ERROR (find_file for {file_name}): {e}"); return None
def load_game_state_from_backend(game_id):
    if not drive_service or not DRIVE_FOLDER_ID or not game_id: return None
    file_name = f"{game_id}.json"
    try:
        file_id = find_file_in_drive(drive_service, file_name, DRIVE_FOLDER_ID)
        if file_id:
            request = drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request); done = False
            while not done: status, done = downloader.next_chunk()
            game_state_json_str = fh.getvalue().decode('utf-8')
            game_data_dict = json.loads(game_state_json_str)
            return _deserialize_state(game_data_dict)
        return None
    except HttpError as e:
        if e.resp.status != 404: st.error(f"DRIVE API ERROR (load_state for {game_id}): {e.resp.status} - {e.content.decode()}")
        return None
    except Exception as e: st.error(f"UNEXPECTED ERROR (load_state for {game_id}): {e}"); return None
def save_game_state_to_backend(game_id, session_state_proxy):
    if not drive_service or not DRIVE_FOLDER_ID or not game_id:
        st.error("SAVE FAILED: Drive service not configured or no game_id."); return False
    state_to_save_dict = {k: v for k, v in session_state_proxy.items()}
    file_name = f"{game_id}.json"
    try:
        serializable_dict_state = _serialize_state(state_to_save_dict)
        if "oldest_ticket_days_to_beat" in serializable_dict_state: del serializable_dict_state["oldest_ticket_days_to_beat"]
        game_state_json_str = json.dumps(serializable_dict_state, indent=2)
        file_metadata = {'name': file_name, 'parents': [DRIVE_FOLDER_ID]}
        media = MediaIoBaseUpload(io.BytesIO(game_state_json_str.encode('utf-8')), mimetype='application/json', resumable=True)
        existing_file_id = find_file_in_drive(drive_service, file_name, DRIVE_FOLDER_ID)
        if existing_file_id:
            drive_service.files().update(fileId=existing_file_id, media_body=media).execute()
            st.toast(f"Game {game_id} updated in Drive.", icon="💾")
        else:
            drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            st.toast(f"Game {game_id} created in Drive.", icon="✨")
        return True
    except HttpError as e: st.error(f"DRIVE API ERROR (save_state for {game_id}): {e.resp.status} - {e.content.decode()}"); return False
    except Exception as e: st.error(f"UNEXPECTED ERROR (save_state for {game_id}): {e}"); return False

# ---------- Logo & Title (no changes) ----------
try: st.image(LOGO_PATH, width=150)
except Exception: st.warning(f"Logo ({LOGO_PATH}) not found.")
st.title(f"💣 Pass the Bomb - ASMPT Edition"); st.caption(f"Version: {APP_VERSION}")
st.markdown("### _Don't get caught holding the bomb when time runs out!_")
st.markdown("#### _The ultimate loser buys the Matcha Lattes!_ 🍵")

query_params = st.query_params 

# ---------- MODIFIED: Manage Game ID and Load State (Auto-Refresh Logic) ----------
if drive_service and DRIVE_FOLDER_ID:
    current_game_id_from_url = query_params.get("game_id", None)

    if current_game_id_from_url:
        # If a game_id is in the URL, ALWAYS try to load its latest state.
        # This will be triggered by the 1-second auto-refresh (and other reruns) for all viewers.
        # st.write(f"Debug (ManageID - AutoRefresh): URL has game_id: {current_game_id_from_url}. Forcing load.") # Optional debug
        loaded_state = load_game_state_from_backend(current_game_id_from_url)
        
        if loaded_state:
            # Update session_state with the fresh data from GDrive
            for k, v in loaded_state.items():
                # Only update if the key is part of our known game state
                if k in DEFAULT_STATE_KEYS: # Use the globally defined DEFAULT_STATE_KEYS
                     st.session_state[k] = v
            
            st.session_state.game_id = loaded_state.get("game_id", current_game_id_from_url) # Ensure game_id is set
            st.session_state.game_started = loaded_state.get("game_started", False) # Ensure game
