import streamlit as st
from datetime import datetime, timedelta
import random
import json
import os
import time # For the live countdown (currently commented out)

# ---------- App Constants & Configuration ----------
APP_VERSION = "3.4 Dynamic Form Key" # <<<<<<< Updated Version
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

# ---------- Persistence Functions (no changes) ----------
if not os.path.exists(GAME_STATES_DIR):
    try: os.makedirs(GAME_STATES_DIR)
    except OSError as e: st.error(f"Could not create dir {GAME_STATES_DIR}: {e}.")
def generate_game_id(): return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=8))
def _serialize_state(state_dict):
    s_state = {}
    for k, v in state_dict.items():
        if isinstance(v, datetime): s_state[k] = v.isoformat()
        elif k == "history" and isinstance(v, list):
            s_state[k] = []
            for r in v:
                nr = r.copy()
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
                    nr = r_dict.copy()
                    if nr.get("time") and isinstance(nr["time"], str):
                        try: nr["time"] = datetime.fromisoformat(nr["time"])
                        except (TypeError, ValueError): pass
                    d_state[k].append(nr)
                else: st.warning(f"Skipping non-dict in '{k}': {r_dict}")
    return d_state
def load_game_state_from_backend(gid):
    if not gid: return None
    fp = os.path.join(GAME_STATES_DIR, f"{gid}.json")
    if os.path.exists(fp):
        try:
            with open(fp, 'r') as f: data = json.load(f)
            return _deserialize_state(data)
        except Exception as e: st.error(f"Error loading {gid}: {e}")
    return None
def save_game_state_to_backend(gid, state):
    if not gid: st.error("Cannot save: No Game ID."); return
    fp = os.path.join(GAME_STATES_DIR, f"{gid}.json")
    try:
        s_state = _serialize_state(state)
        with open(fp, 'w') as f: json.dump(s_state, f, indent=2)
    except Exception as e: st.error(f"Error saving ({gid}): {e}")

# ---------- Page Config, Logo & Title, Manage Game ID, Initialise Session State (no changes) ----------
st.set_page_config(page_title="Pass the Bomb", layout="centered", initial_sidebar_state="collapsed")
try: st.image(LOGO_PATH, width=150)
except Exception: st.warning(f"Logo ({LOGO_PATH}) not found.")
st.title(f"💣 Pass the Bomb - ASMPT Edition"); st.caption(f"Version: {APP_VERSION}")
st.markdown("### _Don't get caught holding the bomb when time runs out!_")
st.markdown("#### _The ultimate loser buys the Matcha Lattes!_ 🍵")
query_params = st.query_params
current_game_id_from_url = query_params.get("game_id", None)
if "game_loaded_from_backend" not in st.session_state:
    st.session_state.game_loaded_from_backend = False
    if current_game_id_from_url:
        loaded_state = load_game_state_from_backend(current_game_id_from_url)
        if loaded_state:
            for k, v in loaded_state.items(): st.session_state[k] = v
            st.session_state.game_id = loaded_state.get("game_id", current_game_id_from_url)
            st.session_state.game_loaded_from_backend = True; st.toast(f"Loaded: {st.session_state.game_id}",icon="🔄")
        else:
            st.warning(f"Could not load: {current_game_id_from_url}.")
            if "game_id" in query_params: query_params.remove("game_id")
            st.session_state.game_id = None
    else: st.session_state.game_id = None
default_state_keys = {"game_started": False, "players": [], "pending_players": [], "current_holder": None,
    "game_end_time": None, "history": [], "oldest_ticket_days_to_beat": 0, "game_id": None}
for k, dv in default_state_keys.items():
    if k not in st.session_state: st.session_state[k] = dv

# ---------- Game Setup UI (no changes) ----------
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
    gd_label = st.selectbox("Game duration:",options=list(DEFAULT_GAME_DURATIONS.keys()),index=2)
    if len(st.session_state.pending_players) < 2: st.info("Add at least 2 players.")
    else:
        if st.button("✅ Start Game",type="primary",use_container_width=True):
            if not st.session_state.game_id: st.session_state.game_id=generate_game_id(); query_params["game_id"]=st.session_state.game_id
            st.session_state.players=list(st.session_state.pending_players); st.session_state.pending_players=[]
            st.session_state.current_holder=random.choice(st.session_state.players)
            st.session_state.game_end_time=datetime.now()+DEFAULT_GAME_DURATIONS[gd_label]
            st.session_state.history=[]; st.session_state.oldest_ticket_days_to_beat=0
            st.session_state.game_started=True; st.session_state.game_loaded_from_backend=True
            save_game_state_to_backend(st.session_state.game_id,st.session_state)
            st.balloons(); st.rerun()

