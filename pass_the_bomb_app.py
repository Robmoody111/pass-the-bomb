# pass_the_bomb_app.py

import streamlit as st
from datetime import datetime, timedelta

# ---------- Logo & Title ----------
st.set_page_config(page_title="Pass the Bomb", layout="centered")
st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/3/33/ASMPT_Logo_2023.svg/2560px-ASMPT_Logo_2023.svg.png", width=200)
st.title("💣 Pass the Bomb - ASMPT Edition")
st.markdown("### _Don't be the one who has to buy the Matcha Lattes... close the oldest ticket to pass the bomb!_")

# ---------- Initialize Game State ----------
if "state" not in st.session_state:
    st.session_state.state = {
        "players": [],
        "current_holder": None,
        "bomb_timer": None,
        "history": [],
        "active": False,
        "game_end": None
    }

state = st.session_state.state

# ---------- Game Setup ----------
if not state["active"]:
    st.subheader("🎮 Start a New Game")

    player_names = st.text_area("Enter player names (one per line)").strip().splitlines()

    game_duration = st.selectbox("Select game duration:", ["1 day", "1 week", "1 month"])
    start_game = st.button("Start Game")

    if start_game and player_names:
        duration_map = {
            "1 day": timedelta(days=1),
            "1 week": timedelta(weeks=1),
            "1 month": timedelta(days=30)
        }
        state["players"] = player_names
        state["current_holder"] = player_names[0]
        state["bomb_timer"] = datetime.now() + timedelta(seconds=60)
        state["game_end"] = datetime.now() + duration_map[game_duration]
        state["history"] = []
        state["active"] = True
        st.success(f"Game started! {player_names[0]} holds the bomb first.")
    elif start_game:
        st.warning("Please enter at least one player.")
    st.stop()

# ---------- Game Countdown ----------
time_left = int((state["bomb_timer"] - datetime.now()).total_seconds())
overall_time_left = state["game_end"] - datetime.now()
if overall_time_left.total_seconds() <= 0:
    state["active"] = False
    st.error("🏁 The game is over! Final bomb holder: " + state["current_holder"])
    st.button("🔁 Restart Game", on_click=lambda: st.session_state.clear())
    st.stop()
else:
    st.markdown(f"⏳ **Game ends in:** `{str(overall_time_left).split('.')[0]}`")

if time_left <= 0:
    state["active"] = False
    st.error(f"💥 BOOM! The bomb exploded in {state['current_holder']}'s hands!")
    st.button("🔁 Restart Game", on_click=lambda: st.session_state.clear())
    st.stop()
else:
    st.info(f"💣 Held by: `{state['current_holder']}` – ⏱ `{time_left}` seconds left to pass it")

# ---------- Bomb Passing ----------
st.subheader("Pass the Bomb")

with st.form("pass_form"):
    your_name = st.selectbox("Who are you?", state["players"])
    next_player = st.selectbox("Who do you want to pass the bomb to?", [p for p in state["players"] if p != your_name])
    ticket_number = st.text_input("Enter any ticket number (for fun!) to pass the bomb")
    ticket_date = st.date_input("What date was the ticket created?", max_value=datetime.now().date())
    submit = st.form_submit_button("Pass it!")

    def is_ticket_closed(ticket_number):
        return True  # All ticket numbers are valid in this version

    if submit:
        if your_name != state["current_holder"]:
            st.warning("You don't have the bomb!")
        elif not is_ticket_closed(ticket_number):
            st.error("❌ Something went wrong. (This shouldn't happen!)")
        else:
            days_old = (datetime.now().date() - ticket_date).days
            state["history"].append({
                "from": your_name,
                "to": next_player,
                "ticket": ticket_number,
                "days_old": days_old,
                "time": datetime.now().isoformat()
            })
            state["current_holder"] = next_player
            state["bomb_timer"] = datetime.now() + timedelta(seconds=60)
            st.success(f"🎉 Congratulations! You are closing a ticket that's **{days_old} days old**.")
            st.info(f"💣 It's now **{next_player}**'s turn!")

# ---------- History ----------
with st.expander("📜 View Bomb Pass History"):
    for record in reversed(state["history"]):
        st.markdown(
            f"- `{record['from']}` ➡️ `{record['to']}` "
            f"(Ticket: `{record['ticket']}` – {record['days_old']} days old)"
        )

# ---------- Footer ----------
st.markdown("<br><center><sub>Made for ASMPT · Powered by Streamlit</sub></center>", unsafe_allow_html=True)
