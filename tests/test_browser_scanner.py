from __future__ import annotations

import uuid

import numpy as np
import pytest

from cube_backend.app_state import (
    cube_state_from_store,
    load_app_state,
    reset_app_state,
    set_calibration_color,
)
from cube_backend.browser_scanner import execute_browser_scanner_action, process_browser_samples
from cube_backend.color_recognition import (
    RecognitionTracker,
    classify_from_calibration,
    get_stable_label,
    validate_sample_grid,
)
from cube_backend.web_sessions import WEB_SESSION_STORE


GREEN_BGR = [0, 180, 0]
RED_BGR = [0, 0, 210]


def sample_payload(color: list[int]) -> dict:
    return {
        "samples": [[color[:] for _ in range(3)] for _ in range(3)],
        "centerBgr": color[:],
        "cameraResolution": {"width": 1280, "height": 720},
    }


def new_session_id() -> str:
    return str(uuid.uuid4())


def test_browser_sample_payload_validation_rejects_bad_shape_and_range():
    with pytest.raises(ValueError, match="3x3"):
        validate_sample_grid([[[0, 0, 0]]])
    with pytest.raises(ValueError, match="0 to 255"):
        validate_sample_grid([[[0, 0, 999] for _ in range(3)] for _ in range(3)])


def test_lab_classifier_uses_calibration_and_preserves_white_rule():
    calibration = {"GREEN": GREEN_BGR, "RED": RED_BGR}
    assert classify_from_calibration([0, 175, 0], calibration)[0] == "GREEN"
    assert classify_from_calibration(np.array([0, 175, 0], dtype=np.uint8), calibration)[0] == "GREEN"
    assert classify_from_calibration([220, 220, 220], calibration)[0] == "WHITE"


def test_stability_requires_five_matching_readings_from_seven():
    label, stable = get_stable_label(["GREEN", "GREEN", "GREEN", "GREEN", "RED", "RED", "RED"])
    assert label == "GREEN"
    assert stable is False
    label, stable = get_stable_label(["GREEN", "RED", "GREEN", "GREEN", "RED", "GREEN", "GREEN"])
    assert label == "GREEN"
    assert stable is True


def test_expected_center_is_enforced_before_capture_and_step_advances():
    with WEB_SESSION_STORE.activate(new_session_id()):
        reset_app_state()
        set_calibration_color("GREEN", GREEN_BGR)
        set_calibration_color("RED", RED_BGR)

        for _ in range(5):
            process_browser_samples(sample_payload(RED_BGR))
        state = load_app_state()
        assert state["scanner"]["faceStable"] is True
        assert state["scanner"]["centerMatches"] is False
        assert state["scanner"]["captureReady"] is False
        with pytest.raises(ValueError, match="expected GREEN"):
            execute_browser_scanner_action("capture")

        execute_browser_scanner_action("previous-step")
        for _ in range(5):
            process_browser_samples(sample_payload(GREEN_BGR))
        state = load_app_state()
        assert state["scanner"]["captureReady"] is True

        execute_browser_scanner_action("capture")
        state = load_app_state()
        assert cube_state_from_store().faces["F"] == [["GREEN"] * 3 for _ in range(3)]
        assert state["scanner"]["currentSlot"] == "R"
        assert state["scanner"]["currentStepIndex"] == 1
        assert state["scanner"]["captureReady"] is False


def test_reset_clears_faces_but_keeps_calibration():
    with WEB_SESSION_STORE.activate(new_session_id()):
        reset_app_state()
        set_calibration_color("GREEN", GREEN_BGR)
        for _ in range(5):
            process_browser_samples(sample_payload(GREEN_BGR))
        execute_browser_scanner_action("capture")
        execute_browser_scanner_action("reset-cube")
        state = load_app_state()
        assert all(face is None for face in state["scanner"]["faces"].values())
        assert state["calibration"]["colors"]["GREEN"] == GREEN_BGR
        assert state["scanner"]["currentStepIndex"] == 0
