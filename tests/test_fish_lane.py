"""Fish lane + bundle tests (no GPU, no lane credentials required).

Covers the pieces a broken integration would otherwise hide:
  * the bundle builder's contract with the runner (payloads/refs/manifest),
  * the ref derivation (quote crop = exact tail of the narration clip),
  * lane resolution rules (free-first auto, explicit-refusal, paid never default),
  * the fish tombstones (no local engine URL, no engine failover),
  * resume span math (never re-render banked chapters),
  * the /api/lanes endpoint never 500s,
  * job creation refuses fish on a non-lane target.
"""
import io
import json
import os
import sys
import tempfile
import wave
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'webapp'))
sys.path.insert(0, str(ROOT / 'scripts'))

os.environ.setdefault('DB_PATH', os.path.join(tempfile.mkdtemp(), 'test.db'))
os.environ.setdefault('UPLOAD_DIR', tempfile.mkdtemp())
os.environ.setdefault('OUTPUT_DIR', tempfile.mkdtemp())
os.environ.setdefault('PREVIEWS_DIR', tempfile.mkdtemp())
os.environ.setdefault('LOG_DIR', tempfile.mkdtemp())
os.environ.setdefault('LIBRARY_DIR', tempfile.mkdtemp())
os.environ.setdefault('TOC_CACHE_DIR', tempfile.mkdtemp())
os.environ.setdefault('TRANSCRIPTS_DIR', tempfile.mkdtemp())
os.environ.setdefault('QUEUE_RUNNER_ENABLED', '0')

import app as appmod  # noqa: E402
import fish_bundle  # noqa: E402
import fish_lane as FL  # noqa: E402
import lanes as LN  # noqa: E402


@pytest.fixture
def client():
    appmod.app.config['TESTING'] = True
    with appmod.app.test_client() as c:
        yield c

PARA = ("On the twenty-first of January nineteen nineteen the first Dáil met in "
        "Dublin and declared an independent republic, though the British "
        "administration continued to govern most of the island from Dublin "
        "Castle. The delegates argued through the winter about land, language "
        "and loyalty, and the surrounding streets filled with people who had "
        "walked in from the country to hear the debates reported aloud.")

PARA_QUOTED = ("Speaking to the delegates, the chairman said “the rights of "
               "small nations are not negotiable in the councils of empires” "
               "and the chamber erupted, while outside in the cold the sentries "
               "shifted from foot to foot and the lamp burners hissed against "
               "the glass along the corridor of the hall.")

PARA3 = ("By the following summer the conflict had spread across four provinces "
         "and the newer formations began keeping their own lists of members, "
         "drilling in farmyards at night and moving dispatches by bicycle "
         "along the coastal roads. Every county reported differently and the "
         "quotas for weapons rarely arrived on time, which forced the volunteer "
         "columns to improvise whatever they could find in the sheds.")


