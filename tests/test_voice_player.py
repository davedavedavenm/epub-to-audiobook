"""Regression guards for the persistent voice audition player (#45).

The UI is intentionally a single HTML document, so these tests guard its
structural contract: one audio element outside the replaceable tab panels and
one controller used by every audition entry point.
"""

from pathlib import Path

from bs4 import BeautifulSoup


HTML_PATH = Path(__file__).resolve().parents[1] / "webapp" / "templates" / "index.html"
HTML = HTML_PATH.read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    """Return a JavaScript function body using balanced braces."""
    marker = f"function {name}("
    start = HTML.index(marker)
    brace = HTML.index("{", start)
    depth = 0
    for index in range(brace, len(HTML)):
        if HTML[index] == "{":
            depth += 1
        elif HTML[index] == "}":
            depth -= 1
            if depth == 0:
                return HTML[start : index + 1]
    raise AssertionError(f"unclosed JavaScript function: {name}")


def test_one_global_audio_element_lives_outside_tabs():
    soup = BeautifulSoup(HTML, "html.parser")
    audio = soup.find_all("audio")
    assert len(audio) == 1, "voice auditions can overlap when they own separate audio elements"
    assert audio[0].get("id") == "preview-audio"
    assert audio[0].find_parent(class_="tab-panel") is None, (
        "the audition audio element will be destroyed or hidden with tab content"
    )
    player = soup.find(id="voice-player")
    assert player is not None and player.find_parent(class_="tab-panel") is None


def test_every_audition_path_uses_the_global_controller():
    workspace = _function_source("previewWorkspaceVoice")
    voice_card = _function_source("playVoicePreview")
    comparison = _function_source("playComparisonPreview")
    assert "requestVoicePreview(voiceId, btn)" in workspace
    assert "requestVoicePreview(voiceId, btn)" in voice_card
    assert "requestVoicePreview(prepared.voiceId, btn, prepared.blob)" in comparison
    assert "compare-audio" not in HTML


def test_tab_navigation_cannot_pause_or_reset_audition():
    switch_tab = _function_source("switchTab")
    assert "preview-audio" not in switch_tab
    assert ".pause(" not in switch_tab
    assert "currentTime" not in switch_tab
    assert "syncPreviewUi();" in _function_source("renderVoices"), (
        "returning to the re-rendered Voices tab must restore the active card state"
    )


def test_pause_and_resume_preserve_current_position():
    toggle = _function_source("toggleGlobalPreview")
    request = _function_source("requestVoicePreview")
    assert "if (!audio.paused) { audio.pause(); return; }" in toggle
    assert "audio.currentTime = 0" in toggle and "audio.ended" in toggle, (
        "position may only reset when replaying an ended sample"
    )
    same_voice_branch = request[request.index("if (speakingVoiceId === voiceId") :]
    assert "toggleGlobalPreview()" in same_voice_branch
    assert "currentTime = 0" not in same_voice_branch.split("const serial", 1)[0], (
        "clicking the paused voice must resume it instead of restarting"
    )


def test_player_exposes_accessible_synchronised_states():
    soup = BeautifulSoup(HTML, "html.parser")
    player = soup.find(id="voice-player")
    status = soup.find(id="voice-player-state")
    toggle = soup.find(id="voice-player-toggle")
    seek = soup.find(id="voice-player-seek")
    assert player.get("aria-label") == "Voice sample player"
    assert status.get("role") == "status" and status.get("aria-live") == "polite"
    assert toggle.get("aria-label")
    assert seek.get("aria-label")
    bind = _function_source("bindPreviewEvents")
    for event in ("play", "pause", "ended", "timeupdate", "loadedmetadata"):
        assert f"addEventListener('{event}'" in bind

