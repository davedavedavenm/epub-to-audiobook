#!/bin/bash
# Two-lane harvest: polls BOTH sessions' as_state.json for completed chapters
# and downloads each mastered mp3 once. Lane scopes are disjoint, so file
# names never collide between lanes.
export PATH=$HOME/.local/bin:$PATH
mkdir -p /tmp/harvest
echo "$(date +%H:%M) harvest loop v2 started (render, render2)" >> /tmp/harvest.log
while true; do
  sleep 240
  for sess in render render2; do
    comp=$(colab exec -s $sess -f /tmp/harvest_probe.py 2>/dev/null | tr -d "\r" | grep -vE "^\[|^\s*$" | tail -1)
    for slug in $comp; do
      f=/tmp/harvest/armed_struggle_$slug\_cillian.mp3
      if [ ! -f "$f" ]; then
        colab download -s $sess /content/out/armed_struggle_$slug\_cillian.mp3 $f >/dev/null 2>&1 && echo "$(date +%H:%M) harvested $slug from $sess" >> /tmp/harvest.log
      fi
    done
  done
done
