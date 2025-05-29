import streamlit as st
from datetime import datetime, timedelta
import random
import json
import os
import time # For the live countdown (currently commented out)

# ---------- App Constants & Configuration ----------
APP_VERSION = "3.5 Simplified Pass Rule" # <<<<<<< Updated Version
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
        # oldest_ticket_days_to_beat will naturally be excluded if not in state_dict
        elif k not in ["new_player_name_input", "oldest_ticket_days_to_beat"] and \
             not k.startswith("remove_player_") and not k.startswith("rm_p_"):
            s_state[k] = v
    return s_state
def _deserialize_state(json_data):
    d_state = json_data.copy()
    for k, v in json_data.items():
        if isinstance(v, str):
            try: d_state[k] = datetime.fromisoformat(v); continue
            except (TypeError, ValueError): pass
        if k == "history" and isinstance(v, list):
