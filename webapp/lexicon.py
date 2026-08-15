"""The seed pronunciation dictionary — ONE definition, shared by the converter
and the voice-audition sample so an audition can't be harsher (or kinder) than a
real book.

Previously this lived only in scripts/convert_book.py, so voice samples were sent
proper nouns RAW while real renders got them respelled — "Xiaomi" was mangled in
the audition but correct in the book (Dave, 2026-07-14). An audition you can't
trust is worse than no audition.

NOTE how these are consumed (MODERN-ENGINE CONTRACT, tts_preprocess):
  * legacy engines (kokoro/edge/polly) -> the WHOLE dict applies.
  * modern engines (chatterbox/tada)         -> only the LETTER-SPACING class
    survives the filter; phonetic respellings are dropped, because shouty
    respellings ("Bay-JING") made modern engines worse. That means modern engines
    still mispronounce proper nouns like Xiaomi — a real, open quality gap, not an
    oversight.
"""

SEED_PRONUNCIATION = {
    # Phonetic respellings — LEGACY ENGINES ONLY (filtered out for modern).
    "Cupertino": "Coo-per-TEE-no", "Beijing": "Bay-JING", "McDonald's": "Mick-DON-uld-z",
    "Huawei": "HWAH-way", "Xiaomi": "SHOW-mee", "Nguyen": "Nwin", "Qualcomm": "KWAL-com",
    "Foxconn": "FOX-con", "Shenzhen": "SHUN-jen", "Guangzhou": "GWANG-joe",
    "Zhengzhou": "JUNG-joe", "Forstall": "FOR-stawl",
    # TADA tokenizer quirks caught by ear/QA (2026-07-08): "iPhones" -> "if owns"
    "iPhone": "eye-phone", "iPhones": "eye-phones", "iPad": "eye-pad", "iPods": "eye-pods",
    "iPod": "eye-pod", "iOS": "eye-O-S",
    # Acronym LETTER-SPACING — the one class that survives for MODERN engines too
    # (plain letters, not a respelling). Undotted initialisms are misread
    # otherwise: "CEO" comes out as "see you".
    "CEO": "C E O", "WTO": "W T O", "EU": "E U", "GDP": "G D P", "IPO": "I P O",
}
