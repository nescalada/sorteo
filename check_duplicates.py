# Read follower info and see if there are duplicates
import os
import csv

FOLLOWER_PATH_INFO = 'followers_info'

def main():
    # Read csv in followers_info
    csv_files = [f for f in os.listdir(FOLLOWER_PATH_INFO) if f.endswith('.csv')]
    all_followers = set()
    for csv_file in csv_files:
        with open(os.path.join(FOLLOWER_PATH_INFO, csv_file), "r", encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for row in reader:
                all_followers.add(tuple(row))
    print(f"Total unique followers found: {len(all_followers)}")

if __name__ == "__main__":
    main()