import streamlit as st
import sqlite3
import pandas as pd
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data/daily_stats.db")

# ========= DB HELPERS ========= #

def get_conn():
    return sqlite3.connect(DB_PATH)

@st.cache_data(ttl=300)
def get_available_dates():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT date FROM daily_summary ORDER BY date DESC")
    dates = [r[0] for r in cursor.fetchall()]
    conn.close()
    return ["All Time"] + dates 

@st.cache_data(ttl=300)
def get_daily_summary(date_str):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT num_players, winner FROM daily_summary WHERE date = ?", (date_str,))
    row = cursor.fetchone()
    conn.close()
    return {"num_players": row[0], "winner": row[1]} if row else None

@st.cache_data(ttl=300)
def get_players(date_str):
    conn = get_conn()
    cursor = conn.cursor()
    if date_str == "All Time":
        cursor.execute("SELECT DISTINCT player FROM player_stats ORDER BY player ASC")
    else:
        cursor.execute("SELECT player FROM player_stats WHERE date = ? ORDER BY player ASC", (date_str,))
    players = [r[0] for r in cursor.fetchall()]
    conn.close()
    return players


@st.cache_data(ttl=300)
def get_top_players(date_str, stat="kills", limit=10):
    conn = get_conn()
    cursor = conn.cursor()

    if date_str == "All Time":
        cursor.execute(f"""
            SELECT player, SUM({stat}) as total_{stat}
            FROM player_stats
            GROUP BY player
            ORDER BY total_{stat} DESC
            LIMIT ?
        """, (limit,))
      
    else:
        cursor.execute(f"""
            SELECT player, {stat}
            FROM player_stats
            WHERE date = ?
            ORDER BY {stat} DESC
            LIMIT ?
        """, (date_str, limit))
    rows = cursor.fetchall()
    conn.close()
    return pd.DataFrame(rows, columns=["Player", stat.capitalize()])


@st.cache_data(ttl=300)
def get_player_stats(date_str, player):
    conn = get_conn()
    cursor = conn.cursor()
    if date_str == "All Time":
        cursor.execute("""
            SELECT 
                SUM(kills), SUM(deaths),
                SUM(damage_dealt), SUM(damage_received),
                NULL, NULL
            FROM player_stats
            WHERE player = ?
        """, (player,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "kills": row[0] or 0,
                "deaths": row[1] or 0,
                "damage_dealt": row[2] or 0.0,
                "damage_received": row[3] or 0.0,
                "nemesis": None,
                "victim": None,
            }
        return None
    else:
        cursor.execute("""
            SELECT kills, deaths, damage_dealt, damage_received, nemesis, victim
            FROM player_stats
            WHERE date = ? AND player = ?
        """, (date_str, player))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "kills": row[0],
                "deaths": row[1],
                "damage_dealt": row[2],
                "damage_received": row[3],
                "nemesis": row[4],
                "victim": row[5],
            }
        return None

@st.cache_data(ttl=300)
def get_player_rank(date_str, player):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT rank FROM ranking WHERE date = ? AND player = ?
    """, (date_str, player))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

@st.cache_data(ttl=300)
def get_all_winners():
    """Return all winners per day."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT date, winner FROM daily_summary ORDER BY date DESC")
    rows = cursor.fetchall()
    conn.close()
    return pd.DataFrame(rows, columns=["Date", "Winner"])


@st.cache_data(ttl=300)
def get_wins(date_str, player):
    """Return how many wins a player has (all-time or specific date)."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM daily_summary WHERE winner = ?", (player,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ========= APP ========= #

st.title("⚔️ fIGth club: fight or unfollow")

# Dates
available_dates = get_available_dates()
if not available_dates:
    st.error("No data available in database.")
    st.stop()

selected_date = st.sidebar.selectbox("Select Date", available_dates)

# Players
players = get_players(selected_date)
if not players:
    st.warning(f"No players found for {selected_date}")
    st.stop()

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
    st.header(f"🏆 Leaderboard — {selected_date}")
    if selected_date == "All Time":
        stat_choice = st.sidebar.radio("Leaderboard Stat", ["kills", "damage_dealt", "winners"])
    else:
        stat_choice = st.sidebar.radio("Leaderboard Stat", ["kills", "damage_dealt"])
    if stat_choice == "winners":
        top_df = get_all_winners()
    else:
        top_df = get_top_players(selected_date, stat_choice, limit=10)
    st.dataframe(top_df, use_container_width=True, hide_index=True)

    # Show winner
    summary = get_daily_summary(selected_date)
    if summary:
        st.markdown(f"🏅 The winner for {selected_date} is **[{summary['winner']}](https://instagram.com/{summary['winner']})**!")

with tab2:
    st.header(f"📊 Stats for [{selected_player}](https://instagram.com/{selected_player})")

    stats = get_player_stats(selected_date, selected_player)
    wins = get_wins(selected_date, selected_player)
    if not stats:
        st.write("No stats available for this player.")
    else:
        cols = st.columns(2)
        with cols[0]:
            st.metric("💥 Damage Dealt", f"{stats['damage_dealt']:.2f}")
            st.metric("🔪 Kills", stats["kills"])
        with cols[1]:
            st.metric("🩸 Damage Received", f"{stats['damage_received']:.2f}")
            st.metric("☠️ Deaths", stats["deaths"])
        if selected_date == "All Time":
            st.metric("🏅 Wins", wins)
        else:
            # Ranking
            rank = get_player_rank(selected_date, selected_player)
            if rank == 0:
                st.metric("Ranking", "👑 WINNER! The arena bows to your unmatched skill!")
            elif rank is not None:
                st.metric("Ranking", rank)

        # Nemesis and Victim
        if selected_date == "All Time":
            col_nemesis, col_victim = st.columns(2)
            with col_nemesis:
                st.markdown("### Nemesis")
                if stats["nemesis"]:
                    st.markdown(f"[{stats['nemesis']}](https://instagram.com/{stats['nemesis']})")
                else:
                    st.write("No nemesis found.")

            with col_victim:
                st.markdown("### Victim")
                if stats["victim"]:
                    st.markdown(f"[{stats['victim']}](https://instagram.com/{stats['victim']})")
                else:
                    st.write("No victim found.")