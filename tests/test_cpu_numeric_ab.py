import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / 'evaluations' / 'cpu-engines' / 'numeric_ab.py'
SPEC = importlib.util.spec_from_file_location('cpu_numeric_ab', MODULE_PATH)
numeric_ab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(numeric_ab)


def test_numeric_ab_source_is_pinned():
    assert numeric_ab.source_hash() == (
        '84f9136147754b0bd196c76e1ca69780af9dfa584465c4a2f0f3cd304270a5b0'
    )
    assert '$1.2 billion' in numeric_ab.RAW_TEXT
    assert '£24.6 million' in numeric_ab.RAW_TEXT
    assert '€1,250.75' in numeric_ab.RAW_TEXT


def test_raw_arm_is_byte_identical(monkeypatch):
    monkeypatch.setenv('NUMERIC_AB_ARM', 'raw')
    text, name, arm = numeric_ab.selected_text()
    assert text == numeric_ab.RAW_TEXT
    assert name.endswith('.raw')
    assert arm == 'raw'


def test_normalized_arm_spells_every_numeric_case(monkeypatch):
    monkeypatch.setenv('NUMERIC_AB_ARM', 'normalized')
    text, name, arm = numeric_ab.selected_text()
    assert name.endswith('.normalized')
    assert arm == 'normalized'
    for expected in (
        'nineteen ninety-seven',
        'one point two billion dollars',
        'twenty-four point six million pounds',
        'thirty-three dollars and fifty cents',
        'one thousand two hundred and fifty euros and seventy-five cents',
        'three thousand four hundred',
        'two hundred and thirty thousand',
        'twenty-first',
        'twelve point five percent',
        'Chapter Three',
        'seventy-one percent',
    ):
        assert expected in text
    assert not any(character.isdigit() for character in text)
    assert not any(symbol in text for symbol in '$£€%')
