"""summarize_patterns: recurring ASR/narration faults become one line each."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webapp"))
import qa_asr  # noqa: E402


def test_bracket_word_drop_shows_up_as_a_recurring_pattern():
    src = ("before easter week was finished i had changed. "
           "in the easter rising he fought. after easter week they left. "
           "the cat sat on the mat.")
    heard = ("before week was finished i had changed. "
             "in the rising he fought. after week they left. "
             "the cat sat on the mat.")
    rep = qa_asr.diff_report(src, heard)
    pats = qa_asr.summarize_patterns(rep["divergences"])
    top = pats[0]
    assert top["kind"] == "dropped" and top["key"] == "easter" and top["count"] == 3, pats


def test_numeral_readbacks_are_already_normalised_away():
    rep = qa_asr.diff_report("in december nineteen sixty nine it began", "in december 1969 it began")
    assert qa_asr.summarize_patterns(rep["divergences"]) == []


def test_empty_and_top_limit():
    assert qa_asr.summarize_patterns([]) == []
    divs = [{"type": "drop", "source": [f"w{i}"], "heard": [], "context": ""} for i in range(30)]
    assert len(qa_asr.summarize_patterns(divs, top=5)) == 5
