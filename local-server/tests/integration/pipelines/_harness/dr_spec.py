"""
Pinned DR spec snapshots for tests.

The DR ontology tests (and the recognition cassette recorder) build against a
fixed `documentation_robotics/spec` version committed under
`tests/integration/fixtures/dr_spec/`, so their expected row counts and
prompt-hashed cassettes never drift with the live sibling checkout, and they
also run on CI. See that directory's README for the source commits and how to
regenerate a snapshot.

Context Studio's own DR model is written for a newer spec than the cassette
pin, so its import test uses its own snapshot (`MODEL_DR_SPEC_VERSION`).
"""

import atexit
import shutil
import tarfile
import tempfile
from functools import cache
from pathlib import Path

PINNED_DR_SPEC_VERSION = "0.8.4"
# The spec version documentation-robotics/model/ is written for.
MODEL_DR_SPEC_VERSION = "0.10.0"
DR_SPEC_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "dr_spec"


@cache
def dr_spec_dir(version: str) -> Path:
    """
    Extract the `version` spec snapshot once per process and return its `spec/` dir.

    The extracted copy lives in a temp directory removed at interpreter exit.
    """
    extract_root = Path(tempfile.mkdtemp(prefix=f"dr_spec_{version}_"))
    atexit.register(shutil.rmtree, extract_root, ignore_errors=True)
    with tarfile.open(DR_SPEC_FIXTURE_DIR / f"dr_spec_{version}.tar.xz", "r:xz") as archive:
        archive.extractall(extract_root, filter="data")
    return extract_root / "spec"


def pinned_dr_spec_dir() -> Path:
    """The pinned spec snapshot's `spec/` dir (the version the cassettes were recorded on)."""
    return dr_spec_dir(PINNED_DR_SPEC_VERSION)
