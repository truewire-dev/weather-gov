"""Generic replay coverage: every recorded example, through the real client, validated.

Parametrized over the recorded pairs. `test_recordings.py` says what each recording
proves; this only proves that every one of them replays and validates.
"""

from pathlib import Path

from truewire.testing import build_http_replay_test

PROJECT = Path(__file__).resolve().parents[3]

test_examples_replay = build_http_replay_test(PROJECT)
