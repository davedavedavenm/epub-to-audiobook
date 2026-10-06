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


def _cl(*pairs):
    return [{"title": t, "words": w} for t, w in pairs]


def test_matter_filter_drops_front_matter_and_cuts_everything_after_notes():
    import fish_bundle as fb
    cl = _cl(("Copyright", 200), ("Contents", 150), ("Prologue", 400), ("An Abduction", 1000),
             ("Albert's Daughters", 5000), ("Evacuation", 4400), ("The Last Gun", 4800),
             ("Acknowledgements", 1000), ("A Note on Sources", 900), ("Notes", 3000),
             ("Say-42", 5000), ("Select Bibliography", 2500), ("Index", 2000))
    kept, skipped = fb.filter_matter(cl)
    assert [c["title"] for c in kept] == ["Prologue", "An Abduction", "Albert's Daughters",
                                          "Evacuation", "The Last Gun"]
    assert {s["title"] for s in skipped} >= {"Copyright", "Contents", "Notes", "Say-42", "Index"}


def test_matter_filter_is_conservative_about_real_chapters():
    import fish_bundle as fb
    kept, _ = fb.filter_matter(_cl(("Preface", 3000), ("ONE: The Irish Revolution", 3000),
                                   ("Notes from a Small Island", 3000), ("Indexing the Past", 3000),
                                   ("Conclusion", 3000)))
    assert len(kept) == 5, [c["title"] for c in kept]
    # a leading "Notes" page is skipped, not treated as the start of the back matter
    kept, _ = fb.filter_matter(_cl(("Notes", 100), ("Chapter 1", 3000)))
    assert [c["title"] for c in kept] == ["Chapter 1"]
    assert len(fb.filter_matter(_cl(("Notes", 100), ("Index", 100)), keep_matter=True)[0]) == 2


def test_matter_filter_does_not_cut_on_a_few_short_front_pages():
    """The Armed Struggle failure in miniature: three short front pages + 'Acknowledgments'."""
    import fish_bundle as fb
    kept, _ = fb.filter_matter(_cl(("ARMED STRUGGLE", 1238), ("Armed Struggle", 229),
                                   ("Acknowledgments", 450), ("Preface", 1900),
                                   ("ONE The Irish Revolution", 15871), ("TWO New States", 15095),
                                   ("Notes and References", 12683)), book_title="Armed Struggle")
    assert [c["title"] for c in kept] == ["Preface", "ONE The Irish Revolution", "TWO New States"]


def test_matter_filter_refuses_to_drop_most_of_a_book():
    import fish_bundle as fb
    import pytest
    with pytest.raises(ValueError):
        fb.filter_matter(_cl(("Contents", 100), ("Index", 50000), ("Prologue", 900)))


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


def test_matter_filter_on_the_real_armed_struggle_chapter_list():
    """Regression: the entry-count version dropped EVERY chapter of this book."""
    import sys as _s
    _s.path.insert(0, str(ROOT / "webapp"))
    import chapters
    import fish_bundle as fb
    epub = ROOT / "fixtures" / "armed_struggle.epub"
    if not epub.exists():   # a copyrighted book: present on Dave's machine, not in the GitHub repo
        import pytest
        pytest.skip("fixtures/armed_struggle.epub not in this checkout")
    cl = chapters.list_renderable_chapters(str(epub))
    kept, skipped = fb.filter_matter(cl, book_title="Armed Struggle")
    titles = [c["title"] for c in kept]
    assert any(t.startswith("Preface") for t in titles) and any(t.startswith("CONCLUSION") for t in titles)
    assert sum(1 for t in titles if t[:3] in ("ONE", "TWO", "THR", "FOU", "FIV", "SIX", "SEV", "EIG")) == 8
    assert sum(c["words"] for c in kept) > 140_000, sum(c["words"] for c in kept)
    why = {s["title"]: s["why"] for s in skipped}
    assert "Contents" in why and "List of Abbreviations" in why and "Notes and References" in why
    assert "Index" in why and "Bibliography" in why


def test_matter_filter_recognises_imprint_pages_by_text_and_strips_the_job_id_prefix():
    import fish_bundle as fb
    cl = [{"title": "ARMED STRUGGLE", "words": 1238, "snippet": "Superb . . . the first full history of the IRA"},
          {"title": "Armed Struggle", "words": 229, "snippet": "First published two thousand three by Macmillan ISBN"},
          {"title": "Preface", "words": 1900, "snippet": "Funerals. The first was for IRA man"},
          {"title": "ONE The Irish Revolution", "words": 15871, "snippet": "x"},
          {"title": "TWO New States", "words": 15095, "snippet": "x"}]
    # webapp job file name, exactly as the lane derives it
    kept, skipped = fb.filter_matter(cl, book_title="Armed Struggle - Richard English")
    assert [c["title"] for c in kept] == ["Preface", "ONE The Irish Revolution", "TWO New States"]
    assert {s["why"] for s in skipped} >= {"imprint/copyright page"}
    # even with NO usable title, the copyright page is caught by its text
    kept2, _ = fb.filter_matter(cl, book_title=None)
    assert "Armed Struggle" not in [c["title"] for c in kept2]


