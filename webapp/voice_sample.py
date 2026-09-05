"""The voice-audition sample — ONE definition, shared by the web app and the
Kaggle GPU sample-renderer, so what you audition is byte-identical wherever it
was generated.

The text is deliberately hard: years, percentages, currency, large numbers,
units, acronyms, an abbreviation, comma-heavy clauses, and proper nouns that
trip narrators (Forstall, Nguyen, Shenzhen, Zhengzhou, Xiaomi, Huawei).
"""

SAMPLE_TEXT = (
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

MODERN_ENGINES = ("chatterbox", "tada")
EXPLICIT_ENGINES = ("pocket", "kitten", "gemini", "deepgram", "neutts")


def sample_text_for(engine: str) -> str:
    """The sample, put through the SAME preprocessing a real render of this engine
    would apply — so the voice you audition is the voice you'd actually get.

    Asymmetric on purpose (measured engine contracts):
      * chatterbox/tada -> numbers/dates left ALONE, no phonetic respellings.
      * pocket/kitten/gemini -> explicit numbers/currency, acronym spacing only.
        This is the arm Dave selected for Peter, Jasper and Rosie on 2026-08-14,
        and the safe contract for the number-dense Gemini audition.
      * kokoro/edge/polly -> numbers spelled out, which they need.
    Sending raw text to everything would make the dumb engines mangle "$1.2
    billion" and you'd be judging a preprocessing bug, not the voice.
    """
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
            SAMPLE_TEXT, lexicon=lexicon,
            modern=engine in MODERN_ENGINES or explicit,
            expand_numbers=True if explicit else None,
        )
    except Exception:
        return SAMPLE_TEXT
