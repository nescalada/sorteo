import streamlit as st
import json
import os
import glob
import pandas as pd
from utils import log_manager

# ========= BULK DATA LOADERS ========= #

@st.cache_data(ttl=300)
def load_interaction_graph():
    """Load the All Time interaction graph."""
    abs_path = os.path.join(os.path.dirname(__file__), 'data/historic_stats/interaction_graph.json')
    with open(abs_path, 'r') as f:
        return json.load(f)

@st.cache_data(ttl=300)
def load_all_daily_graphs():
    """Load all daily interaction files into a single dict."""
    base_dir = os.path.dirname(__file__)
    daily_pattern = os.path.join(base_dir, "data/daily/*.json")
    ranking_pattern = os.path.join(base_dir, "data/daily/ranking/*.json")

    # Load interaction files
    all_graphs = {}
    for path in glob.glob(daily_pattern):
        date_str = os.path.splitext(os.path.basename(path))[0]
        with open(path, 'r') as f:
            daily_data = json.load(f)
        all_graphs[date_str] = {
            "interactions": daily_data["interactions"],
            "winner": daily_data["winner"]
        }

    # Load ranking files
    all_rankings = {}
    for path in glob.glob(ranking_pattern):
        date_str = os.path.basename(path).replace("_ranking.json", "")
        with open(path, 'r') as f:
            all_rankings[date_str] = json.load(f)

    return all_graphs, all_rankings

@st.cache_data(ttl=300)
def precompute_all_wins(all_graphs):
    """Count wins for all players in all dates."""
    wins = {}
    for date, data in all_graphs.items():
        winner = data["winner"]
        wins[winner] = wins.get(winner, 0) + 1
    return wins

# ========= UTILITY ========= #

def get_available_dates(all_graphs):
    return sorted(all_graphs.keys(), reverse=True)

# ========= APP ========= #

st.title("⚔️ fIGth club: fight or unfollow")

# Bulk load
all_graphs, all_rankings = load_all_daily_graphs()
available_dates = get_available_dates(all_graphs)

# Sidebar
date_options = ["All Time"] + available_dates
selected_date = st.sidebar.selectbox("Select Date", date_options)

# Load appropriate dataset
if selected_date == "All Time":
    data = load_interaction_graph()
    wins_dict = precompute_all_wins(all_graphs)
    stat_options = {
        "Wins": lambda p: wins_dict.get(p, 0),
        "Kills": lambda p: log_manager.get_kills(data, p),
        "Deaths": lambda p: log_manager.get_deaths(data, p),
        "Damage Dealt": lambda p: log_manager.get_damage_dealt(data, p),
    }
else:
    data = all_graphs[selected_date]["interactions"]
    winner = all_graphs[selected_date]["winner"]
    ranking = all_rankings.get(selected_date, {})
    stat_options = {
        "Winner": winner,
        "Kills": lambda p: log_manager.get_kills(data, p),
        "Damage Dealt": lambda p: log_manager.get_damage_dealt(data, p),
    }

selected_stat = st.sidebar.selectbox("Leaderboard Stat", list(stat_options.keys()))

# Player selector
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

# Tabs
tab1, tab2 = st.tabs(["🏆 Leaderboard", "📊 Player Stats"])

with tab1:
    st.header(f"🏆 Leaderboard (Top by {selected_stat}) — {selected_date}")

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
        return f"https://instagram.com/{player}"

    st.header(f"📊 Stats for [{selected_player}](https://instagram.com/{selected_player})")

    cols = st.columns(2)
    with cols[0]:
        st.metric("💥 Damage Dealt", f"{log_manager.get_damage_dealt(data, selected_player):.2f}")
        st.metric("🔪 Kills", log_manager.get_kills(data, selected_player))
    with cols[1]:
        st.metric("🩸 Damage Received", f"{log_manager.get_damage_received(data, selected_player):.2f}")
        st.metric("☠️ Deaths", log_manager.get_deaths(data, selected_player))

    if selected_date == "All Time":
        st.metric("🏅 Wins", wins_dict.get(selected_player, 0))
    else:
        rank_player = ranking.get(selected_player)
        if rank_player == 0:
            st.metric("Ranking", "👑 WINNER! The arena bows to your unmatched skill!")
        else:
            st.metric("Ranking", rank_player)

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