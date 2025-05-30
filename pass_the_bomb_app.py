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
APP_VERSION = "5.3 Deferred Load Fix"

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
    "defer_load_after_create": False  # NEW
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
        elif k != "defer_load_after_create":
            result[k] = v
    return result

def _deserialize(data):
    result = data.copy()
    for k, v in data.items():
        if k == "history":
            result[k] = []
            for entry in v:
                if isinstance(entry.get("time"), str):
                    try: entry["time"] = datetime.fromisoformat(entry["time"])
                    except: pass
                result[k].append(entry)
        elif isinstance(v, str):
            try: result[k] = datetime.fromisoformat(v)
            except: pass
    return result

def save_to_drive(game_id, state):
    json_data = json.dumps(_serialize(state), indent=2)
    media = MediaIoBaseUpload(io.BytesIO(json_data.encode()), mimetype="application/json")
    file_meta = {"name": f"{game_id}.json", "parents": [DRIVE_FOLDER_ID]}
    existing_id = find_file(drive_service, f"{game_id}.json", DRIVE_FOLDER_ID)
    if existing_id:
        drive_service.files().update(fileId=existing_id, media_body=media).execute()
    else:
        drive_service.files().create(body=file_meta, media_body=media).execute()

def load_from_drive(game_id):
    file_id = find_file(drive_service, f"{game_id}.json", DRIVE_FOLDER_ID)
    if not file_id: return None
    req = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    MediaIoBaseDownload(fh, req).next_chunk()
    return _deserialize(json.loads(fh.getvalue().decode()))

# --- UI Layout ---
try: st.image(LOGO_PATH, width=180)
except: st.warning("Logo missing.")
st.title("💣 Pass the Bomb – ASMPT Edition")
st.caption(f"Version {APP_VERSION}")
st.markdown("### _Don't get caught holding the bomb when time runs out!_")
st.markdown("#### _The ultimate loser buys the Matcha Lattes! 🍵_")

# --- Session Init ---
query_params = st.query_params
for k, v in DEFAULT_STATE_KEYS.items():
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state["defer_load_after_create"]:
    st.session_state["defer_load_after_create"] = False
    st.stop()

# --- Load Existing Game if game_id in URL ---
if not st.session_state["game_started"]:
    gid = query_params.get("game_id")
    if gid:
        state = load_from_drive(gid)
        if state:
            for k, v in state.items():
                st.session_state[k] = v
            st.session_state["game_id"] = gid
            st.session_state["game_started"] = True
            st.rerun()
        else:
            st.warning(f"Could not auto-refresh game: {gid}. It may no longer exist.")
            st.session_state["game_id"] = None

# --- New Game UI ---
if not st.session_state["game_started"]:
    st.subheader("🎮 Setup New Game")
    with st.form("add_players", clear_on_submit=True):
        name = st.text_input("Enter player name")
        submitted = st.form_submit_button("➕ Add Player")
        if submitted and name.strip() not in st.session_state["pending_players"]:
            st.session_state["pending_players"].append(name.strip())

    if st.session_state["pending_players"]:
        st.markdown("**Players:**")
        for p in st.session_state["pending_players"]:
            st.markdown(f"- {p}")

    dur_label = st.selectbox("Game Duration", list(DEFAULT_GAME_DURATIONS.keys()), index=1)

    if len(st.session_state["pending_players"]) < 2:
        st.info("Add at least 2 players to begin.")
    elif st.button("✅ Start Game"):
        st.session_state["game_id"] = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=8))
        st.query_params["game_id"] = st.session_state["game_id"]
        st.session_state["players"] = list(st.session_state["pending_players"])
        st.session_state["pending_players"] = []
        st.session_state["current_holder"] = random.choice(st.session_state["players"])
        st.session_state["game_end_time"] = datetime.now() + DEFAULT_GAME_DURATIONS[dur_label]
        st.session_state["history"] = []
        st.session_state["game_started"] = True
        save_to_drive(st.session_state["game_id"], st.session_state)
        st.session_state["defer_load_after_create"] = True
        st.rerun()

# --- Game Play ---
if st.session_state["game_started"]:
    now = datetime.now()
    game_left = st.session_state["game_end_time"] - now

    if game_left.total_seconds() <= 0:
        st.error("🏁 Game Over!")
        st.subheader(f"Final bomb holder: {st.session_state['current_holder']}")
        st.warning(f"**{st.session_state['current_holder']}** buys the Matcha Lattes! 🍵")
        save_to_drive(st.session_state["game_id"], st.session_state)
    else:
        st.subheader(f"💣 Bomb held by: {st.session_state['current_holder']}")
        st.metric("Time remaining:", str(game_left).split(".")[0])

        st.markdown("---")
        st.subheader("Pass the Bomb")
        with st.form("pass_form"):
            who = st.session_state["current_holder"]
            next_player = st.selectbox("Pass to:", [p for p in st.session_state["players"] if p != who])
            ticket = st.text_input("Ticket number")
            date = st.date_input("Ticket creation date", max_value=datetime.now().date())
            passed = st.form_submit_button("Pass This Bomb!")
            if passed:
                age = (datetime.now().date() - date).days
                st.session_state["history"].append({
                    "from": who,
                    "to": next_player,
                    "ticket": ticket,
                    "days_old": age,
                    "time": datetime.now()
                })
                st.session_state["current_holder"] = next_player
                save_to_drive(st.session_state["game_id"], st.session_state)
                st.success(f"Ticket was {age} days old. Bomb passed to {next_player}!")
                st.rerun()

        st.markdown("---")
        st.subheader("📜 Bomb Pass History")
        if st.session_state["history"]:
            for r in reversed(st.session_state["history"]):
                t = r["time"].strftime("%Y-%m-%d %H:%M:%S")
                st.markdown(f"- `{r['from']}` ➡️ `{r['to']}` – Ticket: `{r['ticket']}`, **{r['days_old']}d**, at {t}")
        else:
            st.caption("No passes yet.")

# --- Sidebar ---
with st.sidebar:
    st.header("Game Controls")
    if st.session_state["game_id"]:
        st.markdown(f"Game ID: `{st.session_state['game_id']}`")
    if st.button("🔁 Restart Game"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- Footer ---
st.markdown("<br><hr><center><sub>Made for ASMPT · Powered by Streamlit & Matcha</sub></center>", unsafe_allow_html=True)

# --- Live Refresh ---
if st.session_state["game_started"] and isinstance(st.session_state.get("game_end_time"), datetime):
    if st.session_state["game_end_time"] > datetime.now():
        time.sleep(1)
        st.rerun()
