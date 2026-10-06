"""Higgs chunking rules (pure - no GPU). Encodes Dave's 2026-10-05 listening verdicts."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import higgs_prep as hp  # noqa: E402


def S(text, para, quote=False):
    return {"text": text, "para": para, "quote": quote}


def test_heading_lines_become_one_chunk():
    sents = [S("Armed Struggle", 0), S("ONE", 1), S("THE IRISH REVOLUTION", 2),
             S("nineteen sixteen to twenty-three", 3),
             S("The Republic was declared at Easter.", 4)]
    ch = hp.build_chunks(sents)
    assert ch[0]["heading"] and ch[0]["sents"] == [0, 1, 2, 3]
    assert ch[0]["text"] == "Armed Struggle. ONE. THE IRISH REVOLUTION. nineteen sixteen to twenty-three."
    assert not ch[1]["heading"] and ch[1]["sents"] == [4]


def test_prose_sentences_are_not_headings():
    assert not hp.is_heading("It was a truly dramatic event.")
    assert not hp.is_heading("He said it was ‘finished.’")
    assert hp.is_heading("THE IRISH REVOLUTION")
    assert not hp.is_heading("A very long line that has no final punctuation but is clearly "
                             "running prose and not a heading at all really")


def test_chunks_never_cross_paragraphs_and_respect_word_ceiling():
    long = " ".join(["word"] * 30) + "."
    sents = [S(long, 0), S(long, 0), S(long, 0), S(long, 1), S(long, 1)]
    ch = hp.build_chunks(sents, max_words=70)
    assert [c["sents"] for c in ch] == [[0, 1], [2], [3, 4]]
    assert all(c["words"] <= 70 for c in ch)
    assert {c["para"] for c in ch if c["sents"] == [2]} == {0}


def test_overlong_sentence_is_split_at_clause_boundaries():
    clause = " ".join(["alpha"] * 40)
    text = f"{clause}; {clause}; {clause}."
    assert len(text.split()) > hp.HARD_MAX_WORDS
    ch = hp.build_chunks([S(text, 0)])
    assert len(ch) >= 2 and all(c["words"] <= hp.HARD_MAX_WORDS for c in ch)
    assert " ".join(c["text"] for c in ch).replace(";", "").split() == text.replace(";", "").split()


def test_every_sentence_is_covered_exactly_once_in_order():
    sents = [S("TITLE", 0), S("One two three four five six.", 1), S("Seven eight nine.", 1),
             S("A new paragraph here.", 2, True)]
    covered = [k for c in hp.build_chunks(sents) for k in c["sents"]]
    assert covered == [0, 1, 2, 3]


def test_tags_never_include_anger_or_shouting():
    sents = [S("He was furious.", 0), S("They remembered.", 0)]
    ch = hp.build_chunks(sents)[0]
    out = hp.apply_tags(sents, ch, {0: "anger", 1: "contemplation"})
    assert "anger" not in out and "<|emotion:contemplation|>They remembered." in out
    assert hp.apply_tags(sents, ch, {0: "shouting"}) == ch["text"]
    assert hp.apply_tags(sents, ch, None) == ch["text"]


def test_headings_and_split_chunks_are_never_tagged():
    sents = [S("ONE", 0), S("Prose follows here.", 1)]
    ch = hp.build_chunks(sents)
    assert hp.apply_tags(sents, ch[0], {0: "awe"}) == ch[0]["text"]


def test_gaps():
    a = {"para": 1, "heading": False}
    b = {"para": 1, "heading": False}
    c = {"para": 2, "heading": False}
    assert hp.gap_after(a, b) == 0.3 and hp.gap_after(a, c) == 0.5 and hp.gap_after(a, None) == 0.0


def test_real_armed_struggle_opening_matches_the_listened_passage():
    p = ROOT / "scratch" / "as_book_new" / "ch1.json"
    if not p.exists():
        return  # scratch payloads are not tracked; the unit tests above carry the rules
    sents = json.loads(p.read_text(encoding="utf-8"))["sents"]
    ch = hp.build_chunks(sents)
    assert ch[0]["heading"]
    assert max(c["words"] for c in ch) <= hp.HARD_MAX_WORDS


def test_matter_filter_drops_front_matter_and_cuts_everything_after_notes():
    import fish_bundle as fb
    titles = ["Copyright", "Contents", "Prologue", "An Abduction", "Albert's Daughters",
              "The Last Gun", "Acknowledgements", "A Note on Sources", "Notes", "Say-42",
              "Select Bibliography", "Index"]
    kept, skipped = fb.filter_matter([{"title": t} for t in titles])
    assert [c["title"] for c in kept] == ["Prologue", "An Abduction", "Albert's Daughters", "The Last Gun"]
    assert {s["title"] for s in skipped} >= {"Copyright", "Contents", "Notes", "Say-42", "Index"}


def test_matter_filter_is_conservative_about_real_chapters():
    import fish_bundle as fb
    kept, _ = fb.filter_matter([{"title": t} for t in
                                ["Preface", "ONE: The Irish Revolution", "Notes from a Small Island",
                                 "Indexing the Past", "Conclusion"]])
    assert len(kept) == 5, [c["title"] for c in kept]
    # a book that genuinely starts with Notes is not cut (needs >=3 narrative chapters first)
    kept, _ = fb.filter_matter([{"title": "Notes"}, {"title": "Chapter 1"}])
    assert [c["title"] for c in kept] == ["Chapter 1"]
    assert len(fb.filter_matter([{"title": "Notes"}, {"title": "Index"}], keep_matter=True)[0]) == 2


def test_chapter_text_drops_head_title_and_keeps_chapter_number():
    import fish_bundle as fb
    from as_prep import prep
    html = ('<html><head><title>Say-8</title><link href="x.css"/></head><body>'
            '<p class="chapter_number">1</p><h1 class="chapter_head"><a href="#">An Abduction</a></h1>'
            '<p class="open_para">Jean McConville was thirty-eight when she disappeared.</p>'
            '<p class="chapter_number">PROLOGUE</p></body></html>')
    text = fb.chapter_text(html)
    assert "Say-8" not in text and "Chapter 1" in text and "PROLOGUE" in text
    texts = [s["text"] for s in prep(text, {})]
    assert texts[0] == "Chapter one" and "An Abduction" in texts[1], texts
    ch = hp.build_chunks(prep(text, {}))
    assert ch[0]["heading"] and ch[0]["text"].startswith("Chapter one. An Abduction")
    # footnote-style standalone digits are still dropped
    assert "two" not in [s["text"].strip(". ").lower() for s in prep("Text here.\n\n2\n\nMore text follows.", {})]
