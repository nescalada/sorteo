#!/bin/bash

python simulation.py
python utils/log_manager.py

git add .
git commit -m "Day $(date '+%Y-%m-%d'): Update stats"
git push
