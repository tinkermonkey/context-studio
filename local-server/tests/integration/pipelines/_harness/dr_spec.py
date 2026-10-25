"""
Pinned DR spec snapshot for tests.

The DR ontology tests (and the recognition cassette recorder) build against a
fixed `documentation_robotics/spec` version committed under
`tests/integration/fixtures/dr_spec/`, so their expected row counts and
prompt-hashed cassettes never drift with the live sibling checkout, and they
also run on CI. See that directory's README for the source commit and how to
regenerate the snapshot.
"""

import atexit
import shutil
import tarfile
import tempfile
from functools import cache
from pathlib import Path

PINNED_DR_SPEC_VERSION = "0.8.4"
PINNED_DR_SPEC_ARCHIVE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "dr_spec"
    / f"dr_spec_{PINNED_DR_SPEC_VERSION}.tar.xz"
)


@cache
def pinned_dr_spec_dir() -> Path:
    """
    Extract the pinned spec snapshot once per process and return its `spec/` dir.

    The extracted copy lives in a temp directory removed at interpreter exit.
    """
    extract_root = Path(tempfile.mkdtemp(prefix="dr_spec_"))
    atexit.register(shutil.rmtree, extract_root, ignore_errors=True)
    with tarfile.open(PINNED_DR_SPEC_ARCHIVE, "r:xz") as archive:
        archive.extractall(extract_root, filter="data")
    return extract_root / "spec"
