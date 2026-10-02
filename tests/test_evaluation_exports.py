from __future__ import annotations

from app_server import _build_evaluation_csv_text, build_frontend_state, solve_standard
from cube_backend.app_state import (
    record_evaluation_scan_capture,
    record_evaluation_solver_result,
    record_evaluation_validation,
    reset_app_state,
    update_app_state,
    update_evaluation_metadata,
)
from cube_backend.cube_state import CubeState
from cube_backend.app_state import summarize_cube_state


SOLVED_FACELETS = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"


def test_evaluation_payload_tracks_trial_capture_and_solver_result():
    reset_app_state()
    update_evaluation_metadata(trial_id="demo-01", lighting_condition="desk lamp", start_new=True)

    solved = CubeState.from_facelet_string(SOLVED_FACELETS)
    update_app_state(
        {
            "scanner": {"faces": solved.to_faces_dict()},
            "calibration": {"colors": {"WHITE": [255, 255, 255]}},
        }
    )
    summary = summarize_cube_state(solved)

    record_evaluation_scan_capture(
        slot="D",
        scanned_faces=solved.to_faces_dict(),
        effective_faces=solved.to_faces_dict(),
        summary=summary,
        calibration_enabled=True,
    )
    record_evaluation_validation(summary, phase="initial")
    record_evaluation_solver_result(kind="standard", success=True, move_count=21, error=None)

    state = build_frontend_state()
    trial = state["evaluation"]["currentTrial"]

    assert trial["trialId"] == "demo-01"
    assert trial["lightingCondition"] == "desk lamp"
    assert trial["scanStartedAt"] is not None
    assert trial["scanCompletedAt"] is not None
    assert trial["calibrationEnabled"] is True
    assert trial["initialValidation"]["deepValidation"]["ok"] is True
    assert trial["solver"]["kind"] == "standard"
    assert trial["solver"]["success"] is True
    assert trial["solver"]["moveCount"] == 21
    assert state["evaluation"]["exportUrls"]["json"] == "/api/evaluation/export.json"


def test_evaluation_csv_export_contains_trial_summary():
    reset_app_state()
    update_evaluation_metadata(trial_id="trial-csv", lighting_condition="overhead leds", start_new=True)

    solved = CubeState.from_facelet_string(SOLVED_FACELETS)
    summary = summarize_cube_state(solved)
    record_evaluation_scan_capture(
        slot="D",
        scanned_faces=solved.to_faces_dict(),
        effective_faces=solved.to_faces_dict(),
        summary=summary,
        calibration_enabled=False,
    )
    record_evaluation_solver_result(kind="standard", success=False, move_count=0, error="Deep validation failed")

    csv_text = _build_evaluation_csv_text(build_frontend_state())

    assert "trial_id" in csv_text
    assert "trial-csv" in csv_text
    assert "overhead leds" in csv_text
    assert "standard" in csv_text


def test_standard_solve_incomplete_is_graceful_and_logs_evaluation():
    reset_app_state()

    result = solve_standard()
    state = build_frontend_state()
    trial = state["evaluation"]["currentTrial"]

    assert result["status"] == "incomplete"
    assert "Capture all 6 faces before solving." in result["error"]
    assert trial["solver"]["kind"] == "standard"
    assert trial["solver"]["success"] is False
    assert trial["errors"][-1]["source"] == "standard-solve"
