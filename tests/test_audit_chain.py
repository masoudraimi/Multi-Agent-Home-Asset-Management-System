"""Tests for core.audit's tamper-evident hash chain: append+verify clean,
mutate-a-line+verify catches it, rotation preserves continuity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_audit_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect the audit log + chain-state sidecar to a scratch dir and
    reset the in-process hash cache so tests don't see each other's state."""
    import core.audit as audit_mod

    log_path = tmp_path / "audit.log"
    state_path = tmp_path / "audit-chain-state.json"
    monkeypatch.setattr(audit_mod, "_audit_path", lambda: log_path)
    monkeypatch.setattr(audit_mod, "_chain_state_path", lambda: state_path)
    monkeypatch.setattr(audit_mod, "_last_hash_cache", None)
    return audit_mod


def test_chain_verifies_clean_after_several_appends(_isolated_audit_log) -> None:
    from core.audit import audit, verify_chain

    for i in range(5):
        audit("user_login", request_id=f"req-{i}", user_id="u1")

    result = verify_chain()
    assert result.ok is True
    assert result.total_entries == 5
    assert result.first_broken_line is None


def test_tampered_line_is_detected(_isolated_audit_log) -> None:
    from core.audit import audit, verify_chain, _audit_path

    for i in range(4):
        audit("user_login", request_id=f"req-{i}", user_id="u1")

    path = _audit_path()
    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[2])
    tampered["user_id"] = "attacker"  # mutate payload without recomputing entry_hash
    lines[2] = json.dumps(tampered)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify_chain()
    assert result.ok is False
    assert result.first_broken_line == 3
    assert result.reason == "hash_mismatch"


def test_deleted_line_breaks_chain_from_that_point(_isolated_audit_log) -> None:
    from core.audit import audit, verify_chain, _audit_path

    for i in range(4):
        audit("user_login", request_id=f"req-{i}", user_id="u1")

    path = _audit_path()
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]  # remove the second entry entirely
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify_chain()
    assert result.ok is False
    assert result.reason == "prev_hash_mismatch"


def test_rotation_preserves_chain_continuity(_isolated_audit_log) -> None:
    from core.audit import audit, rotate, verify_chain

    for i in range(3):
        audit("user_login", request_id=f"pre-{i}", user_id="u1")

    archive = rotate()
    assert archive is not None and archive.exists()

    for i in range(3):
        audit("user_login", request_id=f"post-{i}", user_id="u1")

    result = verify_chain()
    assert result.ok is True
    assert result.total_entries == 3  # only the post-rotation entries remain in the live file


def test_empty_log_verifies_ok(_isolated_audit_log) -> None:
    from core.audit import verify_chain

    result = verify_chain()
    assert result.ok is True
    assert result.total_entries == 0


def test_unknown_event_type_is_dropped_not_chained(_isolated_audit_log) -> None:
    from core.audit import audit, verify_chain, _audit_path

    audit("not_a_real_event_type", request_id="req-x", user_id="u1")
    assert not _audit_path().exists()
    result = verify_chain()
    assert result.ok is True
    assert result.total_entries == 0
