from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "evaluations" / "new-engines"


def test_new_engine_suite_is_cpu_only_and_resource_capped():
    compose = (EVAL / "compose.yaml").read_text()
    assert compose.count("cpus: 4") == 3
    assert compose.count("CUDA_VISIBLE_DEVICES=") == 3
    assert "devices:" not in compose
    assert "GPU" not in compose


def test_new_engine_suite_pins_authoritative_sources_and_models():
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in EVAL.glob("*.*") if path.is_file()
    )
    for pin in (
        "421f71559848572431bd6229af3e1a73f25986a7",
        "818569c6b832118ad68d61bbd873abe250fcd68a",
        "ab5d38ad46eec64a8e02a56c38a6e4f3c0cfdeb8",
        "1cc69363815254f6a19bd42534a66ee49fc0fae0",
        "39a4d01558db86dca1219273992c77ebc8e03991",
        "75c877ec8ac86dda42bfc0e9968c87f29e10ef57",
    ):
        assert pin in source


def test_audio8_uses_exact_reference_and_documented_chunk_limit():
    shared = (EVAL / "shared.py").read_text()
    audio8 = (EVAL / "render_audio8.py").read_text()
    assert "8774082c3acf6c215dc9307a4a9cce5fd50d4242fc9263534ed420675873e252" in shared
    assert "bounded_chunks(raw, 150)" in audio8
    assert "bounded_chunks(prepared, 150)" in audio8
    assert '"raw": (raw,' in audio8
    assert '"prepared": (prepared,' in audio8


def test_corrective_arms_use_complete_sentences_and_fixed_settings():
    sys.path.insert(0, str(EVAL))
    from shared import sentence_chunks

    chunks = sentence_chunks("One sentence. Dr. Wang finishes this sentence. Last one!")
    assert chunks == ["One sentence.", "Dr. Wang finishes this sentence.", "Last one!"]

    audio8 = (EVAL / "render_audio8.py").read_text(encoding="utf-8")
    zonos2 = (EVAL / "render_zonos2_continuity.py").read_text(encoding="utf-8")
    assert '"prepared_sentence_fixed"' in audio8
    assert "seed=42 if fixed_seed else 42 + index" in audio8
    assert '"join_silence_ms": join_silence_ms' in audio8
    assert '"one persistent server; one cached Arthur embedding"' in zonos2
    assert '"speaker_embedding_id": speaker_id' in zonos2
    assert '"seed": 42' in zonos2
    assert '"join_silence_ms": 0' in zonos2
    assert 'minimum_duration_seconds=5 if mode == "iphone_split" else 10' in zonos2

    assembly = (EVAL / "assemble_zonos2_repair.py").read_text(encoding="utf-8")
    assert "failed_component_retained" in assembly
    assert "_words(original_sentence)" in assembly


def test_output_is_ignored_and_structurally_checked():
    assert "evaluations/new-engines/output/" in (ROOT / ".gitignore").read_text()
    shared = (EVAL / "shared.py").read_text()
    assert '"-f", "null"' in shared
    assert "duration_seconds" in shared
    assert "quality requires human listening" in shared


def test_asr_is_explicitly_structural_not_a_quality_rank():
    verifier = (EVAL / "verify_outputs.py").read_text()
    assert "does not rank voice, accent, pacing, prosody, or pronunciation" in verifier
    assert "diff_report" in verifier
    assert "cpu_threads=4" in verifier
