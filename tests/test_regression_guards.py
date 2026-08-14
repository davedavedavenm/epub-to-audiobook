"""Regression guards for the 2026-07-07 incident fixes (see OPERATIONS.md).

These are deliberate tripwires: if someone reverts or refactors away one of
the incident fixes, a test fails naming the incident it re-opens. Structural
assertions on the source are crude but honest — they encode invariants that
full integration tests (docker + DB + engines) can't cheaply cover.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'webapp' / 'app.py').read_text(encoding='utf-8')
CB_SERVER = (ROOT / 'chatterbox' / 'server.py').read_text(encoding='utf-8')
TADA_SERVER = (ROOT / 'tada' / 'server.py').read_text(encoding='utf-8')
COMPOSE = (ROOT / 'docker-compose.yml').read_text(encoding='utf-8')
DEPLOY = (ROOT / 'scripts' / 'deploy.sh').read_text(encoding='utf-8')
WORKER = (ROOT / 'webapp' / 'worker.py').read_text(encoding='utf-8')
GPU_MANAGER = (ROOT / 'webapp' / 'gpu_manager.py').read_text(encoding='utf-8')
AGENT_RULES = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
DECISIONS = (ROOT / 'DECISIONS.md').read_text(encoding='utf-8')
INDEX = (ROOT / 'webapp' / 'templates' / 'index.html').read_text(encoding='utf-8')


# --- incident 2026-07-07a: retries must actually run ---

def test_retry_clears_container_name():
    """Job d67c50ac: stale container_name aborted every auto-retry.

    Applies to EVERY path that requeues a job (auto-retry, orphan recovery,
    bulk retry-failed): a stale container_name trips the duplicate-start
    guard and silently no-ops the retry.
    """
    blocks = re.findall(r"UPDATE jobs\s+SET status\s?=\s?'queued',.*?WHERE id\s?=\s?\?", APP, re.S)
    assert len(blocks) >= 3, f"expected >=3 requeue UPDATEs, found {len(blocks)}"
    for b in blocks:
        assert re.search(r"container_name\s?=\s?NULL", b), (
            "a requeue path does not clear container_name — re-opens "
            "incident 2026-07-07a:\n" + b[:200])


def test_job_spawns_respect_queue_runner_flag():
    """The webapp must not race the worker (QUEUE_RUNNER_ENABLED=0)."""
    assert 'threading.Thread(target=start_next_queued_job' not in APP, \
        "direct start_next_queued_job spawn bypasses QUEUE_RUNNER_ENABLED"


# --- incident 2026-07-07b: engine OOM death-spiral ---

def test_engine_servers_serialize_generation():
    for name, src in [('chatterbox', CB_SERVER), ('tada', TADA_SERVER)]:
        assert '_GEN_LOCK' in src and 'with _GEN_LOCK' in src, \
            f"{name} server generation no longer serialized — re-opens OOM incident 2026-07-07b"
        assert 'inference_mode' in src, f"{name} server lost inference_mode"


def test_engine_containers_have_memory_caps():
    for svc in ('chatterbox-tts', 'tada-tts'):
        block = COMPOSE.split(f'{svc}:', 1)[1][:800]
        assert 'mem_limit' in block, \
            f"{svc} lost its mem_limit — kernel OOM kills return (incident 2026-07-07b)"


def test_startup_voice_cache_is_throttled():
    """Incident 2026-07-18: startup preview generation loaded TADA without a job
    and OOM-burst the box.

    UPDATED 2026-07-25. This guard used to demand the feature default to OFF,
    on a 15 GiB NUC. Zorin was upgraded on 2026-07-20 (i5-12400 / 31 GB) and
    every voice previewing instantly is a product requirement, so caching now
    defaults ON. What actually prevented that incident was never the default —
    it was the THROTTLE (wait for a quiet box, pause between voices) plus the
    per-engine mem_limits. So guard those instead: they are the mechanism.

    If you turn caching on for a SMALL host, set VOICE_CACHE_ON_START=0 in .env.
    """
    # The throttle must survive: without it the loop saturates the machine and
    # engines fail their own healthchecks while merely being too busy to answer.
    assert 'VOICE_CACHE_MAX_LOAD' in APP, \
        "voice caching lost its load throttle — reopens the Jul-18 OOM burst"
    assert 'getloadavg' in APP, \
        "voice caching no longer waits for a quiet box before each voice"
    assert 'VOICE_CACHE_DELAY' in APP, \
        "voice caching lost the pause between voices"
    # And it must stay switchable, so a constrained host can still opt out.
    assert 'VOICE_CACHE_ON_START' in COMPOSE, \
        "VOICE_CACHE_ON_START is no longer configurable from Compose"


def test_heavy_engine_profiles_are_deploy_opt_in():
    """The HEAVY clone engines must not auto-start on every deploy.

    Fixed 2026-07-25: this used to inspect the `docker compose ... up -d` line,
    which only ever contains "${PROFILE_ARGS[@]}" — the profile names live in
    the array built above it. The assertion could therefore never fail, so it
    guarded nothing. Check the array instead.

    chatterbox-nano IS allowed to auto-start: it carries the default voice, and
    at 110M params / RTF 0.87 it is light. Turbo and TADA stay opt-in because
    they are heavy and slow.
    """
    profile_lines = '\n'.join(ln for ln in DEPLOY.splitlines() if 'PROFILE_ARGS' in ln)
    unconditional = '\n'.join(ln for ln in profile_lines.splitlines() if 'PROFILE_ARGS=(' in ln)
    assert not re.search(r'--profile chatterbox(?!-nano)', unconditional), \
        "deploy unconditionally starts Chatterbox TURBO — it is heavy, keep it opt-in"
    assert '--profile tada' not in unconditional, \
        "deploy unconditionally starts TADA — it is heavy, keep it opt-in"
    assert 'ENABLE_CHATTERBOX_PROFILE' in DEPLOY and 'ENABLE_TADA_PROFILE' in DEPLOY, \
        "heavy engine profiles lost their explicit deploy opt-ins"


def test_slow_engine_timeout_floor():
    assert 'SLOW_ENGINE_MIN_TIMEOUT' in APP or 'Timeout floored' in APP, \
        "slow-engine timeout floor removed — full books will time out again"


def test_metrics_only_from_full_books():
    assert 'partial-range jobs pollute' in APP, \
        "conversion metrics gating removed — ETA pollution returns"


# --- GPU images (incident 2026-07-06/07c) ---

def test_engine_images_gpu_capable():
    for eng in ('chatterbox', 'tada'):
        df = (ROOT / eng / 'Dockerfile').read_text(encoding='utf-8')
        assert 'NVIDIA_VISIBLE_DEVICES' in df, f"{eng} image lost NVIDIA env — silent CPU on GPU hosts"
        assert 'download.pytorch.org/whl/cu' in df, f"{eng} image lost explicit CUDA torch"


def test_tada_torch_stack_pinned():
    """Incident 2026-07-08d: tada's `torch --index-url cu124` was UNPINNED, so
    the hume-tada install (torch>=2.7 + unpinned torchaudio/torchvision)
    re-resolved the whole stack from PyPI to the cu130 build, which needs an
    R580+ driver and silently ran CPU on GPU hosts. The torch stack must be
    version-pinned AND include pinned torchaudio+torchvision from the CUDA
    index, so the requirements install can't drag the default build back in."""
    df = (ROOT / 'tada' / 'Dockerfile').read_text(encoding='utf-8')
    assert re.search(r'torch==\d', df), "tada torch is not version-pinned — cu130 drift returns (2026-07-08d)"
    assert re.search(r'torchaudio==\d', df) and re.search(r'torchvision==\d', df), \
        "tada must pin torchaudio+torchvision too, else requirements re-pulls the cu130 stack (2026-07-08d)"
    # cu130 needs R580+ (rare); the pin must target an older, broadly-supported CUDA
    assert '/whl/cu130' not in df, "tada pinned to cu130 — needs R580+ driver, silent-CPU on most hosts"


