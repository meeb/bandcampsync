"""Tests for bandcampsync.domain.sync_state."""

from bandcampsync.domain.sync_state import SyncState


def test_sync_state_starts_idle() -> None:
    state = SyncState()
    snapshot = state.to_dict()
    assert snapshot["status"] == "idle"
    assert snapshot["last_run_started"] is None
    assert snapshot["last_result"] is None


def test_sync_state_tracks_a_run() -> None:
    state = SyncState()
    state.mark_running()
    assert state.to_dict()["status"] == "running"

    state.mark_finished("ok", next_scheduled="2026-08-21T03:00:00+00:00")
    snapshot = state.to_dict()
    assert snapshot["status"] == "idle"
    assert snapshot["last_result"] == "ok"
    assert snapshot["next_scheduled"] == "2026-08-21T03:00:00+00:00"
    assert snapshot["last_run_finished"] is not None


def test_sync_state_keeps_next_scheduled_when_not_given() -> None:
    state = SyncState()
    state.mark_finished("ok", next_scheduled="2026-08-21T03:00:00+00:00")
    state.mark_running()
    state.mark_finished("ok")
    assert state.to_dict()["next_scheduled"] == "2026-08-21T03:00:00+00:00"
