import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "nvidia_nim_magpie_control.py"


def test_nvidia_control_is_one_request_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    ast.parse(source)
    assert source.count("requests.post(") == 1
    assert "NVIDIA_API_KEY" in source
    assert "--confirm-single-free-prototype-request" in source
    assert "refusing to overwrite" in source
    assert "retry" not in source.lower().split("def main", 1)[1]
    assert "Magpie-Multilingual.EN-US.Aria" in source
    assert '"LINEAR_PCM"' in source
    assert '"44100"' in source
