import ast
import hashlib

from scripts.kaggle import build_magpie_longform_gate as gate


def test_magpie_sources_and_official_pins():
    long_text = gate.listening_text()
    assert len(long_text.split()) == 1470
    assert hashlib.sha256(long_text.encode()).hexdigest() == gate.LONG_SHA256
    assert hashlib.sha256(gate.PREPARED_TEXT.encode()).hexdigest() == gate.HARD_SHA256
    assert not any(char.isdigit() for char in gate.PREPARED_TEXT)
    assert gate.SPEAKERS == {"Aria": 0, "Jason": 1, "John": 2, "Leo": 3, "Sofia": 4}
    assert len(gate.NEMO_SPEECH_COMMIT) == 40
    assert len(gate.MODEL_REVISION) == 40


def test_generated_kernel_is_private_free_t4_and_human_gated(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "OUT", tmp_path)
    assert gate.main() == 0
    source = (tmp_path / "run_magpie_longform_gate.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert '"is_private": True' not in source  # metadata, not runtime source
    assert '"paid_compute": False' in source
    assert '"hosted_api_used": False' in source
    assert '"asr_used": False' in source
    assert '"quality_verdict": "human listening required"' in source
    assert 'if "T4" not in gpu_name' in source
    assert "base64.b64decode" in source
    assert gate.PREPARED_TEXT not in source
    assert "language_tokenizer_map=" not in source
    metadata = (tmp_path / "kernel-metadata.json").read_text(encoding="utf-8")
    assert '"is_private": true' in metadata
    assert '"machine_shape": "NvidiaTeslaT4"' in metadata
