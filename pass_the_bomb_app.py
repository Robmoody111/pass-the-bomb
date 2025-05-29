import streamlit as st
from datetime import datetime, timedelta
import random
import json
import os

# ---------- App Constants & Configuration ----------
APP_VERSION = "2.1 Persistent"
LOGO_PATH = "asmpt_logo.png" # Ensure this image is in the same directory
GAME_STATES_DIR = "game_states" # Directory to store game state JSON files

DEFAULT_GAME_DURATIONS = {
    "⚡ Quick Blast (30 mins)": timedelta(minutes=30),
    "🕒 Standard (1 hour)": timedelta(hours=1),
    "☀️ Half Day (4 hours)": timedelta(hours=4),
    "🗓️ Full Day (8 hours)": timedelta(hours=8),
    "💼 Week (Office Hours)": timedelta(days=5),
}
DEFAULT_BOMB_FUSE_OPTIONS = {
    "⚠️ Very Short (15s)": 15,
    "⏱️ Short (30s)": 30,
    "💣 Standard (1 min)": 60,
    "⏳ Long (2 mins)": 120,
    "🐌 Very Long (5 mins)": 300,
}

# ---------- Helper Functions ----------
def format_timedelta(td):
    if td is None or td.total_seconds() < 0:
        return "0 seconds"
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0: parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0: parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0: parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if not parts or (days == 0 and hours == 0 and minutes == 0):
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    return ", ".join(parts) if parts else "0 seconds"

# ---------- Persistence Functions (Local JSON Files) ----------
# Ensure the game_states directory exists
if not os.path.exists(GAME_STATES_DIR):
    try:
        os.makedirs(GAME_STATES_DIR)
    except OSError as e:
        st.error(f"Could not create directory {GAME_STATES_DIR}: {e}. Game persistence might fail.")

def generate_game_id():
    return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=8))

def _serialize_state(state_dict):
    """Converts datetime objects to ISO strings for JSON."""
    serializable_state = {}
    for key, value in state_dict.items():
        if isinstance(value, (datetime, timedelta)):
            serializable_state[key] = value.isoformat()
        elif key in ["history", "explosion_log"] and isinstance(value, list):
            serializable_state[key] = []
            for record in value:
                new_record = record.copy()
                if new_record.get("time") and isinstance(new_record["time"], datetime):
                    new_record["time"] = new_record["time"].isoformat()
                serializable_state[key].append(new_record)
        elif key not in ["new_player_name"] and not key.startswith("remove_player_"): # Exclude transient UI keys
            serializable_state[key] = value
    return serializable_state

def _deserialize_state(json_data):
    """Converts ISO strings back to datetime objects."""
    deserialized_state = json_data.copy()
    for key, value in json_data.items():
        if isinstance(value, str):
            try:
                # Attempt to parse as datetime
                dt_val = datetime.fromisoformat(value)
                deserialized_state[key] = dt_val
                continue # Move to next item
            except (TypeError, ValueError):
                pass # Not a datetime string, try timedelta

            try:
                # Attempt to parse as timedelta (less common directly from JSON, but for completeness)
                # This part is tricky as timedelta doesn't have a direct fromisoformat
                # Assuming format like "P7DT12H30M20S" or simple seconds string if saved that way
                if value.startswith("P"): # ISO 8601 duration
                    # This requires a robust parser like `isodate` or manual parsing.
                    # For simplicity, we'll assume timedeltas were stored as total seconds if needed
                    pass
                # If you stored timedeltas as total seconds:
                # td_seconds = float(value)
                # deserialized_state[key] = timedelta(seconds=td_seconds)
            except (TypeError, ValueError):
                pass # Not a recognized format

        if key in ["history", "explosion_log"] and isinstance(value, list):
            deserialized_state[key] = []
            for record_str_dict in value:
                new_record = record_str_dict.copy()
                if new_record.get("time") and isinstance(new_record["time"], str):
                    try:
                        new_record["time"] = datetime.fromisoformat(new_record["time"])
                    except (TypeError, ValueError):
                        pass # Keep as string if not parsable
                deserialized_state[key].append(new_record)
    return deserialized_state

