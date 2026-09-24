"""Re-adopt a live Colab assignment whose local sessions.json entry was pruned.

Restores the name->endpoint/token/url mapping and respawns the keep-alive
daemon, without touching the VM (no new assignment, no billing change).
"""
import sys

sys.path.insert(
    0, "/home/dave/.local/share/uv/tools/google-colab-cli/lib/python3.13/site-packages"
)

from colab_cli.common import state
from colab_cli.state import SessionState
from colab_cli.commands.session import spawn_keep_alive

EP = "gpu-l4-s-kkb-ass1a1-rxwdks0v6xni"
NAME = "render"

assignments = state.client.list_assignments()
a = next((x for x in assignments if getattr(x, "endpoint", None) == EP), None)
if a is None:
    print("ASSIGNMENT GONE - VM reclaimed; re-provision needed")
    sys.exit(2)

rpi = a.runtime_proxy_info
s = SessionState(
    name=NAME,
    token=rpi.token,
    url=rpi.url,
    endpoint=EP,
    variant="GPU",
    accelerator="L4",
    machine_shape="STANDARD",
)
state.store.add(s)
pid = spawn_keep_alive(EP, NAME)
s.keep_alive_pid = pid
state.store.add(s)
print("ADOPTED", EP, "keep_alive_pid", pid)
print("url", rpi.url)
