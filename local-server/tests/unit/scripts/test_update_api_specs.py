"""Unit tests for scripts/update_api_specs.py, in particular that --check writes nothing."""

import json
import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)
sys.path.append(
    os.path.join(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ),
        "scripts",
    )
)

import pytest

import update_api_specs

SPEC = {"openapi": "3.1.0", "paths": {"/health": {"get": {}}}}


@pytest.fixture
def spec_paths(tmp_path, monkeypatch):
    """Two spec locations under tmp_path, with the script pointed at them and at SPEC."""
    paths = (str(tmp_path / "backend" / "openapi.json"), str(tmp_path / "ux" / "openapi.json"))
    monkeypatch.setattr(update_api_specs, "SPEC_PATHS", paths)
    monkeypatch.setattr(update_api_specs, "generate_spec", lambda: SPEC)
    return paths


def _snapshot(tmp_path):
    return {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


class TestUpdateApiSpecs:
    """--check compares without writing; the default run writes both files."""

    def test_default_run_writes_both_files(self, spec_paths):
        assert update_api_specs.main([]) == 0
        for path in spec_paths:
            with open(path) as f:
                assert json.load(f) == SPEC

    def test_check_passes_on_fresh_files_and_changes_nothing(self, spec_paths, tmp_path):
        update_api_specs.main([])
        before = _snapshot(tmp_path)

        assert update_api_specs.main(["--check"]) == 0
        assert _snapshot(tmp_path) == before

    def test_check_fails_on_a_stale_file_names_it_and_changes_nothing(
        self, spec_paths, tmp_path, capsys
    ):
        update_api_specs.main([])
        with open(spec_paths[1], "w") as f:
            f.write(update_api_specs.render_spec({"openapi": "3.1.0", "paths": {}}))
        before = _snapshot(tmp_path)

        assert update_api_specs.main(["--check"]) == 1
        assert _snapshot(tmp_path) == before
        err = capsys.readouterr().err
        assert spec_paths[1] in err
        assert spec_paths[0] not in err

    def test_check_fails_when_a_file_is_missing_and_does_not_create_it(self, spec_paths, tmp_path):
        assert update_api_specs.main(["--check"]) == 1
        assert not any(tmp_path.rglob("*.json"))

    def test_check_fails_when_the_app_cannot_be_imported(self, monkeypatch, capsys):
        def broken():
            raise ImportError("no module named boom")

        monkeypatch.setattr(update_api_specs, "generate_spec", broken)

        assert update_api_specs.main(["--check"]) == 1
        assert "boom" in capsys.readouterr().err
