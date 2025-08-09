import streamlit as st
import json
import os
import glob

from utils import log_manager
import pandas as pd

# Load interaction graph (cached every 5 minutes)
@st.cache_data(ttl=300)
def load_interaction_graph(path='data/historic_stats/interaction_graph.json'):
    abs_path = os.path.join(os.path.dirname(__file__), path)
    with open(abs_path, 'r') as f:
        return json.load(f)
    
@st.cache_data(ttl=300)
def load_daily_graph(date_str):
    path = f"data/daily/{date_str}.json"
    abs_path = os.path.join(os.path.dirname(__file__), path)
    with open(abs_path, 'r') as f:
        daily_data = json.load(f)
    return daily_data["interactions"], daily_data["winner"]

def get_available_dates():
    pattern = os.path.join(os.path.dirname(__file__), "data/daily/*.json")
    files = glob.glob(pattern)
    # Extract just YYYY-MM-DD from filenames
    return sorted([os.path.splitext(os.path.basename(f))[0] for f in files], reverse=True)


def get_wins(available_dates, player):
    wins = 0
    for date in available_dates:
        _, winner = load_daily_graph(date)
        if player == winner:
            wins += 1
    return wins

st.title("⚔️fIGth club: fight or unfollow") 

available_dates = get_available_dates()
date_options = ["All Time"] + available_dates
selected_date = st.sidebar.selectbox("Select Date", date_options)

# Load correct data
if selected_date == "All Time":
    data = load_interaction_graph()
else:
    data, winner = load_daily_graph(selected_date)

if selected_date == "All Time":
    stat_options = {
        "Wins": lambda p: get_wins(available_dates, p),
        "Kills": lambda p: log_manager.get_kills(data, p),
        "Deaths": lambda p: log_manager.get_deaths(data, p),
        "Damage Dealt": lambda p: log_manager.get_damage_dealt(data, p),
        "Damage Received": lambda p: log_manager.get_damage_received(data, p),
    }
else:
    stat_options = {
        "Winner": winner,
        "Kills": lambda p: log_manager.get_kills(data, p),
        "Damage Dealt": lambda p: log_manager.get_damage_dealt(data, p),
    }

selected_stat = st.sidebar.selectbox("Leaderboard Stat", list(stat_options.keys()))

tab1, tab2 = st.tabs(["🏆 Leaderboard", "📊 Player Stats"])

players = sorted(data.keys())
if "selected_player" not in st.session_state:
    st.session_state.selected_player = players[0]

if st.session_state.selected_player not in players:
    st.sidebar.warning(f"No data for **{st.session_state.selected_player}** on {selected_date}")

selected_player = st.sidebar.selectbox(
    "Select a player",
    players,
    index=players.index(st.session_state.selected_player) if st.session_state.selected_player in players else 0,
    key="selected_player"
)

with tab1:
    st.header(f"🏆 Leaderboard (Top by {selected_stat}) — {selected_date}")

    # If not All Time and stat is Winner, show simple text
    if selected_date != "All Time" and selected_stat == "Winner":
        st.markdown(f"🏅 The winner for {selected_date} is **[{winner}](https://instagram.com/{winner})**!")
    else:
        leaderboard_data = {
            "Player": players,
            selected_stat: [stat_options[selected_stat](p) for p in players]
        }
        leaderboard_df = pd.DataFrame(leaderboard_data)
        leaderboard_df = leaderboard_df.sort_values(by=selected_stat, ascending=False).reset_index(drop=True)

        st.dataframe(
            leaderboard_df.head(10),
            use_container_width=True,
            hide_index=True
        )

with tab2:
    def get_instagram_link(player):
        # Replace with your logic to get Instagram username
        return f"https://instagram.com/{player}"

    st.header(f"📊 Stats for [{selected_player}](https://instagram.com/{selected_player})")
    col1, col2 = st.columns(2)
    col1.metric("💥 Damage Dealt", f"{log_manager.get_damage_dealt(data, selected_player):.2f}")
    col1.metric("🔪 Kills", log_manager.get_kills(data, selected_player))
    col2.metric("🩸 Damage Received", f"{log_manager.get_damage_received(data, selected_player):.2f}")
    col2.metric("☠️ Deaths", log_manager.get_deaths(data, selected_player))

    # Nemesis and Victim calculation
    interactions = data[selected_player]
    nemesis = log_manager.get_nemesis(data, selected_player)
    victim = log_manager.get_victim(data, selected_player)

    col_nemesis, col_victim = st.columns(2)
    with col_nemesis:
        st.markdown("### Nemesis")
        if nemesis and data[nemesis][selected_player]['kills'] > 0:
            kills = data[nemesis][selected_player]['kills']
            times_str = "time" if kills == 1 else "times"
            st.markdown(f"[{nemesis}]({get_instagram_link(nemesis)}) - Killed you {kills} {times_str}")
        else:
            st.write("No nemesis found.")

    with col_victim:
        st.markdown("### Victim")
        if victim and interactions[victim]['kills'] > 0:
            kills = interactions[victim]['kills']
            times_str = "time" if kills == 1 else "times"
            st.markdown(f"[{victim}]({get_instagram_link(victim)}) - You killed them {kills} {times_str}")
        else:
            st.write("No victim found.")
    
    ## Interaction graph
    # st.markdown("### Interaction Graph")