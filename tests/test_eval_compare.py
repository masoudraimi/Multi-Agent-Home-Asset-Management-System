"""Tests for eval.compare's regression diff, mocking git and the filesystem."""

from __future__ import annotations

import json

import pytest


def _write_results(path, summary, results):
    path.write_text(json.dumps({"summary": summary, "results": results}))


def test_no_previous_baseline_reports_first_run(tmp_path, monkeypatch, capsys):
    import eval.compare as cmp

    results_path = tmp_path / "results.json"
    _write_results(results_path, {"simple": {"accuracy": 1.0}}, [{"id": "s01", "passed": True}])
    monkeypatch.setattr(cmp, "RESULTS_PATH", results_path)
    monkeypatch.setattr(cmp, "_load_previous", lambda: None)

    cmp.main()
    out = capsys.readouterr().out
    assert "establishes the baseline" in out


def test_flip_detection_reports_regression(tmp_path, monkeypatch, capsys):
    import eval.compare as cmp

    results_path = tmp_path / "results.json"
    current = {
        "summary": {"simple": {"accuracy": 0.5}},
        "results": [{"id": "s01", "passed": False}, {"id": "s02", "passed": True}],
    }
    previous = {
        "summary": {"simple": {"accuracy": 1.0}},
        "results": [{"id": "s01", "passed": True}, {"id": "s02", "passed": True}],
    }
    results_path.write_text(json.dumps(current))
    monkeypatch.setattr(cmp, "RESULTS_PATH", results_path)
    monkeypatch.setattr(cmp, "_load_previous", lambda: previous)

    cmp.main()
    out = capsys.readouterr().out
    assert "s01: REGRESSED" in out
    assert "1 scenario(s) flipped" in out


def test_no_flips_reports_none(tmp_path, monkeypatch, capsys):
    import eval.compare as cmp

    results_path = tmp_path / "results.json"
    data = {"summary": {}, "results": [{"id": "s01", "passed": True}]}
    results_path.write_text(json.dumps(data))
    monkeypatch.setattr(cmp, "RESULTS_PATH", results_path)
    monkeypatch.setattr(cmp, "_load_previous", lambda: data)

    cmp.main()
    out = capsys.readouterr().out
    assert "0 scenario(s) flipped" in out


def test_missing_results_file_exits_nonzero(tmp_path, monkeypatch):
    import eval.compare as cmp

    monkeypatch.setattr(cmp, "RESULTS_PATH", tmp_path / "does_not_exist.json")
    with pytest.raises(SystemExit) as exc_info:
        cmp.main()
    assert exc_info.value.code == 1