def test_chatterbox_kaggle_kernel_pins_cuda_torch():
    """The Chatterbox GPU kernel must install a CUDA-pinned torch BEFORE
    chatterbox-tts, or the pip resolver can pull a CPU/mismatched wheel and the
    kernel silently runs on CPU (the TADA silent-CPU class, 2026-07-08d). It
    must also keep the CUDA-availability gate that refuses a CPU run, and pin
    setuptools<81 (perth watermarker imports the removed pkg_resources)."""
    k = (ROOT / 'scripts' / 'kaggle' / 'run_chatterbox.py').read_text(encoding='utf-8')
    assert re.search(r'torch==\d.*cu\d', k, re.S), "chatterbox kernel torch not CUDA-pinned — silent-CPU risk"
    # Order the actual pip-install INVOCATIONS (ignore prose in comments): the
    # CUDA torch install must precede the chatterbox-tts install so pip finds
    # torch satisfied and doesn't re-resolve to a CPU/mismatched wheel.
    code_lines = [l for l in k.splitlines() if not l.lstrip().startswith('#')]
    torch_line = next((i for i, l in enumerate(code_lines) if 'torch==' in l), None)
    cbx_line = next((i for i, l in enumerate(code_lines) if 'chatterbox-tts' in l), None)
    assert torch_line is not None and cbx_line is not None, "couldn't locate the pip install lines"
    assert torch_line < cbx_line, "CUDA torch must be installed BEFORE chatterbox-tts, else it re-resolves"
    assert 'refusing CPU run' in k or 'cuda_available' in k, "kernel dropped the GPU gate — could run CPU unnoticed"
    assert re.search(r'torchvision==\d', k), "chatterbox kernel must pin torchvision too (torchvision::nms mismatch, 2026-07-10)"
    assert 'setuptools<81' in k, "perth watermarker needs setuptools<81 (pkg_resources removed in 81+)"


