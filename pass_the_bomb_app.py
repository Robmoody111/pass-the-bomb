# pass_the_bomb_app.py

import streamlit as st
from datetime import datetime, timedelta

# Game state storage (temporary, resets on app reload)
if "state" not in st.session_state:
    st.session_state.state = {
        "current_holder": "alice@example.com",
        "players": ["alice@example.com", "bob@example.com", "carol@example.com"],
        "bomb_timer": datetime.now() + timedelta(seconds=60),
        "history": [],
        "active": True
    }

def check_ticket_closed(ticket_number):
    # Placeholder logic: treat any number ending in even digit as "closed"
    return ticket_number.isdigit() and int(ticket_number[-1]) % 2 == 0

st.title("💣 Pass the Bomb Game")

# Show current bomb status
state = st.session_state.state
time_left = int((state["bomb_timer"] - datetime.now()).total_seconds())

if time_left <= 0:
    state["active"] = False
    st.error(f"💥 BOOM! The bomb exploded in {state['current_holder']}'s hands!")
else:
    st.info(f"⏱️ Held by: {state['current_holder']} – {time_left} seconds left")

# Form to pass the bomb
if state["active"]:
    with st.form("pass_form"):
        from_player = st.selectbox("Who are you?", state["players"])
        to_player = st.selectbox("Pass the bomb to:", [p for p in state["players"] if p != from_player])
        ticket_number = st.text_input("Closed Ticket Number")
        submitted = st.form_submit_button("Pass the Bomb")

        if submitted:
            if from_player != state["current_holder"]:
                st.warning("You don't hold the bomb!")
            elif not check_ticket_closed(ticket_number):
                st.warning("Ticket is not valid or not closed!")
            else:
                state["history"].append({
                    "from": from_player,
                    "to": to_player,
                    "ticket": ticket_number,
                    "time": datetime.now().isoformat()
                })
                state["current_holder"] = to_player
                state["bomb_timer"] = datetime.now() + timedelta(seconds=60)
                st.success(f"💣 Bomb passed to {to_player}!")

# Show history
if st.checkbox("Show bomb pass history"):
    st.write(state["history"])
