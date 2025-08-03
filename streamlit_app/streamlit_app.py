import streamlit as st
import json

import os

# Load interaction graph (cached)
@st.cache_data
def load_interaction_graph(path='../data/historic_stats/interaction_graph.json'):
    abs_path = os.path.join(os.path.dirname(__file__), path)
    with open(abs_path, 'r') as f:
        return json.load(f)

data = load_interaction_graph()

# Sidebar: select player
players = sorted(data.keys())
selected_player = st.sidebar.selectbox("Select a player", players)

# Utility functions
def get_damage_dealt(graph, player):
    return sum(stats['dmg_dealt'] for stats in graph.get(player, {}).values())

def get_kills(graph, player):
    return sum(stats['kills'] for stats in graph.get(player, {}).values())

def get_damage_received(graph, player):
    return sum(stats.get(player, {}).get('dmg_dealt', 0.0) for stats in graph.values())

def get_deaths(graph, player):
    return sum(stats.get(player, {}).get('kills', 0) for stats in graph.values())

# ---- UI ----
st.title("⚔️ Particle Arena: Daily Battle Stats")

st.header("🏆 Leaderboard (Top Killers)")
leaderboard = sorted(
    [(p, get_kills(data, p)) for p in players],
    key=lambda x: x[1],
    reverse=True
)
st.table(leaderboard[:10])

st.header(f"📊 Stats for: `{selected_player}`")
col1, col2 = st.columns(2)
col1.metric("💥 Damage Dealt", f"{get_damage_dealt(data, selected_player):.2f}")
col1.metric("🔪 Kills", get_kills(data, selected_player))
col2.metric("🩸 Damage Received", f"{get_damage_received(data, selected_player):.2f}")
col2.metric("☠️ Deaths", get_deaths(data, selected_player))

# Optional: show detailed interactions
if st.checkbox("Show interaction details"):
    st.subheader("Interactions")
    for opponent, stats in data[selected_player].items():
        st.write(f"→ vs {opponent}: {stats['dmg_dealt']} dmg, {stats['kills']} kills")