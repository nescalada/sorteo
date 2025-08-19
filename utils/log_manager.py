import os
import csv
import json
import time
import argparse
import sqlite3
from tqdm import tqdm
from collections import defaultdict
from datetime import datetime

DB_PATH = "data/daily_stats.db"
PROCESSED_FILE_PATH = 'data/processed_logs/processed_files.json'

# ========= DB SETUP ========= #
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS player_stats (
        date TEXT,
        player TEXT,
        kills INTEGER,
        deaths INTEGER,
        nemesis TEXT,
        victim TEXT,
        PRIMARY KEY (date, player)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_summary (
        date TEXT PRIMARY KEY,
        num_players INTEGER,
        winner TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ranking (
        date TEXT,
        player TEXT,
        rank INTEGER,
        time NUMERIC(10,2),
        PRIMARY KEY (date, player)
    )
    """)

    conn.commit()
    return conn


# ========= FILE TRACKING ========= #
def load_processed_files():
    if os.path.exists(PROCESSED_FILE_PATH):
        with open(PROCESSED_FILE_PATH, 'r') as f:
            return set(json.load(f))
    return set()

def save_processed_files(filenames):
    dir_path = os.path.dirname(PROCESSED_FILE_PATH)
    os.makedirs(dir_path, exist_ok=True)
    with open(PROCESSED_FILE_PATH, 'w') as f:
        json.dump(list(filenames), f)


# ========= GRAPH HELPERS ========= #
def create_interaction_graph(log_data):
    interaction_graph = defaultdict(lambda: defaultdict(lambda: {'kills': 0}))
    for entry in log_data:
        particle = entry.get('Particle')
        opponent = entry.get('Opponent')
        killed = entry.get('Killed')

        if not (particle and opponent and killed):
            continue

        kill_count = 1 if killed == 'True' else 0

        interaction_graph[opponent][particle]['kills'] += kill_count

    return {p: dict(opp) for p, opp in interaction_graph.items()}

def get_kills(graph, particle):
    return sum(stats['kills'] for stats in graph.get(particle, {}).values())

def get_deaths(graph, particle):
    return sum(stats.get(particle, {}).get('kills', 0) for stats in graph.values())

def get_winner(conn, iso_date):
    cur = conn.cursor()
    cur.execute("SELECT player FROM ranking WHERE date = ? AND rank = 0", (iso_date,))
    row = cur.fetchone()
    return row[0] if row else None


# ========= DB WRITERS ========= #
def save_daily_summary(conn, iso_date, graph):
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM daily_summary WHERE date=?", (iso_date,))
    if cur.fetchone():
        return  # already stored

    summary = {
        "num_players": len(graph),
        "winner": get_winner(conn, iso_date)
    }
    cur.execute("INSERT INTO daily_summary (date, num_players, winner) VALUES (?, ?, ?)",
                (iso_date, summary["num_players"], summary["winner"]))
    conn.commit()


def save_daily_ranking(conn, iso_date, log_data):
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM ranking WHERE date=? LIMIT 1", (iso_date,))
    if cur.fetchone():
        return  # already stored

    ranking = defaultdict(int)
    time_map = {}
    position = 2
    for entry in reversed(log_data):
        particle = entry.get('Particle')
        killed = entry.get('Killed')
        frame = entry.get('Frame', None)

        if ranking[particle] != 0:
            continue
        if particle and killed == 'True':
            ranking[particle] = position
            if frame is not None:
                time_map[particle] = round(float(frame) / 60, 2)
            else:
                time_map[particle] = None
            position += 1

    rows = [
        (iso_date, player, rank, time_map.get(player))
        for player, rank in ranking.items()
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO ranking (date, player, rank, time) VALUES (?, ?, ?, ?)",
        rows
    )
    
    conn.commit()


def save_daily_player_stats(conn, iso_date, graph):
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM player_stats WHERE date=? LIMIT 1", (iso_date,))
    if cur.fetchone():
        return  # already stored

    rows = []
    for player in graph:
        kills = get_kills(graph, player)
        deaths = get_deaths(graph, player)
        nemesis = get_nemesis(graph, player)
        victim = get_victim(graph, player)
        rows.append((
            iso_date,
            player,
            kills,
            deaths,
            nemesis,
            victim,
        ))

    cur.executemany("""
        INSERT OR IGNORE INTO player_stats
        (date, player, kills, deaths, nemesis, victim)
        VALUES (?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()


# ========= EXTRA HELPERS ========= #
def get_nemesis(graph, particle):
    nemesis = None
    max_kills = 0
    for attacker, victims in graph.items():
        kills = victims.get(particle, {}).get('kills', 0)
        if kills > max_kills:
            max_kills = kills
            nemesis = attacker
    return nemesis

def get_victim(graph, particle):
    return max(graph[particle].items(), key=lambda x: x[1]['kills'], default=(None, 0))[0]


# ========= MAIN ========= #
def main(args):
    start = time.time()
    simulations_dir = 'simulations'
    conn = init_db()

    processed_files = load_processed_files() if not args.historic else set()
    all_files = sorted(f for f in os.listdir(simulations_dir) if f.endswith('.csv'))
    files_to_process = [f for f in all_files if args.historic or f not in processed_files]

    if not files_to_process:
        print("No new log files to process.")
        return

    # Group files by day
    files_by_day = defaultdict(list)
    for f in files_to_process:
        date_str = f.split('_')[0]
        if date_str:
            files_by_day[date_str].append(f)

    for date_str, day_files in tqdm(files_by_day.items(), desc="Processing days", unit="day"):
        try:
            date_obj = datetime.strptime(date_str, "%Y%m%d")
            iso_date = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            print(f"Skipping invalid filename format: {date_str}")
            continue

        log_data = []
        for filename in day_files:
            file_path = os.path.join(simulations_dir, filename)
            try:
                with open(file_path, 'r') as f:
                    reader = csv.DictReader(f)
                    log_data.extend(reader)
                processed_files.add(filename)
            except Exception as e:
                print(f"Failed to read {filename}: {e}")

        if not log_data:
            continue

        daily_graph = create_interaction_graph(log_data)

        # Save to DB (idempotent)
        save_daily_ranking(conn, iso_date, log_data)
        save_daily_summary(conn, iso_date, daily_graph)
        save_daily_player_stats(conn, iso_date, daily_graph)

    save_processed_files(processed_files)
    conn.close()
    print(f"\nProcessing complete in {time.time() - start:.2f}s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process particle arena logs into SQLite.")
    parser.add_argument('--historic', action='store_true', help="Rebuild entire history from scratch.")
    args = parser.parse_args()
    main(args)