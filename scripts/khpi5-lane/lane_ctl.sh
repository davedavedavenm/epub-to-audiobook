#!/bin/bash
# lane_ctl.sh — entry point for the webapp's Colab fish lane.
#
# Contract (webapp/fish_lane.py render_colab, webapp/lanes.py _status_colab):
#   status | submit <tag> | progress <tag> | fetch <tag> <mp3> | log <tag>
#   | done <tag> | stop <tag>
#
# Called over ssh as `~/as-lane/lane_ctl.sh <cmd>` (lanes.py) or
# `bash -lc "as-lane/lane_ctl.sh <cmd>"` (fish_lane.py), so it must stay a
# thin, dependency-free dispatcher onto lane_ctl.py.
set -u
export PATH="$HOME/.local/bin:$PATH"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/lane_ctl.py" "$@"
