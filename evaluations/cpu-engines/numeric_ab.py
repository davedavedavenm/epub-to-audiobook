"""Pinned raw-vs-app-normalized corpus for the 2026-08-14 CPU voice A/B."""

import hashlib
import os
import sys
from pathlib import Path


RAW_TEXT = (
    "In 1997, annual revenue was $1.2 billion, while costs reached £24.6 million. "
    "The next offer was $33.50, followed by £57.25 and €1,250.75. "
    "Between 2001 and 2007, headcount rose from 3,400 to 230,000. "
    "The 21st invoice added a 12.5% fee. The order was worth $50 million. "
    "Chapter 3 compares a valuation of £33 billion with 71% growth."
)

REPO_ROOT = Path('/repo') if Path('/repo/webapp').is_dir() else Path(__file__).resolve().parents[2]


def selected_text():
    """Return (text, report label, arm), preserving the original screen by default."""
    arm = os.environ.get('NUMERIC_AB_ARM', '').strip().lower()
    if not arm:
        sys.path.insert(0, str(REPO_ROOT / 'webapp'))
        from voice_sample import SAMPLE_TEXT
        return SAMPLE_TEXT, 'webapp.voice_sample.SAMPLE_TEXT', ''
    if arm not in {'raw', 'normalized'}:
        raise ValueError('NUMERIC_AB_ARM must be raw or normalized')
    if arm == 'raw':
        text = RAW_TEXT
    else:
        sys.path.insert(0, str(REPO_ROOT / 'webapp'))
        from tts_preprocess import normalize_text_for_tts
        # These candidates are not yet admitted as modern engines. This is the
        # exact deterministic path an unclassified engine receives in the app.
        text = normalize_text_for_tts(RAW_TEXT, modern=False)
    return text, f'evaluations.cpu-engines.numeric_ab.{arm}', arm


def source_hash():
    return hashlib.sha256(RAW_TEXT.encode('utf-8')).hexdigest()
