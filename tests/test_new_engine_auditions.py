from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "evaluations" / "new-engines"


def test_new_engine_suite_is_cpu_only_and_resource_capped():
    compose = (EVAL / "compose.yaml").read_text()
    services = compose.count("      dockerfile: evaluations/new-engines/")
    assert services == 5
    assert compose.count("cpus: 4") == services
    assert compose.count("CUDA_VISIBLE_DEVICES=") == services
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
        "58fd4a58de8980b42c1021492728876d67ea2718",
        "0fe297e449ba4f31113977f6c7f8c438fdfd1be3",
        "cb2b2a1949cd70cca469d689416906a6d181fa22",
        "0abc5561e8ffd7b582b8aea2eb9e5f3bf7637c26",
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


def test_self_chunking_engines_render_one_call_and_keep_a_runtime_control():
    """LoudKit and Sopro window internally, so the harness must not pre-chunk.

    Both engines publish their own long-form segmentation (LoudKit windows at
    255 tokens with a six-token carry-over; Sopro splits on --max-seconds), so
    passing the whole prepared passage in one call is what is actually under
    test. Each engine also keeps a same-text control arm on a second numeric
    path, the way Scylla's FP32 control ruled out INT8.
    """
    loudkit = (EVAL / "render_loudkit.py").read_text(encoding="utf-8")
    sopro = (EVAL / "render_sopro.py").read_text(encoding="utf-8")
    for source in (loudkit, sopro):
        assert "bounded_chunks" not in source
        assert "sentence_chunks" not in source
        assert '"join_silence_ms": 0' in source
        assert '"chunking": (' in source
        assert "engine-internal:" in source
        assert '"seed": 42' in source
    assert '"onnx"' in loudkit and '"torch"' in loudkit
    assert '"fp32"' in sopro and '"int8"' in sopro
    assert "uk_male_minter" not in loudkit  # the reference comes from shared.ARTHUR


def test_loudkit_records_that_no_shipped_voice_is_british():
    """The 20 managed voices ship two English profiles, both CC0 US donations.

    VOICES.md lists joe and kathleen as the only English voices, so the cloned
    Arthur path is the only project-relevant arm and the evidence must say so.
    """
    loudkit = (EVAL / "render_loudkit.py").read_text(encoding="utf-8")
    assert "no shipped English voice is British" in loudkit


def test_loudkit_uses_the_passage_api_and_refuses_a_truncated_audition():
    """synthesize() renders exactly one window; synthesize_long() renders the passage.

    The first run of this gate called the single-window form and got 10.2 s of
    audio for the 1,142-character corpus, with upstream's own hit_token_cap set
    and a chunk count of one. The guard keeps a truncated arm from ever being
    written as a listening candidate again.
    """
    loudkit = (EVAL / "render_loudkit.py").read_text(encoding="utf-8")
    assert "engine.synthesize_long(" in loudkit
    assert "engine.synthesize(" not in loudkit
    assert "len(result.chunks) < 2 or result.duration < 60" in loudkit
    # hit_token_cap is surfaced in the evidence, never used to reject an arm:
    # upstream defines it as "worth surfacing", and the listening verdict is Dave's.
    assert '"upstream_hit_token_cap"' in loudkit
    assert '"upstream_inspections"' in loudkit
    assert "refusing to write a truncated audition" in loudkit