def load_game_state_from_backend(game_id):
    if not game_id: return None
    filepath = os.path.join(GAME_STATES_DIR, f"{game_id}.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                state_data_json = json.load(f)
            return _deserialize_state(state_data_json)
        except (json.JSONDecodeError, TypeError, ValueError, OSError) as e:
            st.error(f"Error loading game state for {game_id}: {e}")
            return None
    return None

def save_game_state_to_backend(game_id, state):
    if not game_id:
        st.error("Cannot save game state: No Game ID provided.")
        return
    filepath = os.path.join(GAME_STATES_DIR, f"{game_id}.json")
    try:
        serializable_state = _serialize_state(state)
        with open(filepath, 'w') as f:
            json.dump(serializable_state, f, indent=2)
    except Exception as e:
        st.error(f"Error saving game state ({game_id}): {e}")

# ---------- Page Config ----------
st.set_page_config(page_title="Pass the Bomb", layout="centered", initial_sidebar_state="collapsed")

# ---------- Logo & Title ----------
try:
    st.image(LOGO_PATH, width=150)
except Exception:
    st.warning(f"Logo image ({LOGO_PATH}) not found.")
st.title(f"💣 Pass the Bomb - ASMPT Edition")
st.caption(f"Version: {APP_VERSION}")
st.markdown("### _Don't get caught holding the bomb! Pass it by logging your 'oldest' resolved ticket._")
st.markdown("#### _The ultimate loser buys the Matcha Lattes!_ 🍵")

# ---------- Manage Game ID and Load State ----------
query_params = st.query_params
current_game_id_from_url = query_params.get("game_id", None)

if "game_loaded_from_backend" not in st.session_state:
    st.session_state.game_loaded_from_backend = False
    if current_game_id_from_url:
        loaded_state = load_game_state_from_backend(current_game_id_from_url)
        if loaded_state:
            for key, value in loaded_state.items():
                st.session_state[key] = value
            # Ensure game_id from loaded state is preferred if it exists, otherwise use URL's
            st.session_state.game_id = loaded_state.get("game_id", current_game_id_from_url)
            st.session_state.game_loaded_from_backend = True
            st.toast(f"Successfully loaded game: {st.session_state.game_id}", icon="🔄")
        else:
            st.warning(f"Could not find/load game: {current_game_id_from_url}. Starting new game setup.")
            if "game_id" in query_params: query_params.remove("game_id")
            st.session_state.game_id = None
    else:
        st.session_state.game_id = None

# ---------- Initialise Session State (if not loaded) ----------
default_state_keys = {
    "game_started": False, "players": [], "pending_players": [], "current_holder": None,
    "bomb_timer_end": None, "game_end_time": None, "history": [],
    "oldest_ticket_days_to_beat": 0, "explosion_log": [], "bomb_fuse_setting": 60
}
for key, default_value in default_state_keys.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# ---------- Game Setup UI ----------
if not st.session_state.game_started:
    st.subheader("🎮 Setup New Game")
    # Player Management
    player_col1, player_col2 = st.columns(2)
    with player_col1:
        with st.form("add_players_form", clear_on_submit=True):
            name = st.text_input("Enter player name", key="new_player_name_input")
            add_player_submitted = st.form_submit_button("➕ Add Player")
            if add_player_submitted and name.strip():
                if name.strip() not in st.session_state.pending_players:
                    st.session_state.pending_players.append(name.strip())
                else:
                    st.warning(f"{name.strip()} is already in the list.")
                # No rerun, let form clear and list update below

    with player_col2:
        if st.session_state.pending_players:
            st.markdown("**Players to Add:**")
            for i, player_name in enumerate(list(st.session_state.pending_players)):
                row_col1, row_col2 = st.columns([0.8, 0.2])
                row_col1.markdown(f"- {player_name}")
                if row_col2.button("❌", key=f"remove_player_{i}", help=f"Remove {player_name}"):
                    st.session_state.pending_players.pop(i)
                    st.rerun()
        else:
            st.markdown("_No players added yet for this game._")

    game_duration_label = st.selectbox(
        "Select game duration:", options=list(DEFAULT_GAME_DURATIONS.keys()), index=1)
    selected_fuse_label = st.selectbox(
        "Select bomb pass timer (fuse):", options=list(DEFAULT_BOMB_FUSE_OPTIONS.keys()), index=2)

    if len(st.session_state.pending_players) < 2:
        st.info("Add at least **2 players** to start the game.")
    else:
        if st.button("✅ Start Game", type="primary", use_container_width=True):
            if not st.session_state.game_id: # New game being started
                st.session_state.game_id = generate_game_id()
                query_params["game_id"] = st.session_state.game_id

            st.session_state.players = list(st.session_state.pending_players)
            st.session_state.current_holder = random.choice(st.session_state.players)
            st.session_state.bomb_fuse_setting = DEFAULT_BOMB_FUSE_OPTIONS[selected_fuse_label]
            st.session_state.bomb_timer_end = datetime.now() + timedelta(seconds=st.session_state.bomb_fuse_setting)
            st.session_state.game_end_time = datetime.now() + DEFAULT_GAME_DURATIONS[game_duration_label]
            st.session_state.history = []
            st.session_state.explosion_log = []
            st.session_state.oldest_ticket_days_to_beat = 0
            st.session_state.game_started = True
            st.session_state.game_loaded_from_backend = True # Mark as active

            save_game_state_to_backend(st.session_state.game_id, st.session_state)
            st.balloons()
            st.rerun()

# ---------- Game Interface UI ----------
if st.session_state.game_started:
    now = datetime.now()
    time_left_bomb = st.session_state.bomb_timer_end - now if st.session_state.bomb_timer_end else timedelta(seconds=0)
    time_left_game = st.session_state.game_end_time - now if st.session_state.game_end_time else timedelta(seconds=0)

    # Game Over
    if time_left_game.total_seconds() <= 0:
        st.error(f"🏁 **GAME OVER!** 🏁")
        st.subheader(f"The final bomb holder is: **{st.session_state.current_holder}**")
        st.warning(f"Looks like **{st.session_state.current_holder}** is buying the Matcha Lattes! 🍵")
        st.balloons()
        save_game_state_to_backend(st.session_state.game_id, st.session_state) # Save final state
        # Restart button is in sidebar

    # Bomb Explosion (fuse timer)
    elif time_left_bomb.total_seconds() <= 0:
        st.error(f"💥 **BOOM!** 💥 The bomb exploded in **{st.session_state.current_holder}**'s hands!")
        st.session_state.explosion_log.append({
            "player": st.session_state.current_holder, "time": now
        })
        st.session_state.bomb_timer_end = now + timedelta(seconds=st.session_state.bomb_fuse_setting)
        st.info(f"**{st.session_state.current_holder}** keeps the bomb. Timer reset!")
        st.toast("💣💥 Oh no! Timer reset!", icon="🔥")
        save_game_state_to_backend(st.session_state.game_id, st.session_state)
        # Auto-rerun can be jarring here, let user see and then next interaction updates, or add explicit refresh
        # Forcing a rerun to update timer display immediately
        st.rerun()

    # Gameplay Active
    else:
        st.subheader("🔥 The Bomb is Active! 🔥")
        metric_col1, metric_col2 = st.columns(2)
        metric_col1.metric("Bomb currently held by:", st.session_state.current_holder)
        metric_col2.metric("Pass it in:", format_timedelta(time_left_bomb))
        st.progress(max(0, time_left_bomb.total_seconds() / st.session_state.bomb_fuse_setting))
        st.caption(f"**Overall game ends in:** `{format_timedelta(time_left_game)}`")
        st.markdown("---")

        st.subheader("↪️ Pass the Bomb")
        pass_msg = f"To pass, log a ticket **older than {st.session_state.oldest_ticket_days_to_beat} days**."
        if st.session_state.oldest_ticket_days_to_beat == 0:
            pass_msg += " (_Any ticket age for the first successful pass._)"
        st.markdown(pass_msg)

        with st.form("pass_form"):
            st.markdown(f"You are: **{st.session_state.current_holder}** (current bomb holder)")
            pass_to_options = [p for p in st.session_state.players if p != st.session_state.current_holder]
            if not pass_to_options: # Should only happen with 1 player left if rules allowed
                st.error("No one to pass the bomb to!")
                st.stop()

            next_player = st.selectbox("Pass the bomb to:", pass_to_options, index=0)
            ticket_number = st.text_input("Enter Ticket Number/ID (e.g., JIRA-123)", placeholder="e.g. JIRA-123")
            default_ticket_date = datetime.now().date() - timedelta(days=st.session_state.oldest_ticket_days_to_beat + 1)
            ticket_date = st.date_input("Ticket **creation** date:", max_value=datetime.now().date(), value=default_ticket_date)
            submit_pass = st.form_submit_button("🚀 Pass the Bomb!", type="primary", use_container_width=True)

            if submit_pass:
                if not ticket_number.strip():
                    st.warning("⚠️ Please enter a ticket number.")
                else:
                    days_old = (datetime.now().date() - ticket_date).days
                    if days_old < 0:
                        st.error("Ticket creation date cannot be in the future!")
                    elif days_old <= st.session_state.oldest_ticket_days_to_beat and st.session_state.oldest_ticket_days_to_beat != 0 :
                        st.error(f"❌ **Pass Failed!** Ticket is **{days_old} days old**. Must be older than **{st.session_state.oldest_ticket_days_to_beat} days**.")
                    else:
                        st.session_state.history.append({
                            "from": st.session_state.current_holder, "to": next_player,
                            "ticket": ticket_number, "days_old": days_old, "time": now
                        })
                        st.session_state.current_holder = next_player
                        st.session_state.bomb_timer_end = now + timedelta(seconds=st.session_state.bomb_fuse_setting)
                        st.session_state.oldest_ticket_days_to_beat = max(st.session_state.oldest_ticket_days_to_beat, days_old)

                        st.success(f"🎉 Bomb Passed to **{next_player}**! Your ticket was **{days_old} days old**.")
                        st.info(f"New target: Beat a ticket older than **{st.session_state.oldest_ticket_days_to_beat} days**.")
                        save_game_state_to_backend(st.session_state.game_id, st.session_state)
                        st.rerun()

    # --- Display Game Stats & History ---
    st.markdown("---")
    st.subheader("📊 Game Stats & History")
    with st.expander("📜 Bomb Pass History", expanded=True):
        if not st.session_state.history: st.caption("_No passes made yet._")
        else:
            for record in reversed(st.session_state.history):
                time_str = record['time'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(record.get('time'), datetime) else str(record.get('time'))
                st.markdown(f"- `{record['from']}` ➡️ `{record['to']}` (Ticket: `{record['ticket']}` – **{record['days_old']}d old**) at {time_str}")
    with st.expander("💥 Fuse Explosion Log (Hall of Shame!)"):
        if not st.session_state.explosion_log: st.caption("_No one caught by the fuse... yet!_")
        else:
            for entry in reversed(st.session_state.explosion_log):
                time_str = entry['time'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(entry.get('time'), datetime) else str(entry.get('time'))
                st.markdown(f"- **{entry['player']}** caught by fuse at {time_str}!")

# ---------- Sidebar Controls ----------
with st.sidebar:
    st.header("⚙️ Game Controls")
    if st.session_state.game_id:
        st.markdown(f"**Game ID:** `{st.session_state.game_id}`")
        st.caption("Share the full URL (including '?game_id=...') to let others join this game.")
    else:
        st.caption("Start a new game or use a Game ID URL to load an existing one.")

    if st.session_state.game_started:
        st.subheader("Players:")
        for player in st.session_state.players:
            indicator = "💣" if player == st.session_state.current_holder else ""
            st.markdown(f"- **{player}** {indicator}")
        st.markdown("---")
        if st.button("⚠️ End Game Prematurely", type="secondary"):
            st.session_state.game_end_time = datetime.now() # Force game end
            save_game_state_to_backend(st.session_state.game_id, st.session_state)
            st.rerun()

    if st.button("🔄 Start New Setup / Restart", type="primary"):
        # Clear relevant session state for a full restart, preserving game_id if user wants to restart *this* game
        # Or clear everything to truly start fresh.
        keys_to_clear = list(st.session_state.keys())
        game_id_in_url = query_params.get("game_id", None)

        for key in keys_to_clear:
            if key not in ['game_loaded_from_backend']: # Keep flags that control initial load logic
                del st.session_state[key]
        
        if game_id_in_url: # If a game_id was in URL, remove it to signify new setup
            query_params.remove("game_id")

        st.toast("Game reset. Setup a new game or load one via URL.", icon="🧹")
        st.rerun()

# ---------- Footer ----------
st.markdown("<br><hr><center><sub>Made for ASMPT · Powered by Streamlit & Matcha</sub></center>", unsafe_allow_html=True)

# Optional: Auto-refresh to make timers tick down more visibly
# This can be disruptive if users are typing. Use with caution.
# import time
# if st.session_state.game_started:
#    if st.session_state.bomb_timer_end and st.session_state.game_end_time:
#        if (st.session_state.bomb_timer_end > datetime.now() and
#            st.session_state.game_end_time > datetime.now()):
#            time.sleep(1)
#            st.rerun()