def test_health_reports_cuda():
    for name, src in [('chatterbox', CB_SERVER), ('tada', TADA_SERVER)]:
        assert 'cuda_available' in src, f"{name} /health no longer reports CUDA — GPU issues undiagnosable"


# --- engine health lockdown ---

def test_engine_offline_queue_gate():
    assert 'engine is offline' in APP and 'check_engines_health' in APP, \
        "409 engine-offline gate removed — jobs can queue into dead engines again"


# --- GPU cost safety ---

def test_gpu_render_gate_default_off():
    assert "gpu_render_enabled" in APP and "os.environ.get('GPU_RENDER_ENABLED', '0')" in APP.replace('"', "'"), \
        "GPU render gate weakened — paid GPU no longer default-off"
    settings_block = APP[APP.index("@app.route('/api/settings'"):
                         APP.index("@app.route('/api/settings/pronunciations")]
    assert "'GPU_RENDER_ENABLED'" not in settings_block, \
        "unauthenticated Settings API can arm paid GPU provisioning"


def test_queue_length_cannot_provision_paid_gpu():
    """Incident: queued books automatically crossed a Vast threshold.

    A queue is work to do, never authorization to spend. Paid provisioning is
    manual and the manager itself must fail closed if a future caller forgets
    the authorization argument.
    """
    assert '_gpu.scale_up' not in WORKER, \
        "worker can still rent a paid GPU from queue state"
    assert 'AUTOSCALE_ENABLED = False' in GPU_MANAGER, \
        "legacy AUTOSCALE_ENABLED can become active again"
    assert 'AUTOSCALE_ENABLED=' not in COMPOSE, \
        "Compose still exposes the retired queue autoscale switch"
    assert 'def scale_up(self, *, authorized: bool = False)' in GPU_MANAGER, \
        "Vast manager no longer fails closed without explicit authorization"
    assert 'raw.githubusercontent.com/vast-ai' not in GPU_MANAGER, \
        "paid path downloads an unpinned billing CLI at runtime"
    requirements = (ROOT / 'webapp' / 'requirements.txt').read_text(encoding='utf-8')
    assert 'vastai==' in requirements, \
        "official Vast CLI is not version-pinned in the application image"
    assert 'requests==2.33.0' in requirements, \
        "requests pin is incompatible with the pinned vastai 1.5.4 package"
    assert "render_target not in ('local', 'kaggle')" in APP, \
        "job API accepts a paid render target from ordinary queueing"


