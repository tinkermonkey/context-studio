"""
VCR configuration for grounding test cassettes.

Records and replays HTTP interactions using cassette YAML files.
Ensures tests run without external network dependencies.
"""

from pathlib import Path

import pytest
import vcr


@pytest.fixture
def recorded_vcr():
    """VCR fixture for recorded HTTP playback (no network calls)."""
    cassettes_dir = Path(__file__).parent.parent.parent / "fixtures" / "cassettes"

    vcr_instance = vcr.VCR(
        cassette_library_dir=str(cassettes_dir),
        path_transformer=vcr.VCR.ensure_suffix(".yaml"),
        record_mode="none",
    )

    return vcr_instance
