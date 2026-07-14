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


def sample_text_for(engine: str) -> str:
    """The sample, put through the SAME preprocessing a real render of this engine
    would apply — so the voice you audition is the voice you'd actually get.

    Asymmetric on purpose (MODERN-ENGINE CONTRACT):
      * chatterbox/tada -> numbers/dates left ALONE, no phonetic respellings.
      * kokoro/piper/edge/polly -> numbers spelled out, which they need.
    Sending raw text to everything would make the dumb engines mangle "$1.2
    billion" and you'd be judging a preprocessing bug, not the voice.
    """
    try:
        from tts_preprocess import normalize_text_for_tts
        return normalize_text_for_tts(SAMPLE_TEXT, lexicon=SAMPLE_LEXICON,
                                      modern=engine in MODERN_ENGINES)
    except Exception:
        return SAMPLE_TEXT
