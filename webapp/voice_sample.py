"""Versioned shared audition passage. Read AUDITION-STANDARD.md before changing it.

All new default previews and comparison scripts import this module. The legacy
passage is retained only to reproduce historical, hash-pinned experiments.
"""
import hashlib

SAMPLE_ID = "narrator-standard-v1"
SAMPLE_LABEL = "Shared test v1"
LEGACY_SAMPLE_ID = "legacy-apple-2026"
ORDINARY_TEXT = (
    "The room grew quiet as the visitors took their seats. Outside, rain tapped "
    "against the windows, but nobody seemed in a hurry to leave. The speaker "
    "paused, looked around the table, and began a story about the people who "
    "had helped her understand a changing world."
)
CHALLENGE_TEXT = (
    "In 2026, Dr. Helen Carter travelled from the United Kingdom to South Africa, "
    "Kenya, Nigeria and China. In Johannesburg, Amina Okafor and David Williams "
    "discussed Nelson Mandela, Desmond Tutu and the election of 1994. In Beijing, "
    "Wang Wei and Li Na compared reports from Huawei and Xiaomi.\n\n"
    "The meeting began at 9:30 a.m. on 12 March. Of the 1,250 people invited, "
    "875 attended. Ticket prices rose by 7.5%, from £24.60 to £26.45. A separate "
    "project cost $1.2 million and covered 3.5 kilometres. \"Are these the final "
    "figures?\" Helen asked. \"Yes,\" David replied, \"but the next report is due "
    "on 21 April.\""
)
SAMPLE_TEXT = ORDINARY_TEXT + "\n\n" + CHALLENGE_TEXT
SAMPLE_SHA256 = hashlib.sha256(SAMPLE_TEXT.encode("utf-8")).hexdigest()

LEGACY_SAMPLE_TEXT = (
    "In the spring of 1997, Apple was nine weeks from bankruptcy. Its CEO had "
    "been ousted, Steve Jobs had returned, the share price had fallen 71 percent, "
    "and the company was burning through $1.2 billion a year. Few analysts at "
    "Goldman Sachs believed it would survive to see the year 2000.\n\n"
    "What changed was not one decision, but a thousand small ones. Scott Forstall, "
    "Jony Ive, and a young engineer named Nguyen worked eighteen-hour days, six "
    "days a week, for months on end. Between 2001 and 2007, Apple's partners in "
    "Shenzhen and Zhengzhou scaled from 3,400 workers to over 230,000; a single "
    "Foxconn campus drew 1.5 gigawatts.\n\n"
    "Today the iPhone accounts for roughly 52% of revenue, and the App Store for "
    "some £24.6 billion a year. Rivals — Huawei, Xiaomi, Samsung — circle "
    "constantly. Whether that dependence is a triumph or a trap, for the WTO, for "
    "the EU, and for a supply chain 7,000 miles long, is the question Dr. Wang has "
    "spent a decade trying to answer."
)

# The SAME dictionary a real render uses — so the audition can't be harsher (or
# kinder) than the book. tts_preprocess applies it per the MODERN-ENGINE CONTRACT:
# legacy engines get the whole dict (so "Xiaomi" -> "SHOW-mee"); modern engines
# keep only the acronym letter-spacing class.
from lexicon import SEED_PRONUNCIATION as SAMPLE_LEXICON  # noqa: E402

MODERN_ENGINES = ("chatterbox", "chatterbox_nano", "tada", "breeze", "qwen3", "vibevoice", "fish")
EXPLICIT_ENGINES = ("pocket", "kitten", "gemini", "deepgram", "cpu_narrators")


def sample_text_for(engine: str, *, sample_id: str = SAMPLE_ID) -> str:
    """The sample, put through the SAME preprocessing a real render of this engine
    would apply — so the voice you audition is the voice you'd actually get.

    Asymmetric on purpose (measured engine contracts):
      * chatterbox/tada -> numbers/dates left ALONE, no phonetic respellings.
      * pocket/kitten/gemini -> explicit numbers/currency, acronym spacing only.
        This is the arm Dave selected for Peter, Jasper and Rosie on 2026-08-14,
        and the safe contract for the number-dense Gemini audition.
      * kokoro/edge/polly -> numbers spelled out, which they need.
    Sending raw text to every engine can make numeric frontends misread "$1.2
    billion" and you'd be judging a preprocessing bug, not the voice.
    """
    if sample_id not in (SAMPLE_ID, LEGACY_SAMPLE_ID):
        raise ValueError(f"Unknown audition sample: {sample_id}")
    source = SAMPLE_TEXT if sample_id == SAMPLE_ID else LEGACY_SAMPLE_TEXT
    try:
        from tts_preprocess import normalize_text_for_tts, _is_letter_spacing
        lexicon = SAMPLE_LEXICON
        if engine in EXPLICIT_ENGINES:
            lexicon = {
                key: value for key, value in SAMPLE_LEXICON.items()
                if _is_letter_spacing(key, value)
            }
        explicit = engine in EXPLICIT_ENGINES
        return normalize_text_for_tts(
            source, lexicon=lexicon,
            modern=engine in MODERN_ENGINES or explicit,
            expand_numbers=True if explicit else None,
        )
    except Exception as exc:
        raise RuntimeError(f"Could not prepare shared sample for {engine}") from exc
