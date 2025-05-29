import streamlit as st
from datetime import datetime, timedelta

# ---------- Page Config ----------
st.set_page_config(page_title="Pass the Bomb", layout="centered")

# ---------- Logo ----------
st.image("asmpt_logo.png", width=200)  # Upload this to your repo alongside this .py file

# ---------- Title & Tagline ----------
st.title("💣 Pass the Bomb - ASMPT Edition")
st.markdown("### _Don't be the one who has to buy the Matcha Lattes... close the oldest ticket to pass the bomb!_")

# ---------- Initialise Session State ----------
if "game_started" not in st.session_state:
    st.session_state.game_started = False
    st.session_state.players = []
    st.session_state.pending_players = []
    st.session_state.current_holder = None
    st.session_state.bomb_timer = None
    st.session_state.game_end = None
    st.session_state.history = []

# ---------- Game Setup ----------
if not st.session_state.game_started:
    st.subheader("🎮 Start a New Game")

    with st.form("add_players_form"):
        name = st.text_input("Enter player name")
        add = st.form_submit_button("➕ Add Player")
        if add and name.strip():
            st.session_state.pending_players.append(name.strip())

    if st.session_state.pending_players:
        st.markdown("**Players Added:**")
        for player in st.session_state.pending_players:
            st.markdown(f"- {player}")

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
            st.session_state.bomb_timer = datetime.now() + timede