# --- library-corpus findings (187 real EPUBs, 2026-10-06) ---------------------

def test_file_name_titles_shared_by_many_chapters_are_not_matter():
    """Bonfire of the Vanities: 8 body files titled 'index' (from index_split_00x) were cut as the Index."""
    import fish_bundle as fb
    cl = [{"title": "Prologue", "words": 9000}] + [{"title": "index", "words": 25000, "back_matter": True}
                                                    for _ in range(8)] + [{"title": "Epilogue", "words": 1700}]
    kept, _ = fb.filter_matter(cl)
    assert len(kept) == 10
    # a single genuine Index after real chapters is still cut
    cl2 = [{"title": f"Chapter {i}", "words": 5000} for i in range(1, 6)] + [{"title": "Index", "words": 9000}]
    assert len(fb.filter_matter(cl2)[0]) == 5


def test_strip_imprint_removes_copyright_lines_from_the_first_chapters_only():
    import fish_bundle as fb
    sents = [{"text": "Copyright (c) two thousand one by Tim Winton.", "para": 0, "quote": False},
             {"text": "ISBN nine seven eight.", "para": 0, "quote": False},
             {"text": "He walked to the shore and looked out over the grey water for a long time.", "para": 1, "quote": False}]
    later = [{"text": "She said the copyright had expired long ago on the old song and laughed.", "para": 0, "quote": False}]
    pay = {"ch01": {"sents": [dict(x) for x in sents]}, "ch02": {"sents": []}, "ch03": {"sents": []},
           "ch09": {"sents": [dict(x) for x in later]}}
    removed = fb.strip_imprint(pay, ["ch01", "ch02", "ch03", "ch09"])
    assert removed == 2 and len(pay["ch01"]["sents"]) == 1
    assert len(pay["ch09"]["sents"]) == 1                 # ch09 is beyond the first chapters: untouched


def test_spine_fallback_reads_books_the_chapter_detector_misses(tmp_path):
    import sys as _s
    _s.path.insert(0, str(ROOT / "tests"))
    from test_fish_lane import _make_epub
    import fish_bundle as fb
    epub = tmp_path / "b.epub"
    _make_epub(epub)
    cl = fb.spine_chapters(epub)
    assert [c["title"] for c in cl] == ["Chapter One", "Chapter Two", "Chapter Three"]
    assert all(c["words"] >= 100 and c["href"].endswith(".xhtml") for c in cl)


def test_symbol_junk_rule_ignores_arrows_but_catches_symbol_soup():
    import book_preflight as bp
    rx = bp._JUNK["symbols"]
    assert not rx.search("--> and <shanice@mail.co.uk> and a | b")
    assert rx.search("{{{ ### ~~~ }}}")


def test_spine_fallback_trusts_media_type_not_file_extension(tmp_path):
    """The War of Art ships content as .html_split_000, Interpreter of Maladies as .xml."""
    import zipfile as zf
    import fish_bundle as fb
    body = "<html><body><h1>Resistance</h1><p>" + ("The writer sits down and the fear arrives. " * 40) + "</p></body></html>"
    epub = tmp_path / "odd.epub"
    with zf.ZipFile(epub, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml",
                   '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                   '<rootfile full-path="OPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr("OPS/c01.xml", body)
        z.writestr("OPS/part.html_split_001", body.replace("Resistance", "Turning Pro"))
        z.writestr("OPS/content.opf",
                   '<package xmlns="http://www.idpf.org/2007/opf"><manifest>'
                   '<item id="a" href="c01.xml" media-type="application/xhtml+xml"/>'
                   '<item id="b" href="part.html_split_001" media-type="application/xhtml+xml"/>'
                   '<item id="c" href="cover.jpeg" media-type="image/jpeg"/></manifest>'
                   '<spine><itemref idref="a"/><itemref idref="b"/><itemref idref="c"/></spine></package>')
    cl = fb.spine_chapters(epub)
    assert [c["title"] for c in cl] == ["Resistance", "Turning Pro"]


def test_long_copyright_paragraph_is_stripped_but_prose_is_not():
    import fish_bundle as fb
    legal = ("All rights reserved. No part of this book may be reproduced or transmitted in any form or by "
             "any means without permission in writing from the publisher, except by a reviewer who may quote "
             "brief passages. The moral right of the author has been asserted. This is a work of fiction and "
             "any resemblance to real persons is purely coincidental and unintended by the author.")
    prose = "He had reproduced the map from memory, and he laid it on the table between them in the lamplight."
    pay = {"ch01": {"sents": [{"text": legal, "para": 0, "quote": False}, {"text": prose, "para": 1, "quote": False}]}}
    assert fb.strip_imprint(pay, ["ch01"]) == 1 and pay["ch01"]["sents"][0]["text"] == prose


def test_preflight_ignores_repeated_file_name_titles():
    import book_preflight as bp
    c = [{"slug": f"ch{i}", "title": "index", "words": 5000} for i in range(4)]
    assert bp._repeated_title(c, c[0]) and not bp._repeated_title(c[:2], c[0])
