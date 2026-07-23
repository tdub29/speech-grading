"""Root pytest conftest: puts the repo on sys.path and exposes shared fixtures."""

import os
import sys

import pytest

ROOT = os.path.dirname(__file__)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "sample_transcript.json")


@pytest.fixture
def sample_transcript():
    """A derived canonical Transcript with deliberate fillers/hedges/pauses/repeats."""
    from speech_grading.schema import load_transcript_json
    return load_transcript_json(FIXTURE)
