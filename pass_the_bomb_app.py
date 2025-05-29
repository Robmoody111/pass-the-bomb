# pass_the_bomb_app.py

import streamlit as st
from datetime import datetime, timedelta

# ---------- Config ----------
st.set_page_config(page_title="Pass the Bomb", layout="centered")

# ---------- Logo ----------
st.image("asmpt_logo.png", width=200)  # Upload this to your repo

# ---------- Title & Tagline ----------
st.title("💣 Pass the Bomb - ASMPT Edition")
st.markdown("### _Don't be the one who has to buy the Matcha Lattes... close the oldest ticket to pass the bomb!_")

# ---------- State ----------
if "game_started" not in st.session_state:
    st.session_state.game_started = False
    st.session_state.players = []
    st.session_state.current_holder = None
    st.session_state.bomb_timer = None
    st.session_state.game_end = None
    st.session_state.history = []
    st.session_state.name_input = ""
    st.session_state.pending_players = []

# ---------- Game Setup ----------
if not st.session_state.game_started:

    st.subheader("🎮 Start a New Game")

    name = st.text_input("Enter player name")
if st.button("➕ Add Player"):
    if name.strip():
        st.session_state.pending_players.append(name.strip())
        st.rerun()

    if st.session_state.pending_players:
        st.markdown("**Players Added:**")
        for p in st.session_state.pending_players:
            st.markdown(f"- {p}")

    game_duration = st.selectbox("Select game duration:", ["1 day", "1 week", "1 month"])

    if len(st.session_state.pending_players) < 2:
        st.info("Add at least **2 players** to start the game.")
    else:
        if st.button("✅ Start Game"):
            duration_map = {
                "1 day": timedelta(days=1),
                "1 week": timedelta(weeks=1),
                "1 month": timedelta(days=30)
            }
            st.session_state.players = st.session_state.pending_players
            st.session_state.current_holder = st.session_state.players[0]
            st.session_state.bomb_timer = datetime.now() + timedelta(seconds=60)
            st.session_state.game_end = datetime.now() + duration_map[game_duration]
            st.session_state.history = []
            st.session_state.game_started = True
            st.experimental_rerun()

# ---------- Game Interface ----------
if st.session_state.game_started:

    # Time Remaining
    time_left = int((st.session_state.bomb_timer - datetime.now()).total_seconds())
    game_left = st.session_state.game_end - datetime.now()

    if game_left.total_seconds() <= 0:
        st.error("🏁 The game is over! Final bomb holder: " + st.session_state.current_holder)
        if st.button("🔁 Restart Game"):
            st.session_state.clear()
    elif time_left <= 0:
        st.error(f"💥 BOOM! The bomb exploded in {st.session_state.current_holder}'s hands!")
        if st.button("🔁 Restart Game"):
            st.session_state.clear()
    else:
        st.markdown(f"⏳ **Game ends in:** `{str(game_left).split('.')[0]}`")
        st.info(f"💣 Held by: `{st.session_state.current_holder}` – ⏱ `{time_left}` seconds left to pass it")

        # Bomb Passing
        st.subheader("Pass the Bomb")
        with st.form("pass_form"):
            your_name = st.selectbox("Who are you?", st.session_state.players)
            next_player = st.selectbox("Pass the bomb to:", [p for p in st.session_state.players if p != your_name])
            ticket_number = st.text_input("Enter any ticket number (for fun!) to pass the bomb")
            ticket_date = st.date_input("What date was the ticket created?", max_value=datetime.now().date())
            submit = st.form_submit_button("Pass it!")

            if submit:
                if your_name != st.session_state.current_holder:
                    st.warning("You don't have the bomb!")
                else:
                    days_old = (datetime.now().date() - ticket_date).days
                    st.session_state.history.append({
                        "from": your_name,
                        "to": next_player,
                        "ticket": ticket_number,
                        "days_old": days_old,
                        "time": datetime.now().isoformat()
                    })
                    st.session_state.current_holder = next_player
                    st.session_state.bomb_timer = datetime.now() + timedelta(seconds=60)
                    st.success(f"🎉 Congrats! That ticket was **{days_old} days old**.")
                    st.info(f"💣 It's now **{next_player}**'s turn!")

        # History
        with st.expander("📜 Bomb Pass History"):
            for record in reversed(st.session_state.history):
                st.markdown(
                    f"- `{record['from']}` ➡️ `{record['to']}` "
                    f"(Ticket: `{record['ticket']}` – {record['days_old']} days old)"
                )

# ---------- Footer ----------
st.markdown("<br><center><sub>Made for ASMPT · Powered by Streamlit</sub></center>", unsafe_allow_html=True)
