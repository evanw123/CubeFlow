from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from .app_state import (
    clear_all_manual_edits,
    clear_manual_edits_for_slot,
    cube_state_from_store,
    load_app_state,
    load_calibration_store,
    now_iso,
    record_evaluation_scan_capture,
    record_evaluation_validation,
    save_app_state,
    summarize_cube_state,
)
from .color_recognition import (
    RecognitionTracker,
    all_face_stable,
    classify_from_calibration,
    extract_stable_face_grid,
    normalize_bgr,
    validate_sample_grid,
)
from .cube_state import CubeState, FACE_ORDER
from .web_sessions import get_active_web_session


SCAN_STEPS = [
    {"slot": "F", "frontColor": "GREEN", "topColor": "WHITE", "instruction": "Show GREEN face", "orientationHint": "Keep WHITE on top"},
    {"slot": "R", "frontColor": "RED", "topColor": "WHITE", "instruction": "Show RED face", "orientationHint": "Keep WHITE on top"},
    {"slot": "B", "frontColor": "BLUE", "topColor": "WHITE", "instruction": "Show BLUE face", "orientationHint": "Keep WHITE on top"},
    {"slot": "L", "frontColor": "ORANGE", "topColor": "WHITE", "instruction": "Show ORANGE face", "orientationHint": "Keep WHITE on top"},
    {"slot": "U", "frontColor": "WHITE", "topColor": "BLUE", "instruction": "Show WHITE face", "orientationHint": "Keep BLUE on top"},
    {"slot": "D", "frontColor": "YELLOW", "topColor": "GREEN", "instruction": "Show YELLOW face", "orientationHint": "Keep GREEN on top"},
]


@dataclass
class BrowserScannerRuntime:
    tracker: RecognitionTracker = field(default_factory=RecognitionTracker)
    lock: threading.RLock = field(default_factory=threading.RLock)

    def reset_recognition(self) -> None:
        with self.lock:
            self.tracker.reset()


def get_browser_scanner_runtime() -> BrowserScannerRuntime:
    session = get_active_web_session()
    if session is None:
        raise RuntimeError("Browser scanner requires an active web session.")
    with session.lock:
        runtime = session.runtime.get("browserScanner")
        if not isinstance(runtime, BrowserScannerRuntime):
            runtime = BrowserScannerRuntime()
            session.runtime["browserScanner"] = runtime
        return runtime


def _step(index: int) -> dict[str, str]:
    return SCAN_STEPS[max(0, min(len(SCAN_STEPS) - 1, int(index)))]


def _camera_resolution(value: Any) -> dict[str, int] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("cameraResolution must be an object.")
    width = value.get("width")
    height = value.get("height")
    if isinstance(width, bool) or isinstance(height, bool) or not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
        raise ValueError("cameraResolution width and height must be numbers.")
    width_int, height_int = int(width), int(height)
    if width_int < 1 or height_int < 1 or width_int > 8192 or height_int > 8192:
        raise ValueError("cameraResolution is outside the supported range.")
    return {"width": width_int, "height": height_int}


def set_browser_camera_status(running: bool, *, error: str | None = None) -> dict[str, Any]:
    state = load_app_state()
    scanner = state.setdefault("scanner", {})
    scanner.update(
        {
            "running": bool(running),
            "cameraStatus": "ready" if running else "stopped",
            "previewAvailable": bool(running),
            "stateAvailable": bool(running),
            "processRunning": False,
            "source": "browser",
            "lastError": error,
        }
    )
    if not running:
        scanner["captureReady"] = False
        scanner["faceStable"] = False
    return save_app_state(state)


def process_browser_samples(payload: dict[str, Any]) -> dict[str, Any]:
    samples = validate_sample_grid(payload.get("samples"))
    center_bgr = normalize_bgr(payload.get("centerBgr"), field_name="centerBgr")
    resolution = _camera_resolution(payload.get("cameraResolution"))
    runtime = get_browser_scanner_runtime()
    calibration = load_calibration_store()

    with runtime.lock:
        live_grid, stable_grid = runtime.tracker.classify(samples, calibration)

    state = load_app_state()
    scanner = state.setdefault("scanner", {})
    current_index = int(scanner.get("currentStepIndex", 0) or 0)
    step = _step(current_index)
    center_label, _display, _debug = classify_from_calibration(center_bgr, calibration)
    face_stable = all_face_stable(stable_grid)
    center_matches = center_label == step["frontColor"]
    capture_ready = face_stable and center_matches

    if capture_ready:
        capture_status = "Ready to capture"
        capture_tone = "success"
    elif face_stable and not center_matches:
        capture_status = f"Stable but center is {center_label}, expected {step['frontColor']}"
        capture_tone = "danger"
    elif calibration:
        capture_status = "Waiting for stable face"
        capture_tone = "neutral"
    else:
        capture_status = "Calibrate cube colors first"
        capture_tone = "warning"

    scanner.update(
        {
            "running": True,
            "source": "browser",
            "cameraStatus": "scanning",
            "processRunning": False,
            "previewAvailable": True,
            "stateAvailable": True,
            "lastError": None,
            "currentStepIndex": current_index,
            "currentSlot": step["slot"],
            "instruction": step["instruction"],
            "orientationHint": step["orientationHint"],
            "expectedCenter": step["frontColor"],
            "currentCenterBgr": center_bgr,
            "centerLabel": center_label,
            "faceStable": face_stable,
            "centerMatches": center_matches,
            "captureReady": capture_ready,
            "captureStatus": capture_status,
            "captureStatusTone": capture_tone,
            "liveRecognitionGrid": live_grid,
            "liveRecognitionStableGrid": [[stable_grid[row][col][1] for col in range(3)] for row in range(3)],
            "stableRecognitionGrid": extract_stable_face_grid(stable_grid),
            "cameraResolution": resolution,
            "previewUpdatedAt": now_iso(),
        }
    )
    return save_app_state(state)