def _make_epub(path: Path, chapters=(('Chapter One', PARA),
                                     ('Chapter Two', PARA_QUOTED),
                                     ('Chapter Three', PARA3))):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('mimetype', 'application/epub+zip')
        z.writestr('META-INF/container.xml',
                   '<?xml version="1.0"?><container version="1.0" '
                   'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                   'media-type="application/oebps-package+xml"/></rootfiles></container>')
        items, refs = [], []
        for i, (title, text) in enumerate(chapters, 1):
            name = f'chap{i}.xhtml'
            z.writestr(f'OEBPS/{name}',
                       f'<?xml version="1.0" encoding="utf-8"?>'
                       f'<html xmlns="http://www.w3.org/1999/xhtml"><head>'
                       f'<title>{title}</title></head><body>'
                       f'<h1>{title}</h1>'
                       + ''.join(f'<p>{text}</p>' for _ in range(3))
                       + '</body></html>')
            items.append(f'<item id="c{i}" href="{name}" media-type="application/xhtml+xml"/>')
            refs.append(f'<itemref idref="c{i}"/>')
        z.writestr('OEBPS/content.opf',
                   '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" '
                   'version="2.0" unique-identifier="id"><metadata '
                   'xmlns:dc="http://purl.org/dc/elements/1.1/">'
                   '<dc:title>Lane Test Book</dc:title><dc:creator>Test</dc:creator>'
                   '<dc:identifier id="id">urn:uuid:lanetest</dc:identifier>'
                   '</metadata><manifest>' + ''.join(items) +
                   '</manifest><spine>' + ''.join(refs) + '</spine></package>')


@pytest.fixture()
def mini_epub(tmp_path):
    p = tmp_path / 'book.epub'
    _make_epub(p)
    return p


# --- bundle contract -------------------------------------------------------

def test_bundle_contract(mini_epub, tmp_path):
    out = tmp_path / 'b.zip'
    m = fish_bundle.build_bundle(mini_epub, out)
    assert out.exists() and out.stat().st_size > 100_000  # refs alone are ~1.8 MB
    assert [c['slug'] for c in m['chapters']] == ['ch01', 'ch02', 'ch03']
    assert m['book_tag'] and m['voice_tag'] == 'cillian'
    assert m['recipe']['temperature'] == 0.85 and m['recipe']['seeds'] == [42, 43, 44]
    # The recipe's hard rule: no bare digit runs survive prep (1919 -> words).
    assert m['digit_runs'] == [], m['digit_runs']

    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        assert {'manifest.json', 'refs/cillian_irish.wav',
                'refs/crop_expressive_tail.wav', 'refs/refs.json'} <= names
        for slug in ('ch01', 'ch02', 'ch03'):
            assert f'payloads/{slug}.json' in names
            assert f'transcripts/{slug}.txt' in names
        payload = json.loads(z.read('payloads/ch01.json'))
        assert payload['slug'] == 'ch01'
        assert all({'text', 'para', 'quote'} <= set(s) for s in payload['sents'])
        assert payload['sents'], 'no sentences prepped'


def test_bundle_quote_crop_is_exact_tail_of_narration():
    """The quote reference must be the tail of the TRACKED narration clip —
    byte-identical PCM frames to the deployed crop (recipe lock)."""
    def frames(b):
        with wave.open(io.BytesIO(b)) as w:
            return w.getnchannels(), w.getframerate(), w.readframes(w.getnframes())

    narr, quote, texts = fish_bundle.read_refs()
    ch, rate, f = frames(quote)
    assert (ch, rate) == (1, 24000)
    with wave.open(io.BytesIO(narr)) as w:
        all_frames = w.readframes(w.getnframes())
    assert f == all_frames[-len(f):], 'quote crop is not the tail of the narration clip'
    # Ref texts ship in the repo so a fresh checkout can build bundles.
    assert texts.get('crop_expressive_tail_text')
    assert fish_bundle.REF_TEXTS.exists()


def test_bundle_range_filter(mini_epub, tmp_path):
    m = fish_bundle.build_bundle(mini_epub, tmp_path / 'b.zip', start=2, end=2)
    assert [c['slug'] for c in m['chapters']] == ['ch02']
    assert [c['index'] for c in m['chapters']] == [2]


def test_digit_scan_flags_bare_runs():
    payloads = {'ch01': {'sents': [{'text': 'He was 1 of the men', 'para': 0, 'quote': False},
                                   {'text': 'The year nineteen sixteen passed', 'para': 0,
                                    'quote': False}]}}
    found = fish_bundle.scan_digit_runs(payloads)
    assert len(found) == 1 and found[0]['digit'] == '1'


# --- runner portability guard ---------------------------------------------

def test_runner_is_lane_portable_but_defaults_to_content():
    src = (ROOT / 'scripts' / 'fish_colab_runner.py').read_text(encoding='utf-8')
    assert 'FISH_BASE' in src and 'manifest.json' in src
    # The deployed Colab lanes must keep their exact default behaviour.
    assert 'os.environ.get("FISH_BASE", "/content")' in src
    # No stray hardcoded /content outside the default + docstring.
    strays = [l for l in src.splitlines()
              if '/content' in l and not l.strip().startswith('#')
              and 'FISH_BASE' not in l and '"""' not in l and 'Lane portability' not in l]
    assert not strays, strays


# --- lane resolution rules -------------------------------------------------

def _isolate_lane_creds(monkeypatch, tmp_path):
    """Point every lane-credential source at a guaranteed-empty state.

    Real machines carry real creds outside the env: ~/.kaggle/access_token
    (kaggle_ready's file check) and the settings DB (_cfg reads get_setting
    first). Without this the 'nothing configured' assertions are host-dependent.
    """
    for k in ('COLAB_SSH_HOST', 'LIGHTNING_API_KEY', 'LIGHTNING_USERNAME',
              'KAGGLE_API_TOKEN', 'KAGGLE_KEY', 'KAGGLE_USERNAME'):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv('KAGGLE_CONFIG_DIR', str(tmp_path))  # no kaggle.json/token


def test_resolve_lane_free_first(monkeypatch, tmp_path):
    """auto NEVER selects the paid lane — queueing a book is not authorization
    to spend (DECISIONS.md: queue never provisions paid GPU)."""
    _isolate_lane_creds(monkeypatch, tmp_path)
    LN._cache.clear()
    with pytest.raises(ValueError):
        LN.resolve_lane('auto')
    # Only the PAID lane configured -> auto must STILL refuse. Spending money
    # requires naming the lane; an unconfigured free lane is not a reason to
    # fall through to a billable one.
    monkeypatch.setenv('LIGHTNING_API_KEY', 'k')
    monkeypatch.setenv('LIGHTNING_USERNAME', 'u')
    LN._cache.clear()
    with pytest.raises(ValueError) as e:
        LN.resolve_lane('auto')
    assert 'paid' in str(e.value).lower()
    # Naming it explicitly is the authorization, and it works.
    assert LN.resolve_lane('lightning') == 'lightning'
    # An explicit pick of an unconfigured free lane refuses too.
    with pytest.raises(ValueError):
        LN.resolve_lane('colab')
    # An unknown lane name is refused, never silently treated as auto.
    with pytest.raises(ValueError) as e:
        LN.resolve_lane('vast')
    assert 'unknown lane' in str(e.value).lower()
    # Free lane present -> auto prefers it over paid, always.
    monkeypatch.setenv('COLAB_SSH_HOST', 'khpi5')
    LN._cache.clear()
    assert LN.resolve_lane('auto') == 'colab'
    assert LN.resolve_lane('lightning') == 'lightning'


def test_lane_ready_kaggle_is_honest(monkeypatch):
    monkeypatch.setenv('KAGGLE_API_TOKEN', 'tok')
    monkeypatch.setenv('KAGGLE_USERNAME', 'user')
    LN._cache.clear()
    ready, why = FL.lane_ready('kaggle')
    assert ready is False and 'not wired' in why


def test_lane_ready_lightning_refuses_when_sdk_missing(monkeypatch):
    """Credentials authorise the paid lane; the environment must still be able to
    honour them.

    lightning-sdk cannot be installed alongside the Vast CLI (urllib3 caps
    overlap — webapp/requirements.txt), so a named-lightning render is refused
    HERE, at the first line of render_on_lane(), with the same words the Render
    Lanes panel shows — instead of being queued and dying on an ImportError.

    Authorization semantics are deliberately untouched: naming the lane is
    still the authorization (test_job_creation_accepts_a_named_paid_lane...).
    """
    monkeypatch.setenv('LIGHTNING_API_KEY', 'k')
    monkeypatch.setenv('LIGHTNING_USERNAME', 'u')
    LN._cache.clear()
    if LN.lightning_sdk_available():
        pytest.skip('lightning-sdk installed — refusal path not reachable')
    ready, why = FL.lane_ready('lightning')
    assert ready is False
    assert 'not installed' in why
    # POST-time authorization still succeeds — this is a readiness gate, not a
    # credential one.
    assert LN.resolve_lane('lightning') == 'lightning'


# --- tombstones / no wrong-engine books ------------------------------------

def test_fish_has_no_local_engine_url():
    with pytest.raises(ValueError) as e:
        appmod.get_engine_url('fish', 'job1')
    assert 'lane' in str(e.value).lower()


def test_fish_never_falls_back(monkeypatch):
    """A fish request must never become a kokoro/tada book (#24/piper class)."""
    appmod._ENGINE_HEALTH_CACHE['ts'] = 0
    appmod._ENGINE_HEALTH_CACHE['data'] = {}
    assert 'fish' not in appmod._ENGINE_FALLBACK_ORDER
    eng, voice, note = appmod.pick_engine_with_fallback(
        'fish', 'fish_cillian_irish', allow_fallback=True)
    assert eng == 'fish' and voice == 'fish_cillian_irish' and note is None


def test_fish_engine_registered_and_preview_is_gpu_only():
    assert 'fish' in appmod.TTS_ENGINES
    v = appmod.all_voices()['fish_cillian_irish']
    assert v['engine'] == 'fish' and v['accent'] == 'Irish'
    # No cached preview in the temp PREVIEWS_DIR -> the voice must NOT claim to
    # be audition-ready, and get_voice_preview must not try to synthesize here.
    merged = appmod.voices_for_client()['fish_cillian_irish']
    assert merged['preview_cached'] is False
    assert appmod.get_voice_preview('fish_cillian_irish') is None


def test_health_fish_tracks_lane_config(monkeypatch, tmp_path):
    _isolate_lane_creds(monkeypatch, tmp_path)
    LN._cache.clear()
    appmod._ENGINE_HEALTH_CACHE['ts'] = 0
    appmod._ENGINE_HEALTH_CACHE['data'] = {}
    assert appmod.check_engines_health().get('fish') is False
    monkeypatch.setenv('LIGHTNING_API_KEY', 'k')
    monkeypatch.setenv('LIGHTNING_USERNAME', 'u')
    LN._cache.clear()
    appmod._ENGINE_HEALTH_CACHE['ts'] = 0
    appmod._ENGINE_HEALTH_CACHE['data'] = {}
    assert appmod.check_engines_health().get('fish') is True


# --- resume span math ------------------------------------------------------

def test_lane_missing_spans_keeps_banked_chapters(tmp_path):
    epub = tmp_path / 'book.epub'
    _make_epub(epub)
    out = tmp_path / 'out'
    out.mkdir()
    (out / '001_Chapter_One.mp3').write_bytes(b'x' * 20_000)
    spans, banked, missing = appmod._lane_missing_spans(epub, out, 1, 0)
    assert banked == 1 and missing == 2
    assert spans == [(2, 3)]
    (out / '002_Chapter_Two.mp3').write_bytes(b'x' * 20_000)
    (out / '003_Chapter_Three.mp3').write_bytes(b'x' * 20_000)
    spans, banked, missing = appmod._lane_missing_spans(epub, out, 1, 0)
    assert spans == [] and banked == 3 and missing == 0


def test_harvest_target_naming(tmp_path):
    manifest = {'chapters': [{'slug': 'ch09', 'index': 9,
                              'title': 'ONE: The Irish Revolution 1916-23'}]}
    targets = FL._harvest_targets(manifest, tmp_path)
    assert targets['ch09'].name == '009_ONE The Irish Revolution 1916-23.mp3'
    assert ':' not in targets['ch09'].name  # illegal on Windows, pointless anywhere


def test_state_done_counts():
    state = {'completed': ['ch01'], 'progress': {'ch01': 73, 'ch02': 40}}
    done, completed = FL._state_done(state)
    assert done == 113 and completed == {'ch01'}
    assert FL._state_done({}) == (0, set())


# --- API surface -----------------------------------------------------------

def test_lanes_endpoint_never_500s(client):
    r = client.get('/api/lanes')
    assert r.status_code == 200
    data = r.get_json()
    assert set(data['lanes']) == set(LN.LANES)
    for lane, st in data['lanes'].items():
        assert {'configured', 'state', 'reason', 'checked_at'} <= set(st)
    assert 'fish_available' in data


def test_lanes_endpoint_honest_about_missing_sdk(client, monkeypatch):
    """With Lightning credentials but no SDK installed the lane reports the
    exact reason instead of pretending to work (or throwing a 500)."""
    monkeypatch.setenv('LIGHTNING_API_KEY', 'k')
    monkeypatch.setenv('LIGHTNING_USERNAME', 'u')
    LN._cache.clear()
    try:
        import lightning_sdk  # noqa: F401
        pytest.skip('lightning-sdk installed — honest-failure path not reachable')
    except ImportError:
        pass
    st = LN.lane_status('lightning')
    assert st['configured'] is True
    assert st['state'] == 'error' and 'not installed' in st['reason']


def test_job_creation_refuses_fish_off_lane(client, tmp_path):
    epub = tmp_path / 'book.epub'
    _make_epub(epub)
    r = client.post('/api/library/convert', json={
        'path': str(epub), 'voice': 'fish_cillian_irish', 'render_target': 'local'})
    assert r.status_code == 400
    assert 'lane' in r.get_json()['error'].lower()
    # And the old paid-GPU guard still holds for other targets.
    r = client.post('/api/library/convert', json={
        'path': str(epub), 'voice': 'uk_female_samuel_nano', 'render_target': 'vast'})
    assert r.status_code == 400


# --- the creation boundary: a queued job can never reach the paid lane -----

def _reset_health():
    appmod._ENGINE_HEALTH_CACHE['ts'] = 0
    appmod._ENGINE_HEALTH_CACHE['data'] = {}


def test_job_creation_refuses_paid_lane_from_auto(client, tmp_path, monkeypatch):
    """Only Lightning configured + no lane named -> the POST is refused.

    The refusal must name the action that authorises spending, and the job
    must never enter the queue (queueing is not authorization to spend).
    """
    _isolate_lane_creds(monkeypatch, tmp_path)
    monkeypatch.setenv('LIGHTNING_API_KEY', 'k')
    monkeypatch.setenv('LIGHTNING_USERNAME', 'u')
    monkeypatch.delenv('FISH_LANE', raising=False)
    LN._cache.clear()
    _reset_health()
    epub = tmp_path / 'book.epub'
    _make_epub(epub)
    r = client.post('/api/library/convert', json={
        'path': str(epub), 'voice': 'fish_cillian_irish', 'render_target': 'lane'})
    assert r.status_code == 400
    err = r.get_json()['error']
    assert 'paid' in err.lower() and 'lightning' in err.lower()
    _reset_health()


def test_job_creation_accepts_a_named_paid_lane_and_persists_it(client, tmp_path,
                                                                monkeypatch):
    """Naming the lane IS the authorization — and it must survive the save.

    The column is explicit in save_job's INSERT, so this also guards the
    silent-drop class (see test_job_roundtrip.py).
    """
    _isolate_lane_creds(monkeypatch, tmp_path)
    monkeypatch.setenv('LIGHTNING_API_KEY', 'k')
    monkeypatch.setenv('LIGHTNING_USERNAME', 'u')
    monkeypatch.delenv('FISH_LANE', raising=False)
    LN._cache.clear()
    _reset_health()
    epub = tmp_path / 'book.epub'
    _make_epub(epub)
    r = client.post('/api/library/convert', json={
        'path': str(epub), 'voice': 'fish_cillian_irish', 'render_target': 'lane',
        'lane': 'lightning'})
    assert r.status_code == 200, r.get_json()
    job_id = r.get_json()['job_id']
    try:
        assert (appmod.get_job(job_id) or {}).get('lane') == 'lightning'
    finally:
        with appmod.get_db() as conn:
            conn.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
    _reset_health()


def test_job_creation_refuses_nonsense_lane_combinations(client, tmp_path,
                                                         monkeypatch):
    epub = tmp_path / 'book.epub'
    _make_epub(epub)
    # A lane named on a non-lane render: refuse, don't silently drop it.
    # (Refused before the engine health check, so no credentials involved.)
    r = client.post('/api/library/convert', json={
        'path': str(epub), 'voice': 'uk_female_samuel_nano',
        'render_target': 'local', 'lane': 'colab'})
    assert r.status_code == 400 and 'lane' in r.get_json()['error'].lower()
    # A lane render for a non-fish engine: refuse at creation, not at start.
    r = client.post('/api/library/convert', json={
        'path': str(epub), 'voice': 'uk_female_samuel_nano',
        'render_target': 'lane'})
    assert r.status_code == 400 and 'fish' in r.get_json()['error'].lower()
    # An unknown lane name: refuse with the name, never fall through to auto.
    # One real lane credential so the fish health check passes first (a host
    # with no lanes at all would stop at the 409 instead — hermeticity).
    _isolate_lane_creds(monkeypatch, tmp_path)
    monkeypatch.setenv('LIGHTNING_API_KEY', 'k')
    monkeypatch.setenv('LIGHTNING_USERNAME', 'u')
    LN._cache.clear()
    _reset_health()
    r = client.post('/api/library/convert', json={
        'path': str(epub), 'voice': 'fish_cillian_irish',
        'render_target': 'lane', 'lane': 'vast'})
    assert r.status_code == 400 and 'unknown lane' in r.get_json()['error'].lower()
    _reset_health()


def test_batch_convert_refuses_fish_at_post(client):
    """Batch has no lane target, so a fish voice must never be queued there.

    Otherwise the tombstone fires only at job start — a queued job that could
    not start, which is the same class the single-book POST refuses.
    """
    r = client.post('/api/library/batch-convert', json={
        'paths': ['non_existent_book.epub'],
        'voice_option': 'fish_cillian_irish',
        'tts_engine_option': 'keep'})
    assert r.status_code == 400
    assert 'lane' in r.get_json()['error'].lower()