def test_official_documentation_gate_is_mandatory():
    """Agents must RTFM before experimenting with external systems."""
    assert 'Authoritative-Source Gate' in AGENT_RULES
    assert 'must read the current official documentation' in AGENT_RULES
    assert 'Official documentation before experimentation' in DECISIONS


def test_startup_preview_cache_cannot_call_paid_engines():
    """Background maintenance may spend CPU, never money or internet quota."""
    cache_block = APP[APP.index('def _cache_all_voices_background'):
                      APP.index('def background_startup')]
    for engine in ('kokoro', 'chatterbox', 'chatterbox_nano', 'tada', 'pocket', 'kitten'):
        assert f"'{engine}'" in cache_block
    assert "'polly'" not in cache_block
    assert "'inworld'" not in cache_block
    assert "'edge'" not in cache_block
    assert 'health.get' in cache_block


def test_cpu_candidates_are_opt_in_cpu_only_and_cached_before_play():
    for service, profile in (('pocket-tts:', 'pocket'), ('kitten-tts:', 'kitten')):
        assert service in COMPOSE
        assert f'- {profile}' in COMPOSE
    assert COMPOSE.count('CUDA_VISIBLE_DEVICES=') >= 2
    assert 'ENABLE_POCKET_PROFILE' in DEPLOY
    assert 'ENABLE_KITTEN_PROFILE' in DEPLOY
    assert "'pocket', 'kitten'" in APP


def test_every_converter_command_carries_engine_text_profile():
    assert APP.count("'--text-profile', text_profile_for_engine(tts_engine)") == 2
    converter = (ROOT / 'scripts' / 'convert_book.py').read_text(encoding='utf-8')
    assert "choices=('auto', 'modern', 'explicit', 'legacy')" in converter
    assert "_TEXT_PROFILE == 'legacy'" in converter


def test_play_button_never_starts_cold_voice_synthesis():
    """Auditions are an immediate persisted-cache read, never a hidden render."""
    route = APP[APP.index("@app.route('/api/preview/<voice_id>')"):
                APP.index("@app.route('/api/convert'")]
    assert 'get_voice_preview(' not in route
    assert '_preview_is_cached(voice_id)' in route
    assert "'preview_cached': _preview_is_cached(voice_id)" in APP
    assert 'v.preview_cached === true' in INDEX


def test_vibevoice_uses_listening_selected_cfg_two():
    assert 'VIBEVOICE_CFG_SCALE=${VIBEVOICE_CFG_SCALE:-2.0}' in COMPOSE


def test_unknown_engine_cost_is_not_reported_as_free():
    """Missing paid pricing must be visible, never silently rounded to $0."""
    assert "if engine not in PRICING:" in APP
    assert "return None" in APP[APP.index('def calculate_price_estimate'):
                                APP.index('# ============ Orphan Job Detection')]
    assert "'unknown_not_free'" in APP


# --- incident 2026-07-08: cross-process recovery race ---

def test_recovery_has_cross_process_lock():
    """Resume API (webapp) and orphan cleanup (worker) raced two recovery
    threads; in-memory guards cannot work across processes."""
    assert 'recovery_lock_' in APP,         "cross-process recovery DB lock removed — re-opens 2026-07-08 recovery race"


# --- audio quality fixes 2026-07-08 ---

