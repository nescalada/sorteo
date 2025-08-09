import os
import csv
import json
import time
import argparse
from collections import defaultdict
from datetime import datetime

PROCESSED_FILE_PATH = 'data/processed_logs/processed_files.json'
GRAPH_CACHE_PATH = 'data/historic_stats/interaction_graph.json'
DAILY_RESULTS_DIR = 'data/daily/'

# Ensure the files exist
os.makedirs(os.path.dirname(PROCESSED_FILE_PATH), exist_ok=True)
os.makedirs(os.path.dirname(GRAPH_CACHE_PATH), exist_ok=True)
os.makedirs(DAILY_RESULTS_DIR, exist_ok=True)

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

def load_cached_graph():
    if os.path.exists(GRAPH_CACHE_PATH):
        with open(GRAPH_CACHE_PATH, 'r') as f:
            return json.load(f)
    return {}

def save_cached_graph(graph):
    with open(GRAPH_CACHE_PATH, 'w') as f:
        json.dump(graph, f)

def reset_tracking():
    if os.path.exists(PROCESSED_FILE_PATH):
        os.remove(PROCESSED_FILE_PATH)
    if os.path.exists(GRAPH_CACHE_PATH):
        os.remove(GRAPH_CACHE_PATH)
    print("Tracking and cache have been reset.")

def create_interaction_graph(log_data):
    interaction_graph = defaultdict(lambda: defaultdict(lambda: {'dmg_dealt': 0.0, 'kills': 0}))
    for entry in log_data:
        particle = entry.get('Particle')
        opponent = entry.get('Opponent')
        damage_taken = entry.get('Force Received') or entry.get('damage_taken')
        killed = entry.get('Killed')

        if not (particle and opponent and damage_taken):
            continue

        try:
            dmg = float(damage_taken)
        except (ValueError, TypeError):
            dmg = 0.0

        kill_count = 1 if killed == 'True' else 0

        interaction_graph[opponent][particle]['dmg_dealt'] += dmg
        interaction_graph[opponent][particle]['kills'] += kill_count

    return {p: dict(opp) for p, opp in interaction_graph.items()}

def get_damage_dealt(graph, particle):
    return sum(stats['dmg_dealt'] for stats in graph.get(particle, {}).values())

def get_damage_received(graph, particle):
    return sum(stats.get(particle, {}).get('dmg_dealt', 0.0) for stats in graph.values())

def get_kills(graph, particle):
    return sum(stats['kills'] for stats in graph.get(particle, {}).values())

def get_deaths(graph, particle):
    return sum(stats.get(particle, {}).get('kills', 0) for stats in graph.values())

def get_top_killer(graph):
    return max(
        ((p, get_kills(graph, p)) for p in graph),
        key=lambda x: x[1],
        default=(None, 0)
    )

def get_nemesis(graph, particle):
    # Returns the particle that killed 'particle' the most
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

def get_top_damage_dealer(graph):
    return max(
        ((p, get_damage_dealt(graph, p)) for p in graph),
        key=lambda x: x[1],
        default=(None, 0)
    )

def get_top_damage_receiver(graph):
    return max(
        ((p, get_damage_received(graph, p)) for p in graph),
        key=lambda x: x[1],
        default=(None, 0)
    )

def get_top_death_count(graph):
    return max(
        ((p, get_deaths(graph, p)) for p in graph),
        key=lambda x: x[1],
        default=(None, 0)
    )

def get_winner(graph):
    alive_particles = {p for p in graph if get_deaths(graph, p) == 0}
    if len(alive_particles) == 1:
        return list(alive_particles)
    return None

def settle_day(graph, filenames):
    if not filenames:
        print("No files to settle.")
        return
    # Use first file's timestamp
    timestamp = filenames[0].split('_')[0]
    try:
        datetime.strptime(timestamp, "%Y%m%d")
    except ValueError:
        print(f"Invalid timestamp format in filename: {filenames[0]}")
        return

    outfile = os.path.join(DAILY_RESULTS_DIR, f"{timestamp}.json")
    with open(outfile, 'w') as f:
        json.dump({
            "date": timestamp,
            "winner": get_top_killer(graph)[0],
            "interactions": graph
        }, f)
    print(f"Daily results saved: {outfile}")


def main(args):
    start = time.time()
    simulations_dir = 'simulations'

    if args.reset:
        reset_tracking()

    processed_files = load_processed_files() if not args.historic else set()
    cached_graph = {} if args.historic else load_cached_graph()

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

    for date_str, day_files in files_by_day.items():
        try:
            date_obj = datetime.strptime(date_str, "%Y%m%d")
            iso_date = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            print(f"Skipping invalid filename format: {date_str}")
            continue

        # Generate daily stats filename
        daily_file = os.path.join(DAILY_RESULTS_DIR, f"{iso_date}.json")
        should_generate_daily = not os.path.exists(daily_file)

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

        if should_generate_daily:
            winner = get_winner(daily_graph)[0]
            
            with open(daily_file, 'w') as f:
                json.dump({
                    "date": iso_date,
                    "winner": winner,
                    "interactions": daily_graph
                }, f)
            print(f"Saved daily stats for {iso_date}")

        # Merge into historical graph
        for attacker, victims in daily_graph.items():
            if attacker not in cached_graph:
                cached_graph[attacker] = {}
            for victim, stats in victims.items():
                if victim not in cached_graph[attacker]:
                    cached_graph[attacker][victim] = {'dmg_dealt': 0.0, 'kills': 0}
                cached_graph[attacker][victim]['dmg_dealt'] += stats['dmg_dealt']
                cached_graph[attacker][victim]['kills'] += stats['kills']

    save_processed_files(processed_files)
    save_cached_graph(cached_graph)

    print(f"\n Processing complete in {time.time() - start:.2f}s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process particle arena logs.")
    parser.add_argument('-r', '--reset', action='store_true', help="Reset tracking and cache.")
    parser.add_argument('--settle', action='store_true', help="Settle the current day into a daily file.")
    parser.add_argument('--historic', action='store_true', help="Rebuild entire history from scratch.")
    args = parser.parse_args()
    main(args)