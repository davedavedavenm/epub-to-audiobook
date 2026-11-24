"""Shared engine text contracts for books, recovery and narrator auditions.

These are listening-backed application choices, not inferred model capabilities.
Changing a profile requires a controlled audition; keep proper-name handling
separate from number expansion. See PREPROCESSING.md and DECISIONS.md.
"""

MODERN_ENGINES = ("chatterbox", "chatterbox_nano", "tada", "breeze", "qwen3", "vibevoice", "fish")
EXPLICIT_ENGINES = ("pocket", "kitten", "gemini", "deepgram", "cpu_narrators", "tontaube")
NATIVE_ENGINES = ("zonos3", "reverb")


def text_profile_for_engine(engine: str) -> str:
    if engine in NATIVE_ENGINES:
        return 'native'
    if engine in EXPLICIT_ENGINES:
        return 'explicit'
    if engine in MODERN_ENGINES:
        return 'modern'
    return 'legacy'