# ---------- Game Interface UI ----------
if st.session_state.game_started:
    now = datetime.now()
    time_left_game = (st.session_state.game_end_time - now) if isinstance(st.session_state.game_end_time, datetime) else timedelta(seconds=0)

    if time_left_game.total_seconds() <= 0: # Game Over
        st.error(f"🏁 **GAME OVER!** 🏁"); st.subheader(f"Final bomb holder: **{st.session_state.current_holder}**")
        st.warning(f"**{st.session_state.current_holder}** buys Matcha Lattes! 🍵"); st.balloons()
        save_game_state_to_backend(st.session_state.game_id, st.session_state)
    else: # Gameplay Active
        st.subheader(f"💣 Bomb held by: {st.session_state.current_holder}")
        st.metric("Game Ends In:", format_timedelta(time_left_game)); st.markdown("---")
        st.subheader("↪️ Pass the Bomb")
        pass_msg = f"To pass, log ticket > {st.session_state.oldest_ticket_days_to_beat} days old."
        if st.session_state.oldest_ticket_days_to_beat == 0: pass_msg += " (Any age for 1st pass.)"
        st.markdown(pass_msg)
        can_pass = False; pass_to_options = []
        if st.session_state.current_holder and st.session_state.current_holder in st.session_state.players and \
           isinstance(st.session_state.players, list) and len(st.session_state.players) >= 2:
             pass_to_options = [p for p in st.session_state.players if p != st.session_state.current_holder]
             if pass_to_options: can_pass = True
        if not can_pass: st.error("Cannot pass bomb: No valid players to pass to.")
        else:
            # --- MODIFICATION: Dynamic form key ---
            # The form_key is now unique based on the number of passes made + current holder
            # This forces Streamlit to treat it as a new form instance after each pass.
            current_turn_identifier = len(st.session_state.get("history", []))
            dynamic_form_key = f"pass_form_turn_{current_turn_identifier}_{st.session_state.current_holder}"
            with st.form(dynamic_form_key):
            # --- END MODIFICATION ---
                st.markdown(f"You are: **{st.session_state.current_holder}** (current bomb holder)")
                next_player = st.selectbox("Pass bomb to:", pass_to_options, index=0)
                ticket_number = st.text_input("Ticket Number/ID:", placeholder="e.g. JIRA-123")
                d_val = datetime.now().date() - timedelta(days=max(0, int(st.session_state.oldest_ticket_days_to_beat)) + 1)
                ticket_date = st.date_input("Ticket creation date:", max_value=datetime.now().date(), value=d_val)
                
                # Using the most basic submit button call
                submit_pass_button_pressed = st.form_submit_button("Pass This Bomb!")

                if submit_pass_button_pressed:
                    if not ticket_number.strip(): st.warning("⚠️ Enter ticket number.")
                    else:
                        days_old = (datetime.now().date() - ticket_date).days
                        if days_old < 0: st.error("Ticket date cannot be future!")
                        elif days_old <= st.session_state.oldest_ticket_days_to_beat and st.session_state.oldest_ticket_days_to_beat != 0:
                            st.error(f"❌ Pass Failed! Ticket {days_old}d old. Need > {st.session_state.oldest_ticket_days_to_beat}d.")
                        else:
                            st.session_state.history.append({
                                "from": st.session_state.current_holder, "to": next_player,
                                "ticket": ticket_number, "days_old": days_old, "time": now
                            })
                            st.session_state.current_holder = next_player
                            st.session_state.oldest_ticket_days_to_beat = max(st.session_state.oldest_ticket_days_to_beat, days_old)
                            st.success(f"🎉 Bomb Passed to {next_player}! Ticket: {days_old}d old.")
                            save_game_state_to_backend(st.session_state.game_id, st.session_state)
                            st.rerun() # Rerun to reflect the pass and new form key
                            
    st.markdown("---"); st.subheader("📊 Game Stats & History")
    with st.expander("📜 Bomb Pass History", expanded=True):
        if not st.session_state.history: st.caption("_No passes yet._")
        else:
            for r in reversed(st.session_state.history):
                t_val=r.get('time');t_str=t_val.strftime('%Y-%m-%d %H:%M:%S') if isinstance(t_val,datetime) else str(t_val)
                st.markdown(f"-`{r.get('from','?')}`➡️`{r.get('to','?')}`(Tkt:`{r.get('ticket','?')}`–**{r.get('days_old','?')}d old**) at {t_str}")

# ---------- Sidebar Controls (no changes) ----------
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
            st.session_state.game_end_time=datetime.now(); save_game_state_to_backend(st.session_state.game_id,st.session_state); st.rerun()
    if st.button("🔄 Start New Setup / Restart App",type="primary"):
        current_q_params=st.query_params.to_dict()
        if "game_id" in current_q_params: del current_q_params["game_id"]; st.query_params.from_dict(current_q_params)
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.toast("App reset.",icon="🧹"); st.rerun()

# ---------- Footer (no changes) ----------
st.markdown("<br><hr><center><sub>Made for ASMPT · Powered by Streamlit & Matcha</sub></center>", unsafe_allow_html=True)

# ---------- Live Timer Update (Still commented out for debugging) ----------
# if st.session_state.get("game_started", False) and isinstance(st.session_state.get("game_end_time"), datetime):
#     if st.session_state.game_end_time > datetime.now():
#         time.sleep(1)
#         st.rerun()
