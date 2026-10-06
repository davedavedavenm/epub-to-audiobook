# khpi5 Colab lane control plane

These four files are the copy of `~/as-lane/` on **khpi5** (the Raspberry Pi that drives
Colab through `google-colab-cli`). The webapp reaches them over SSH
(`COLAB_SSH_HOST`, `as-lane/lane_ctl.sh`); see `webapp/fish_lane.py::render_colab`.
They are runner-agnostic: any runner that honours the lane contract works
(`scripts/fish_colab_runner.py`, `scripts/higgs_colab_runner.py`).

Deploy = copy to `~/as-lane/` on khpi5 (backups are kept as `*.bak-<date>`).

## Lane contract (what a runner must provide)
- `/content/as_bundle.zip` in, `/content/runner.py` launched detached by `lane_launch.py`
- `/content/as_state.json` `{"completed": [slug...], "progress": {slug: n}}` (heartbeat)
- `/content/manifest.json` (chapter slugs), `/content/out/<book_tag>_<slug>_<voice_tag>.mp3`
- `/content/render.log` (stdout); markers `=== CHAPTER DONE: <slug>` / `ALL CHAPTERS COMPLETE`

## 2026-10-06 fix
`list_sessions()` parsed every `[xxx]` line of `colab sessions`, including the CLI's
`[colab] A new version ... is available` notices, as live sessions. The status showed 4
phantom sessions named `colab`, so the 2-slot guard refused every submit
("4/2 Colab GPU slots in use"). It now matches only real session lines
(`[name] gpu-... | Hardware: ...`) and `enable_update_check` is false in
`~/.config/colab-cli/settings.json`.
