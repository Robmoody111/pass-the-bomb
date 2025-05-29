import streamlit as st
from datetime import datetime, timedelta
import random
import json
import os
import time # For the live countdown

# ---------- App Constants & Configuration ----------
APP_VERSION = "3.1 Debug Pass Form" # <<<<<<< Updated Version
LOGO_PATH = "asmpt_logo.png"
GAME_STATES_DIR = "game_states"

DEFAULT_GAME_DURATIONS = {
    "☕ Short (15 mins)": timedelta(minutes=15),
    "⚡ Quick Blast (30 mins)": timedelta(minutes=30),
    "🕒 Standard (1 hour)": timedelta(hours=1),
    "☀️ Half Day (4 hours)": timedelta(hours=4),
    "🗓️ Full Day (8 hours)": timedelta(hours=8),
    "💼 Week (Office Hours)": timedelta(days=5),
}

# ---------- Helper Functions (そのまま) ----------
def format_timedelta(td):
    if td is None or td.total_seconds() < 0:
        return "0 seconds"
    total_seconds = int(td.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0: parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0: parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0: parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if total_seconds < 60 or not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    return ", ".join(parts) if parts else "0 seconds"

# ---------- Persistence Functions (そのまま) ----------
if not os.path.exists(GAME_STATES_DIR):
    try: os.makedirs(GAME_STATES_DIR)
    except OSError as e: st.error(f"Could not create directory {GAME_STATES_DIR}: {e}.")

def generate_game_id():
    return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=8))

def _serialize_state(state_dict):
    serializable_state = {}
    for key, value in state_dict.items():
        if isinstance(value, datetime):
            serializable_state[key] = value.isoformat()
        elif key == "history" and isinstance(value, list):
            serializable_state[key] = []
            for record in value:
                new_record = record.copy()
                if new_record.get("time") and isinstance(new_record["time"], datetime):
                    new_record["time"] = new_record["time"].isoformat()
                serializable_state[key].append(new_record)
        elif key not in ["new_player_name_input"] and not key.startswith("remove_player_"):
            serializable_state[key] = value
    return serializable_state

def _deserialize_state(json_data):
    deserialized_state = json_data.copy()
    for key, value in json_data.items():
        if isinstance(value, str):
            try:
                dt_val = datetime.fromisoformat(value)
                deserialized_state[key] = dt_val
                continue
            except (TypeError, ValueError): pass
        if key == "history" and isinstance(value, list):
            deserialized_state[key] = []
            for record_str_dict in value:
                if isinstance(record_str_dict, dict):
                    new_record = record_str_dict.copy()
                    if new_record.get("time") and isinstance(new_record["time"], str):
                        try: new_record["time"] = datetime.fromisoformat(new_record["time"])
                        except (TypeError, ValueError): pass
                    deserialized_state[key].append(new_record)
                else: st.warning(f"Skipping non-dict record in '{key}': {record_str_dict}")
    return deserialized_state

