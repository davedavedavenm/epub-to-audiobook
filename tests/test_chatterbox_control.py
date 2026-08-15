"""Regression guards for the controlled Chatterbox diagnostic."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "webapp"))

import render_chatterbox_control as control  # noqa: E402
from voice_sample import sample_text_for  # noqa: E402


def test_hard_passage_and_server_chunks_are_pinned():
    text = sample_text_for("chatterbox")
    evidence = control._chunk_evidence(text)

    assert len(text) == 1010
    assert len(text.encode("utf-8")) == 1015
    assert len(text.split()) == 182
    assert len(evidence["chunks"]) == 4
    assert tuple(chunk["sha256"] for chunk in evidence["chunks"]) == (
        control.EXPECTED_CHUNK_SHA256
    )


def test_control_arms_use_one_seed_and_explicit_controls():
    assert control.SEED == 12_345
    assert {arm["cfg_weight"] for arm in control.ARMS} == {0.0, 0.5}
    assert {arm["exaggeration"] for arm in control.ARMS} == {0.5}
    assert all(status == status.lower() for status in control.ACTIVE_STATUSES)
    assert "recovering" in control.ACTIVE_STATUSES
    by_id = {arm["id"]: arm for arm in control.ARMS}
    assert by_id["irish-tadhg-v3-cfg-0.5"]["reference_sha256"] == control.TADHG_SHA256
    assert (
        by_id["australian-vctk-p374-v3-cfg-0.5"]["reference_sha256"]
        == control.VCTK_P374_SHA256
    )


def test_server_seed_is_temporary_and_custom_reference_wins():
    server = (ROOT / "chatterbox" / "server.py").read_text(encoding="utf-8")
    harness = (ROOT / "scripts" / "render_chatterbox_control.py").read_text(
        encoding="utf-8"
    )

    assert "seed: int | None = None" in server
    assert "with _request_rng(req.seed), torch.inference_mode():" in server
    assert "random.getstate()" in server and "random.setstate(python_state)" in server
    assert "np.random.get_state()" in server and "np.random.set_state(numpy_state)" in server
    assert "torch.get_rng_state()" in server and "torch.set_rng_state(torch_state)" in server
    assert 'f"if [ -f /app/voices/custom/{voice}.wav ]; then "' in harness
    assert '"epub-to-audiobook-ui"' in harness
    assert "base64.b64decode(encoded, validate=True)" in harness


def test_v3_compose_default_matches_official_same_language_default():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "CHATTERBOX_CFG_WEIGHT=${CHATTERBOX_V3_CFG_WEIGHT:-0.5}" in compose
