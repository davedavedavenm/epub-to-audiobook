#!/usr/bin/env python3
"""Measure real TypeSafe/Jev answers for the jevspeak normalization layer.

Runs the ambiguous-span candidates for a set of tricky, realistic book
sentences through Jev in ONE batched request and prints the actual chosen
reading, confidence and probability distribution. Used to set and justify the
``JEV_MIN_CONFIDENCE`` threshold; no production code path depends on this file.

Usage:
    python scripts/measure_jevspeak.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))

import jevspeak  # noqa: E402
import requests  # noqa: E402

EXAMPLES = [
    "She added 1/2 a cup of sugar to the batter.",
    "He scored 3/4 in the entrance test.",
    "The 9/11 attacks changed the world.",
    "Dr. Smith examined the patient carefully.",
    "He turned onto Elm Dr. at dusk.",
    "St. Patrick drove the snakes from Ireland.",
    "The office is on High St. near the bank.",
    "See No. 4 in the attached list.",
    "Chapter IV begins the tale.",
    "The nurse started an IV drip at once.",
    "The cable is 3.5mm thick.",
    "He ran 5m to the open door.",
    "Pages 10-12 cover the war.",
    "It cost £4.50 at the market.",
    "J. R. R. Tolkien wrote the book.",
]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    key = jevspeak._api_key()
    if not key:
        print('No TypeSafe API key found. Set TYPESAFE_API_KEY or '
              'TYPESAFE_API_KEY_PATH.', file=sys.stderr)
        return 2

    text = ' '.join(EXAMPLES)
    candidates = jevspeak.find_normalization_candidates(text)
    questions = jevspeak._normalization_questions(candidates)
    state = jevspeak._state_for(candidates)

    print(f'{len(candidates)} candidates -> 1 request\n')
    resp = requests.post(
        jevspeak.DEFAULT_API_URL,
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        json={'state': state, 'model': jevspeak.DEFAULT_MODEL, 'questions': questions},
        timeout=60,
    )
    resp.raise_for_status()
    body = resp.json()
    answers = body.get('answers', {})

    print(f"{'id':<4} {'kind':<9} {'span':<10} {'choice':<12} {'conf':>5}  probabilities")
    print('-' * 100)
    for candidate in candidates:
        answer = answers.get(candidate.cid, {})
        probs = answer.get('probabilities') or {}
        top = ', '.join(f'{k}={v:.2f}' for k, v in
                        sorted(probs.items(), key=lambda kv: kv[1], reverse=True))
        print(f"{candidate.cid:<4} {candidate.kind:<9} {candidate.span:<10} "
              f"{str(answer.get('choice')):<12} {answer.get('confidence', 0):>5.2f}  {top}")
        print(f"      sentence: {candidate.sentence}")

    print('\nusage:', json.dumps(body.get('usage', {})))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