def _set_step(state: dict[str, Any], index: int) -> None:
    scanner = state.setdefault("scanner", {})
    next_index = max(0, min(len(SCAN_STEPS) - 1, index))
    step = _step(next_index)
    scanner.update(
        {
            "currentStepIndex": next_index,
            "currentSlot": step["slot"],
            "instruction": step["instruction"],
            "orientationHint": step["orientationHint"],
            "expectedCenter": step["frontColor"],
            "captureReady": False,
            "faceStable": False,
            "centerMatches": False,
            "captureStatus": "Waiting for stable face",
            "captureStatusTone": "neutral",
            "liveRecognitionStableGrid": [[False] * 3 for _ in range(3)],
            "stableRecognitionGrid": [["UNKNOWN"] * 3 for _ in range(3)],
        }
    )
    get_browser_scanner_runtime().reset_recognition()


def execute_browser_scanner_action(action: str) -> dict[str, Any]:
    normalized_action = str(action or "").strip().lower()
    if normalized_action not in {"capture", "next-step", "previous-step", "clear-face", "reset-cube", "validate"}:
        raise ValueError("Unsupported browser scanner action.")

    state = load_app_state()
    scanner = state.setdefault("scanner", {})
    current_index = int(scanner.get("currentStepIndex", 0) or 0)
    current_step = _step(current_index)

    if normalized_action == "capture":
        if not scanner.get("captureReady"):
            raise ValueError(scanner.get("captureStatus") or "The face is not ready to capture.")
        stable_face = scanner.get("stableRecognitionGrid")
        if not isinstance(stable_face, list) or len(stable_face) != 3:
            raise ValueError("No stable 3x3 recognition result is available.")

        slot = current_step["slot"]
        clear_manual_edits_for_slot(slot)
        state = load_app_state()
        scanner = state.setdefault("scanner", {})
        faces = scanner.setdefault("faces", {face: None for face in FACE_ORDER})
        faces[slot] = [[str(color) for color in row] for row in stable_face]
        scanner.update(
            {
                "lastCapturedAt": now_iso(),
                "lastCapturedSlot": slot,
                "lastCaptureMessage": f"{slot} face captured",
                "captureReady": False,
            }
        )
        state["solves"] = {"standard": None, "cfop": None}
        if current_index < len(SCAN_STEPS) - 1:
            _set_step(state, current_index + 1)
        saved = save_app_state(state)
        cube_state = CubeState.from_faces_dict(saved["scanner"]["faces"])
        summary = summarize_cube_state(cube_state)
        record_evaluation_scan_capture(
            slot=slot,
            scanned_faces=cube_state.to_faces_dict(),
            effective_faces=cube_state_from_store().to_faces_dict(),
            summary=summary,
            calibration_enabled=bool(load_calibration_store()),
        )
        if summary["complete"]:
            record_evaluation_validation(summary, phase="initial")
        return load_app_state()

    if normalized_action == "next-step":
        _set_step(state, current_index + 1)
    elif normalized_action == "previous-step":
        _set_step(state, current_index - 1)
    elif normalized_action == "clear-face":
        slot = current_step["slot"]
        clear_manual_edits_for_slot(slot)
        state = load_app_state()
        scanner = state.setdefault("scanner", {})
        scanner.setdefault("faces", {face: None for face in FACE_ORDER})[slot] = None
        scanner["lastCaptureMessage"] = f"{slot} face cleared"
        state["solves"] = {"standard": None, "cfop": None}
        get_browser_scanner_runtime().reset_recognition()
    elif normalized_action == "reset-cube":
        clear_all_manual_edits()
        state = load_app_state()
        scanner = state.setdefault("scanner", {})
        scanner["faces"] = {slot: None for slot in FACE_ORDER}
        scanner["lastCapturedAt"] = None
        scanner["lastCapturedSlot"] = None
        scanner["lastCaptureMessage"] = "Cube scan reset"
        state["solves"] = {"standard": None, "cfop": None}
        _set_step(state, 0)
    elif normalized_action == "validate":
        record_evaluation_validation(summarize_cube_state(cube_state_from_store()), phase="final")
        return load_app_state()

    return save_app_state(state)
