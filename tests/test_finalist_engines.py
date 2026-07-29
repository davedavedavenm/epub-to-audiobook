"""Production-boundary guards for VibeVoice/Qwen3-TTS finalists."""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))
os.environ.setdefault('DB_PATH', os.path.join(tempfile.mkdtemp(), 'test.db'))
os.environ.setdefault('UPLOAD_DIR', tempfile.mkdtemp())
os.environ.setdefault('OUTPUT_DIR', tempfile.mkdtemp())
os.environ.setdefault('PREVIEWS_DIR', tempfile.mkdtemp())
os.environ.setdefault('LOG_DIR', tempfile.mkdtemp())
os.environ.setdefault('LIBRARY_DIR', tempfile.mkdtemp())
os.environ.setdefault('TOC_CACHE_DIR', tempfile.mkdtemp())
os.environ.setdefault('TRANSCRIPTS_DIR', tempfile.mkdtemp())
os.environ.setdefault('QUEUE_RUNNER_ENABLED', '0')

import app as A


def _patch_gate(monkeypatch, engine):
    monkeypatch.setattr(A, 'get_job', lambda _jid: {
        'id': 'job', 'tts_engine': engine, 'output_format': 'm4b',
        'book_name': 'Raven', 'input_filename': ''})
    monkeypatch.setattr(A, '_ollama_available', lambda: False)
    monkeypatch.setattr(A, '_read_captured_chunks', lambda _jid: [])
    monkeypatch.setattr(A, 'append_job_log', lambda *a, **k: None)
    monkeypatch.setattr(A, 'update_job', lambda *a, **k: None)


def _chapter(out: Path, number=1):
    p = out / f'{number:04d}_Raven.mp3'
    p.write_bytes(b'ID3' + b'x' * 12000)
    return p


def _qa(out: Path, chapters=(1,), wer=0.02):
    (out / 'qa_report.json').write_text(json.dumps({'chapters': [
        {'chapter': n, 'wer': wer, 'n_source': 500, 'flagged': False,
         'divergences': [], 'lexicon_suggestions': {}} for n in chapters]}))


def test_only_listened_finalist_voices_are_registered():
    assert A.VOICES['uk_male_minter_vibevoice']['engine'] == 'vibevoice'
    assert A.VOICES['uk_male_minter_qwen3']['engine'] == 'qwen3'
    assert not any(v.startswith('uk_female_') and m.get('engine') in ('vibevoice', 'qwen3')
                   for v, m in A.VOICES.items())


def test_retry_commands_keep_quality_parameters_and_asr(monkeypatch):
    monkeypatch.setattr(A, 'get_setting', lambda _key: None)
    base = {'id': 'j', 'input_filename': 'b.epub', 'output_dirname': 'o',
            'voice': 'uk_male_minter_vibevoice', 'tts_engine': 'vibevoice'}
    vibe = A.build_retry_cmd_from_job(base)
    assert vibe[vibe.index('--chunk-chars') + 1] == '1000000'
    assert vibe[vibe.index('--request-timeout') + 1] == '21600'
    assert '--qa' in vibe and '--job-id' in vibe
    qwen = A.build_retry_cmd_from_job({**base, 'voice': 'uk_male_minter_qwen3',
                                      'tts_engine': 'qwen3'})
    assert qwen[qwen.index('--chunk-chars') + 1] == '450'
    assert qwen[qwen.index('--join-silence-ms') + 1] == '350'
    assert '--qa' in qwen and '--job-id' in qwen


def test_finalist_missing_qa_holds_before_m4b_or_sync(tmp_path, monkeypatch):
    _patch_gate(monkeypatch, 'vibevoice')
    _chapter(tmp_path)
    called = []
    monkeypatch.setattr(A, '_maybe_build_m4b', lambda *a: called.append('m4b'))
    monkeypatch.setattr(A, 'copy_to_audiobookshelf', lambda *a, **k: called.append('sync'))
    assert A._gate_and_sync('job', tmp_path, 'Raven', 1) == 'held'
    assert called == []
    gate = json.loads((tmp_path / '_presync_gate.json').read_text())
    assert gate['verified'] is False
    assert 'missing' in gate['unverified_reason']


def test_finalist_incomplete_or_invalid_qa_holds(tmp_path, monkeypatch):
    _patch_gate(monkeypatch, 'qwen3')
    _chapter(tmp_path, 1)
    _chapter(tmp_path, 2)
    _qa(tmp_path, (1,))
    held, flags, _ = A.presync_quality_gate('job', tmp_path)
    assert held
    assert any(f['issue'] == 'qa_missing' and '2' in f['detail'] for f in flags)
    (tmp_path / 'qa_report.json').write_text('{bad json')
    held, flags, _ = A.presync_quality_gate('job', tmp_path)
    assert held and flags[0]['issue'] == 'qa_missing'


def test_valid_single_chapter_qa_reaches_m4b_then_sync(tmp_path, monkeypatch):
    _patch_gate(monkeypatch, 'vibevoice')
    _chapter(tmp_path)
    _qa(tmp_path)
    called = []
    monkeypatch.setattr(A, '_maybe_build_m4b', lambda *a: called.append('m4b'))
    monkeypatch.setattr(A, 'copy_to_audiobookshelf', lambda *a, **k: called.append('sync') or False)
    assert A._gate_and_sync('job', tmp_path, 'Raven', 1) == 'completed'
    assert called == ['m4b', 'sync']
    assert json.loads((tmp_path / '_presync_gate.json').read_text())['verified'] is True


def test_finalist_kaggle_templates_pin_runtime_and_deployed_app_ref():
    root = Path(__file__).resolve().parents[1]
    vibe = (root / 'scripts/kaggle/run_vibevoice.py').read_text()
    qwen = (root / 'scripts/kaggle/run_qwen3.py').read_text()
    assert '07cb79feadd2d3fd7f47530d4c964a12857936a0' in vibe
    assert '022e286b98fbec7e1e916cb940cdf532cd9f488e' in qwen
    for src in (vibe, qwen):
        assert 'APP_REF = ""' in src
        assert 'checkout", "--detach", APP_REF' in src
        assert 'BRANCH = "master"' not in src
        assert 'qa_report.json' in src and 'assert qa.get("chapters")' in src
        assert '["apt-get", "install", "-y", "git-lfs"]' in src
        assert '["git", "-C", REPO_DIR, "lfs", "pull"' in src
        assert 'check=False' not in src
        assert 'raw[:4] == b"RIFF"' in src and 'len(raw) == 864182' in src
        assert '8774082c3acf6c215dc9307a4a9cce5fd50d4242fc9263534ed420675873e252' in src
