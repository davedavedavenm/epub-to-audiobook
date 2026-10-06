"""book_preflight: each defect found by hand on Say Nothing / Armed Struggle is a rule."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import book_preflight as bp  # noqa: E402

PROSE = ("The group met in the back room of the pub and argued for hours about what should be done "
         "next, while outside the rain came down on the empty street. ") * 3


def book(chapters, engine="higgs"):
    """chapters: [(title, [sentences])] -> (manifest, payloads)"""
    man = {"engine": engine, "chapters": []}
    pay = {}
    for i, (title, sents) in enumerate(chapters, 1):
        slug = f"ch{i:02d}"
        sd = [{"text": t, "para": j, "quote": False} for j, t in enumerate(sents)]
        pay[slug] = {"slug": slug, "title": title, "sents": sd,
                     "chunks": [{"text": " ".join(sents[:2]), "words": 40, "sents": [0]}]}
        man["chapters"].append({"slug": slug, "title": title, "words": sum(len(t.split()) for t in sents)})
    return man, pay


def good(n=6):
    return book([(f"Chapter {i}", [f"Chapter {i}.", PROSE] + [PROSE] * 12) for i in range(1, n + 1)])


def rules(rep, kind):
    return {x["rule"] for x in rep[kind]}


def test_clean_book_passes_and_estimates_cost():
    rep = bp.audit(*good())
    assert rep["ok"], rep
    assert rep["info"]["audio_hours"] > 0 and rep["info"]["colab_units"] > 0
    assert "PASS" in bp.format_report(rep)


def test_leaked_filename_is_refused():          # "Say-eight. An Abduction."
    man, pay = good()
    pay["ch01"]["chunks"][0]["text"] = "Say-8. An Abduction."
    assert "leaked-filename" in rules(bp.audit(man, pay), "errors")


def test_duplicate_chapters_are_refused():      # the untitled 26k-word duplicate
    man, pay = good()
    pay["ch03"]["sents"] = [dict(s) for s in pay["ch02"]["sents"]]
    assert "duplicate" in rules(bp.audit(man, pay), "errors")


def test_matter_in_body_is_refused():
    man, pay = good()
    man["chapters"][2]["title"] = "Notes and References"
    assert "matter-in-body" in rules(bp.audit(man, pay), "errors")


def test_empty_and_tiny_books_are_refused():
    assert "no-chapters" in rules(bp.audit({"chapters": []}, {}), "errors")
    man, pay = book([("Chapter 1", ["Short."])])
    assert "tiny-book" in rules(bp.audit(man, pay), "errors")


def test_junk_heavy_is_refused_but_a_few_junk_sentences_only_warn():
    man, pay = book([(f"Chapter {i}", [f"{PROSE} Part {i}-{k}." for k in range(40)]) for i in range(1, 7)])  # 240 sentences
    junk = "Photo credit (Jacqueline Arzt/AP/REX/Shutterstock)"
    pay["ch01"]["sents"][2]["text"] = junk
    rep = bp.audit(man, pay)
    assert rep["ok"] and "junk-sentences" in rules(rep, "warnings")
    for c in pay.values():
        for s in c["sents"]:
            s["text"] = "Visit www.example.com now"
    assert "junk-heavy" in rules(bp.audit(man, pay), "errors")


def test_digits_giant_and_tiny_chapters_warn():
    man, pay = good(8)
    pay["ch02"]["sents"][3]["text"] = "He lived at number 12 for years."
    pay["ch03"]["sents"] = pay["ch03"]["sents"] * 8
    man["chapters"][2]["words"] *= 8
    man["chapters"][4]["words"] = 90
    man["chapters"][4]["title"] = "A Short Interlude"
    w = rules(bp.audit(man, pay), "warnings")
    assert {"digits", "giant-chapter", "tiny-chapter"} <= w


def test_short_prologue_is_not_flagged():
    man, pay = good()
    man["chapters"][0]["words"] = 90
    man["chapters"][0]["title"] = "Prologue"
    assert "tiny-chapter" not in rules(bp.audit(man, pay), "warnings")


def test_say_nothing_and_armed_struggle_bundles_would_pass_but_the_old_bugs_would_not():
    """The three real failures, replayed: leaked <title>, dropped chapters, notes kept as a chapter."""
    man, pay = good()
    pay["ch01"]["chunks"][0]["text"] = "index_split_013. Preface."
    man["chapters"][1]["title"] = "Index"
    rep = bp.audit(man, pay)
    assert not rep["ok"] and {"leaked-filename", "matter-in-body"} <= rules(rep, "errors")


def test_imprint_page_in_the_first_chapters_is_refused():
    """The webapp-path Armed Struggle failure: copyright page kept as chapter 2."""
    man, pay = good()
    pay["ch02"]["sents"][1]["text"] = "ISBN nine hundred and seventy-eight, www.panmacmillan.com"
    assert "front-matter-leak" in rules(bp.audit(man, pay), "errors")