def load_game_state_from_backend(game_id):
    if not game_id: return None
    filepath = os.path.join(GAME_STATES_DIR, f"{game_id}.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f: state_data_json = json.load(f)
            return _deserialize_state(state_data_json)
        except Exception as e: st.error(f"Error loading game state for {game_id}: {e}")
    return None

def save_game_state_to_backend(game_id, state):
    if not game_id:
        st.error("Cannot save: No Game ID.")
        return
    filepath = os.path.join(GAME_STATES_DIR, f"{game_id}.json")
    try:
        serializable_state = _serialize_state(state)
        with open(filepath, 'w') as f: json.dump(serializable_state, f, indent=2)
    except Exception as e: st.error(f"Error saving game state ({game_id}): {e}")

# ---------- Page Config (そのまま) ----------
st.set_page_config(page_title="Pass the Bomb", layout="centered", initial_sidebar_state="collapsed")

# ---------- Logo & Title (そのまま) ----------
try: st.image(LOGO_PATH, width=150)
except Exception: st.warning(f"Logo image ({LOGO_PATH}) not found.")
st.title(f"💣 Pass the Bomb - ASMPT Edition")
st.caption(f"Version: {APP_VERSION}")
st.markdown("### _Don't get caught holding the bomb when time runs out!_")
st.markdown("#### _The ultimate loser buys the Matcha Lattes!_ 🍵")

# ---------- Manage Game ID and Load State (そのまま) ----------
query_params = st.query_params
current_game_id_from_url = query_params.get("game_id", None)
if "game_loaded_from_backend" not in st.session_state:
    st.session_state.game_loaded_from_backend = False
    if current_game_id_from_url:
        loaded_state = load_game_state_from_backend(current_game_id_from_url)
        if loaded_state:
            for key, value in loaded_state.items(): st.session_state[key] = value
            st.session_state.game_id = loaded_state.get("game_id", current_game_id_from_url)
            st.session_state.game_loaded_from_backend = True
            st.toast(f"Loaded game: {st.session_state.game_id}", icon="🔄")
        else:
            st.warning(f"Could not load game: {current_game_id_from_url}.")
            if "game_id" in query_params: query_params.remove("game_id")
            st.session_state.game_id = None
    else: st.session_state.game_id = None

# ---------- Initialise Session State (そのまま) ----------
default_state_keys = {
    "game_started": False, "players": [], "pending_players": [], "current_holder": None,
    "game_end_time": None, "history": [], "oldest_ticket_days_to_beat": 0, "game_id": None
}
for key, default_value in default_state_keys.items():
    if key not in st.session_state: st.session_state[key] = default_value

# ---------- Game Setup UI (そのまま) ----------
if not st.session_state.game_started:
    st.subheader("🎮 Setup New Game")
    player_col1, player_col2 = st.columns(2)
    with player_col1:
        with st.form("add_players_form", clear_on_submit=True):
            name = st.text_input("Enter player name", key="new_player_name_input")
            add_player_submitted = st.form_submit_button("➕ Add Player")
            if add_player_submitted and name.strip():
                if name.strip() not in st.session_state.pending_players:
                    st.session_state.pending_players.append(name.strip())
                else: st.warning(f"{name.strip()} is already in list.")
    with player_col2:
        if st.session_state.pending_players:
            st.markdown("**Players to Add:**")
            for i, player_name in enumerate(list(st.session_state.pending_players)):
                rc1, rc2 = st.columns([0.8, 0.2])
                rc1.markdown(f"- {player_name}")
                if rc2.button("❌", key=f"rm_p_{player_name}_{i}", help=f"Remove {player_name}"):
                    st.session_state.pending_players.pop(i)
                    st.rerun()
        else: st.markdown("_No players added._")
    game_duration_label = st.selectbox("Game duration:", options=list(DEFAULT_GAME_DURATIONS.keys()), index=2)
    if len(st.session_state.pending_players) < 2:
        st.info("Add at least 2 players.")
    else:
        if st.button("✅ Start Game", type="primary", use_container_width=True):
            if not st.session_state.game_id:
                st.session_state.game_id = generate_game_id()
                query_params["game_id"] = st.session_state.game_id
            st.session_state.players = list(st.session_state.pending_players)
            st.session_state.pending_players = []
            st.session_state.current_holder = random.choice(st.session_state.players)
            st.session_state.game_end_time = datetime.now() + DEFAULT_GAME_DURATIONS[game_duration_label]
            st.session_state.history = []
            st.session_state.oldest_ticket_days_to_beat = 0
            st.session_state.game_started = True
            st.session_state.game_loaded_from_backend = True
            save_game_state_to_backend(st.session_state.game_id, st.session_state)
            st.balloons()
            st.rerun()

# ---------- Game Interface UI ----------
if st.session_state.game_started:
    now = datetime.now()
    time_left_game = (st.session_state.game_end_time - now) if isinstance(st.session_state.game_end_time, datetime) else timedelta(seconds=0)

    if time_left_game.total_seconds() <= 0:
        st.error(f"🏁 **GAME OVER!** 🏁")
        st.subheader(f"Final bomb holder: **{st.session_state.current_holder}**")
        st.warning(f"**{st.session_state.current_holder}** buys Matcha Lattes! 🍵")
        st.balloons()
        save_game_state_to_backend(st.session_state.game_id, st.session_state)
    else:
        st.subheader(f"💣 Bomb held by: {st.session_state.current_holder}")
        st.metric("Game Ends In:", format_timedelta(time_left_game))
        st.markdown("---")
        st.subheader("↪️ Pass the Bomb")
        pass_msg = f"To pass, log ticket > {st.session_state.oldest_ticket_days_to_beat} days old."
        if st.session_state.oldest_ticket_days_to_beat == 0: pass_msg += " (Any age for 1st pass.)"
        st.markdown(pass_msg)

        # --- MODIFICATION 1: More robust can_pass logic ---
        can_pass = False
        pass_to_options = []
        if st.session_state.current_holder and \
           st.session_state.current_holder in st.session_state.players and \
           isinstance(st.session_state.players, list) and \
           len(st.session_state.players) >= 2: # Need at least one other player to pass to
             pass_to_options = [p for p in st.session_state.players if p != st.session_state.current_holder]
             if pass_to_options: # Ensure the list isn't empty after filtering
                 can_pass = True
        # --- END MODIFICATION 1 ---

        if not can_pass:
            st.error("Cannot pass bomb: No valid players to pass to, or an issue with current holder.")
        else:
            with st.form("pass_form"):
                st.markdown(f"You are: **{st.session_state.current_holder}** (current bomb holder)")
                next_player = st.selectbox("Pass bomb to:", pass_to_options, index=0)
                ticket_number = st.text_input("Ticket Number/ID:", placeholder="e.g. JIRA-123")
                d_val = datetime.now().date() - timedelta(days=max(0,st.session_state.oldest_ticket_days_to_beat) + 1)
                ticket_date = st.date_input("Ticket creation date:", max_value=datetime.now().date(), value=d_val)
                
                # --- MODIFICATION 2: Added a static key to the submit button ---
                submit_pass
