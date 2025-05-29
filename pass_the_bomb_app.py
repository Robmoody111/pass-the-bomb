# pass_the_bomb_app.py

import streamlit as st
from datetime import datetime, timedelta

# ---------- Logo & Title ----------
st.set_page_config(page_title="Pass the Bomb", layout="centered")
st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/f/f6/ASMPT_Logo.svg/2560px-ASMPT_Logo.svg.png", width=250)
st.title("💣 Pass the Bomb - ASMPT Edition")

# ---------- Initialize Game State ----------
if "state" not in st.session_state:
    st.session_state.state = {
        "players": [],
        "current_holder": None,
        "bomb_timer": None,
        "history": [],
        "active": False
    }

state = st.session_state.state

# ---------- Game Setup ----------
if not state["active"]:
    st.subheader("🎮 Start a New Game")
    player_names = st.text_area("Enter player names (one per line)").strip().splitlines()
    start_game = st.button("Start Game")

    if start_game and player_names:
        state["players"] = player_names
        state["current_holder"] = player_names[0]
        state["bomb_timer"] = datetime.now() + timedelta(seconds=60)
        state["history"] = []
        state["active"] = True
        st.success(f"Game started! {player_names[0]} holds the bomb first.")
    elif start_game:
        st.warning("Please enter at least one player.")
    st.stop()

# ---------- Bomb Status ----------
time_left = int((state["bomb_timer"] - datetime.now()).total_seconds())

if time_left <= 0:
    state["active"] = False
    st.error(f"💥 BOOM! The bomb exploded in {state['current_holder']}'s hands!")
    st.button("🔁 Restart Game", on_click=lambda: st.session_state.clear())
    st.stop()
else:
    st.info(f"💣 Held by: `{state['current_holder']}` – ⏱ `{time_left}` seconds left")

# ---------- Bomb Passing ----------
st.subheader("Pass the Bomb")

with st.form("pass_form"):
    your_name = st.selectbox("Who are you?", state["players"])
    next_player = st.selectbox("Who do you want to pass the bomb to?", [p for p in state["players"] if p != your_name])
    ticket_number = st.text_input("Enter a closed ticket number to pass the bomb")
    submit = st.form_submit_button("Pass it!")

    def is_ticket_closed(ticket_number):
        # Mock: any ticket ending in even number is "closed"
        return ticket_number.isdigit() and int(ticket_number[-1]) % 2 == 0

    if submit:
        if your_name != state["current_holder"]:
            st.warning("You don't have the bomb!")
        elif not is_ticket_closed(ticket_number):
            st.error("❌ Ticket is invalid or not closed.")
        else:
            state["history"].append({
                "from": your_name,
                "to": next_player,
                "ticket": ticket_number,
                "time": datetime.now().isoformat()
            })
            state["current_holder"] = next_player
            state["bomb_timer"] = datetime.now() + timedelta(seconds=60)
            st.success(f"Bomb passed to {next_player}!")

# ---------- History ----------
with st.expander("📜 View Bomb Pass History"):
    for record in reversed(state["history"]):
        st.markdown(f"- `{record['from']}` ➡️ `{record['to']}` (Ticket: {record['ticket']})")

# ---------- Footer ----------
st.markdown("<br><center><sub>Made for ASMPT · Powered by Streamlit</sub></center>", unsafe_allow_html=True)