def test_dashes_not_forced_to_commas():
    """Dash-heavy prose produced constant pauses when every dash became a comma."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('tp', ROOT / 'webapp' / 'tts_preprocess.py')
    tp = importlib.util.module_from_spec(spec); spec.loader.exec_module(tp)
    out = tp.normalize_text_for_tts("Apple — the company — grew.")
    assert ', the company ,' not in out, "em-dash still forced to comma (pause regression 2026-07-08)"


def test_tada_first_word_leadin_trim():
    assert '_trim_leadin' in TADA_SERVER and 'LEADIN' in TADA_SERVER,         "TADA first-word lead-in trim removed — cold-start garble returns"


def test_qa_layer2_wired():
    """Structural ASR remains reachable; it is not a quality/ranking oracle.

    Production auto-rerender is inactive. The retained value is detecting
    missing, repeated, truncated or grossly mismatched audio for human review.
    """
    qa = (ROOT / 'webapp' / 'qa_asr.py').read_text(encoding='utf-8')
    assert 'def diff_report' in qa and 'def verify_chapter' in qa, "QA Layer 2 core removed (#7)"
    cb = (ROOT / 'scripts' / 'convert_book.py').read_text(encoding='utf-8')
    assert '--qa' in cb, "convert_book lost the --qa hook — QA Layer 2 unreachable (#7)"
    assert '--auto-rerender' not in cb and 'Auto-rerendering' not in cb, \
        "ASR WER can still replace audio without Dave listening"


def test_preprocess_reads_engine_from_job_not_unset_local():
    """convert_book's preprocessing runs BEFORE the local `tts_engine` is
    assigned; it must read the engine from the job. Referencing the not-yet-set
    local threw at runtime and silently fell back to raw text — none of the
    modern-contract preprocessing applied (caught on the real worker path,
    2026-07-08)."""
    assert '_modern = tts_engine in' not in APP, \
        "preprocess block references tts_engine before it is assigned (use-before-assign regression)"
    assert 'modern=_modern' in APP, "modern-contract preprocessing no longer wired into convert_book"


def test_preprocessing_llm_provider_chain():
    """#6: the narration profile must degrade through providers to a seed floor,
    never straight to {} (which drops all pronunciation help)."""
    lm = (ROOT / 'webapp' / 'llm_metadata.py').read_text(encoding='utf-8')
    assert '_call_llm_json_chain' in lm and '_fallback_settings' in lm, "LLM provider chain removed (#6)"
    assert 'SEED_RULES' in lm and '_seed_profile' in lm, "seed-rule floor removed (#6)"


def test_recovery_frees_slot_when_container_missing():
    """#14: a 'converting' job whose container is gone after a restart must be
    failed (freeing the single MAX_CONCURRENT slot), not left stuck holding the
    queue. resume_inflight_jobs must have the else-branch that fails it."""
    assert "container missing after worker restart" in APP, \
        "recovery no longer fails zombie jobs — queue-jam regression (#14)"


def test_conversion_engine_failover_wired():
    """#6: a dead engine must be able to fail over to a healthy one instead of
    always hard-stranding a book."""
    assert 'pick_engine_with_fallback' in APP and '_ENGINE_FALLBACK_ORDER' in APP, \
        "conversion engine failover helper removed (#6)"
    assert 'allow_engine_fallback' in APP, "engine failover not wired into the queue gate (#6)"


def test_rejected_piper_is_not_an_automatic_fallback():
    """A healthy endpoint is not enough: Piper failed the controlled listening
    A/B and must never silently replace a quality-approved engine."""
    assert "_ENGINE_FALLBACK_ORDER = ['tada', 'chatterbox', 'kokoro']" in APP
    assert 'PROFILE_ARGS=(--profile chatterbox-nano)' in DEPLOY
    assert 'ENABLE_PIPER_PROFILE' in DEPLOY


def _load_tp():
    import importlib.util
    spec = importlib.util.spec_from_file_location('tp2', ROOT / 'webapp' / 'tts_preprocess.py')
    tp = importlib.util.module_from_spec(spec); spec.loader.exec_module(tp)
    return tp


def test_years_are_spelled_for_every_engine():
    """REVERSED 2026-07-14 by an ear-test A/B (#26).

    This guard used to assert the opposite: modern engines had to keep RAW years,
    because spelling '1976' made them PAUSE before the last digit ('1976' heard as
    '1970...6', incident 2026-07-08).

    That diagnosis was wrong. The pause came from the COMMA num2words inserts into
    spelled numbers ("three thousand, four hundred") — engines read a comma as a
    pause. With the comma stripped, Dave A/B'd raw '1997' vs 'nineteen ninety-seven'
    on chatterbox and judged the SPELLED form better. The original defect was the
    comma; the year-spelling ban was collateral damage.

    So: years are spelled for EVERY engine. Currency/percent/large ints are still
    raw for modern — NOT yet judged by ear, do not extend without an A/B (#26).

    AMENDED 2026-07-27: this guard asserted `'seventy-six' in out`, pinning the
    HYPHEN num2words happens to emit. That is a separator, not the requirement.
    The requirement is that a year is spoken as words and never leaks as raw
    digits, and that still holds exactly. Modern engines now also get the
    intra-word hyphen removed ("ninety seven"), because they read such a hyphen
    as a pause — the daisy-chain defect. Legacy output is unchanged.
    """
    tp = _load_tp()
    for modern in (True, False):
        out = tp.normalize_text_for_tts("founded in 1976, returned in 1997.", modern=modern)
        sep = ' ' if modern else '-'
        assert f'seventy{sep}six' in out and f'ninety{sep}seven' in out, \
            f"year spelling broken (modern={modern}): {out}"
        assert '1976' not in out, f"raw year leaked (modern={modern}): {out}"

    # The comma that caused the original artifact must never come back.
    big = tp.normalize_text_for_tts("3,400 workers", modern=False)
    assert 'three thousand four hundred' in big and 'thousand,' not in big, big


def test_modern_contract_skips_all_plain_number_spelling():
    """MODERN-ENGINE CONTRACT: modern engines read plain numbers/years/decades/
    large integers natively. Every plain-number spelling transform must sit
    under the single `if not modern:` guard so we stop discovering these one
    incident at a time (2026-07-08). Symbol/abbrev expansion still applies.

    AMENDED 2026-07-27, narrowly: the comma-number case asserted the literal
    "2,905", which pinned the SEPARATOR as well as the digits. A thousands
    comma is not a number — it is a comma, and this codebase's own finding is
    that engines read a comma as a PAUSE. The 2026-07-08 fix stripped the comma
    num2words emits and never the one already in the source, so "2,905" still
    read as "two thousand… nine hundred" on the engines that render every book.
    The digits are still asserted, which is what the contract is actually about;
    only the separator is now allowed to go."""
    tp = _load_tp()
    cases = {
        "It was the 1990s.":        ('1990s', 'nineties'),   # decade
        "a crowd of 2,905 people":  ('2905', 'nine hundred'),  # digits kept, comma dropped
        "the figure hit 45000":     ('45000', 'forty-five thousand'),  # large int
    }
    for text, (keep, must_not) in cases.items():
        out = tp.normalize_text_for_tts(text, modern=True)
        assert keep in out and must_not not in out, (
            f"modern engine spelled a plain number ({text!r} -> {out!r}) — "
            "re-opens the mid-number pause artifact class (2026-07-08)")
    # Revised 2026-07-09 (minimal-for-modern): modern KEEPS only acronym
    # letter-spacing (U.S.->U S, which genuinely helps) but SKIPS %/$/1st and
    # word-abbrev expansion — it reads those natively, and blind expansion
    # misfired ("Main St."->"Main Saint", "Coo-per-TEE-no").
    sym = tp.normalize_text_for_tts("the U.S. had 50% and Dr. Lee left on 1st", modern=True)
    assert 'U S' in sym, "modern dropped acronym letter-spacing (U.S.->U S helps)"
    assert 'percent' not in sym and 'Doctor' not in sym and 'first' not in sym, \
        "modern still expanding %/Dr./ordinals — should read them natively (minimal contract)"
    # legacy engines still get the full expansion
    leg = tp.normalize_text_for_tts("about 50% and Dr. Lee", modern=False)
    assert 'percent' in leg and 'Doctor' in leg, "legacy expansion broken"


def test_modern_keeps_acronym_letter_spacing_only():
    """Modern engines misread undotted initialisms ("CEO" heard as "see you",
    2026-07-10) — acronym LETTER-SPACING lexicon rules are the one class that
    must still apply for modern. Phonetic respellings stay banned."""
    tp = _load_tp()
    lex = {"CEO": "C E O", "IPO": "I P O", "Beijing": "Bay-JING"}
    out = tp.normalize_text_for_tts("The CEO priced the IPO in Beijing.", lexicon=lex, modern=True)
    assert 'C E O' in out and 'I P O' in out, "acronym letter-spacing dropped for modern ('see you' regression)"
    assert 'Bay-JING' not in out and 'Beijing' in out, "phonetic respelling leaked into modern"


def test_modern_skips_phonetic_lexicon():
    """Modern engines read Beijing/Cupertino natively; the phonetic respelling
    lexicon ("Bay-JING","Coo-per-TEE-no") makes them read broken syllables
    ("bay...zhing"). Modern must SKIP the lexicon (Dave, 2026-07-09)."""
    tp = _load_tp()
    lex = {"Beijing": "Bay-JING", "Cupertino": "Coo-per-TEE-no", "iPhones": "eye-phones"}
    out = tp.normalize_text_for_tts("Broken iPhones in Beijing near Cupertino.", lexicon=lex, modern=True)
    assert 'Bay-JING' not in out and 'Coo-per-TEE-no' not in out and 'eye-phones' not in out, \
        "modern engine applied phonetic respelling — re-opens the 'bay...zhing' breakage"
    assert 'Beijing' in out and 'Cupertino' in out and 'iPhones' in out
    # legacy engines (Kokoro/Piper) still get the respelling — they need it
    leg = tp.normalize_text_for_tts("We flew to Beijing.", lexicon=lex, modern=False)
    assert 'Bay-JING' in leg, "legacy lexicon respelling broken"


def test_no_local_import_shadows_an_earlier_use():
    """A local `import x` makes x local to the WHOLE function, so any use of x
    EARLIER in that function is unbound at runtime.

    copy_to_audiobookshelf had `import shlex` twice while shlex was also a
    module-level import. Ruff's F401 autofix removed the first as redundant —
    correct in isolation, fatal in combination: the surviving local import still
    made the name function-local, so the earlier shlex.quote() had nothing bound
    and EVERY Audiobookshelf sync died with "cannot access free variable
    'shlex'" (2026-07-25). No unit test touched that path.

    Only the genuinely broken shape is flagged: a local import of a
    module-level name that the function already used above it. Late-but-unused-
    before imports are a style choice, not a bug.
    """
    import ast
    src = (ROOT / 'webapp' / 'app.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    module_names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                module_names.add((a.asname or a.name).split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                module_names.add(a.asname or a.name)

    offenders = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        local_imports = {}
        for node in ast.walk(fn):
            if isinstance(node, ast.Import):
                for a in node.names:
                    nm = (a.asname or a.name).split('.')[0]
                    if nm in module_names:
                        local_imports.setdefault(nm, node.lineno)
        if not local_imports:
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                imp_line = local_imports.get(node.id)
                if imp_line and node.lineno < imp_line:
                    offenders.append(
                        f"{fn.name}(): uses '{node.id}' at line {node.lineno} but "
                        f"imports it locally at line {imp_line}")
    assert not offenders, (
        "a function-local import shadows the module-level name for the WHOLE "
        "function, leaving earlier uses unbound at runtime: " + "; ".join(sorted(set(offenders))))


def test_single_completion_path():
    """Every render path must finish through _gate_and_sync.

    The completion sequence (quality gate -> M4B -> ABS sync -> final status)
    was re-implemented inline in THREE places: the local render, the recovery
    path, and the shared helper. So post-processing added to the helper silently
    skipped the two busiest paths — the M4B shipped late on local renders and
    not at all on recovered ones (2026-07-25).

    presync_quality_gate is the tell: if it is called anywhere but inside
    _gate_and_sync, someone has grown a second completion path again.
    """
    callers = [ln for ln in APP.splitlines()
               if 'presync_quality_gate(' in ln and 'def presync_quality_gate' not in ln]
    assert len(callers) == 1, (
        "the completion sequence has been duplicated again — presync_quality_gate "
        "should only be called by _gate_and_sync, found:\n  " + "\n  ".join(callers))
