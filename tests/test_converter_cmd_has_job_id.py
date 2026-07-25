"""Every converter invocation must carry --job-id (#33).

Without it `convert_book.py` writes no transcript chunks, so the render cannot
be verified afterwards and the quality gate passes on an empty inspection.

This test exists because the first attempt at the fix patched only ONE of the
two call sites: they are indented differently, so a replace-all matched the
watchdog's retry builder and silently missed the main render path. Nothing
caught it until a live render produced no chunks.

Asserting on the source is deliberately crude, but it is the cheapest thing
that would have failed at the time.
"""

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'webapp' / 'app.py'


def _converter_command_blocks(src: str):
    """Yield each list literal that invokes convert_book.py."""
    blocks = []
    for m in re.finditer(r"convert_book\.py'", src):
        start = src.rfind('[', 0, m.start())
        end = src.find(']', m.end())
        if start != -1 and end != -1:
            blocks.append(src[start:end])
    return blocks


def test_every_converter_invocation_passes_job_id():
    src = APP.read_text(encoding='utf-8')
    blocks = _converter_command_blocks(src)
    assert blocks, 'no convert_book.py invocations found — has the file moved?'
    missing = [i for i, b in enumerate(blocks) if '--job-id' not in b]
    assert not missing, (
        f'{len(missing)} of {len(blocks)} convert_book.py invocations omit '
        f'--job-id; those renders would be unverifiable (#33)'
    )


def test_converter_accepts_job_id():
    """The flag has to exist on the other end of the call, too."""
    conv = Path(__file__).resolve().parents[1] / 'scripts' / 'convert_book.py'
    assert "'--job-id'" in conv.read_text(encoding='utf-8')
