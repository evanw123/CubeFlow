from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cube_state import CubeState, FACE_ORDER

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_STATE_DIR = REPO_ROOT / ".app_state"
STATE_PATH = APP_STATE_DIR / "state.json"
SETTINGS_PATH = APP_STATE_DIR / "settings.json"
COMMANDS_PATH = APP_STATE_DIR / "commands.json"
SCAN_PREVIEW_PATH = APP_STATE_DIR / "scan-preview.jpg"
LAST_VIEW_SNAPSHOT_PATH = APP_STATE_DIR / "last-viewer-snapshot.json"
LAST_PLAYBACK_SESSION_PATH = APP_STATE_DIR / "last-playback-session.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "dark",
    "debugMode": False,
    "showAdvancedScannerInfo": False,
    "betaFeaturesEnabled": True,
    "showAnalysisOverlay": False,
    "cameraDeviceIndex": 0,
    "accentColor": "cyan",
}

EDITABLE_COLORS = ["WHITE", "YELLOW", "RED", "ORANGE", "BLUE", "GREEN", "UNKNOWN"]
CALIBRATION_COLORS = ["WHITE", "YELLOW", "GREEN", "BLUE", "RED", "ORANGE"]


def default_evaluation_trial() -> dict[str, Any]:
    return {
        "trialId": "",
        "lightingCondition": "",
        "trialStartedAt": None,
        "scanStartedAt": None,
        "scanCompletedAt": None,
        "calibrationEnabled": False,
        "recognizedStickerColors": {
            "scannedFaces": {slot: None for slot in FACE_ORDER},
            "effectiveFaces": {slot: None for slot in FACE_ORDER},
        },
        "manualCorrections": [],
        "initialValidation": None,
        "finalValidation": None,
        "solver": {
            "kind": None,
            "success": None,
            "moveCount": 0,
            "error": None,
            "solvedAt": None,
        },
        "previewFpsApprox": None,
        "previewTargetFps": None,
        "previewFpsSource": None,
        "clientInfo": {
            "userAgent": None,
            "appVersion": None,
            "platform": None,
        },
        "errors": [],
        "events": [],
    }


def default_app_state() -> dict[str, Any]:
    return {
        "app": {
            "name": "CubeFlow",
            "subtitle": "Scan, validate, and solve your Rubik's cube.",
            "mode": "normal",
            "lastUpdatedAt": None,
        },
        "scanner": {
            "running": False,
            "currentStepIndex": 0,
            "currentSlot": "F",
            "instruction": "Show GREEN face",
            "orientationHint": "Keep WHITE on top",
            "captureStatus": "Waiting for stable face",
            "captureStatusTone": "neutral",
            "captureReady": False,
            "faceStable": False,
            "centerMatches": False,
            "centerLabel": None,
            "expectedCenter": "GREEN",
            "currentCenterBgr": None,
            "previewUpdatedAt": None,
            "lastCapturedAt": None,
            "lastCapturedSlot": None,
            "lastCaptureMessage": None,
            "capturedFaces": {slot: False for slot in FACE_ORDER},
            "faces": {slot: None for slot in FACE_ORDER},
            "liveRecognitionGrid": [["UNKNOWN"] * 3 for _ in range(3)],
            "liveRecognitionStableGrid": [[False] * 3 for _ in range(3)],
            "advanced": {
                "counts": {},
                "calibration": {},
                "validationErrors": [],
                "deepValidationErrors": [],
                "deepValidationWarnings": [],
                "solverReady": False,
                "cfopReady": False,
            },
        },
        "corrections": {
            "overrides": {},
            "history": [],
            "lastEditedAt": None,
        },
        "calibration": {
            "colors": {},
            "lastUpdatedAt": None,
        },
        "review": {
            "complete": False,
            "capturedFaceCount": 0,
            "basicValidation": {"ok": False, "errors": []},
            "deepValidation": {"ok": False, "errors": [], "warnings": []},
            "faceletString": None,
            "lastValidatedAt": None,
            "manualEditCount": 0,
            "manualMask": {slot: [[False] * 3 for _ in range(3)] for slot in FACE_ORDER},
            "editableColors": EDITABLE_COLORS[:],
            "centersLocked": True,
        },
        "solves": {
            "standard": None,
            "cfop": None,
        },
        "viewer": {
            "lastOpenedMode": None,
            "lastOpenedAt": None,
            "lastSessionTitle": None,
        },
        "evaluation": {
            "currentTrial": default_evaluation_trial(),
            "history": [],
        },
        "recent": {
            "lastScanStatus": "No scan yet",
            "lastScanTimestamp": None,
        },
    }


def ensure_app_state_dir() -> None:
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_json(path: Path, fallback: Any) -> Any:
    ensure_app_state_dir()
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _save_json(path: Path, value: Any) -> None:
    ensure_app_state_dir()
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def load_settings() -> dict[str, Any]:
    stored = _load_json(SETTINGS_PATH, {})
    merged = DEFAULT_SETTINGS.copy()
    if isinstance(stored, dict):
        merged.update(stored)
    return merged


def save_settings(settings: Mapping[str, Any]) -> dict[str, Any]:
    merged = DEFAULT_SETTINGS.copy()
    merged.update(dict(settings))
    _save_json(SETTINGS_PATH, merged)
    return merged


def load_app_state() -> dict[str, Any]:
    state = default_app_state()
    stored = _load_json(STATE_PATH, {})
    if isinstance(stored, dict):
        _deep_update(state, stored)
    return state


def save_app_state(state: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = default_app_state()
    _deep_update(snapshot, dict(state))
    snapshot["app"]["lastUpdatedAt"] = now_iso()
    _save_json(STATE_PATH, snapshot)
    return snapshot


def update_app_state(patch: Mapping[str, Any]) -> dict[str, Any]:
    state = load_app_state()
    _deep_update(state, dict(patch))
    return save_app_state(state)


def reset_app_state() -> dict[str, Any]:
    state = default_app_state()
    settings = load_settings()
    state["app"]["mode"] = "advanced" if settings.get("debugMode") else "normal"
    save_app_state(state)
    clear_commands()
    return state


def clear_commands() -> None:
    _save_json(COMMANDS_PATH, [])


def enqueue_command(action: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    commands = _load_json(COMMANDS_PATH, [])
    if not isinstance(commands, list):
        commands = []
    command = {
        "id": f"cmd-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        "action": action,
        "payload": dict(payload or {}),
        "createdAt": now_iso(),
    }
    commands.append(command)
    _save_json(COMMANDS_PATH, commands)
    return command


def pop_pending_commands() -> list[dict[str, Any]]:
    commands = _load_json(COMMANDS_PATH, [])
    if not isinstance(commands, list):
        commands = []
    clear_commands()
    return [command for command in commands if isinstance(command, dict)]


def save_scan_preview_bytes(image_bytes: bytes) -> None:
    ensure_app_state_dir()
    temp_path = SCAN_PREVIEW_PATH.with_suffix(".tmp")
    temp_path.write_bytes(image_bytes)
    os.replace(temp_path, SCAN_PREVIEW_PATH)


def scan_preview_exists() -> bool:
    return SCAN_PREVIEW_PATH.exists()


def load_calibration_store() -> dict[str, list[int]]:
    state = load_app_state()
    calibration_state = state.get("calibration", {})
    colors = calibration_state.get("colors", {}) if isinstance(calibration_state, dict) else {}
    normalized: dict[str, list[int]] = {}
    if not isinstance(colors, dict):
        return normalized

    for color_name in CALIBRATION_COLORS:
        value = colors.get(color_name)
        if (
            isinstance(value, list)
            and len(value) == 3
            and all(isinstance(component, (int, float)) for component in value)
        ):
            normalized[color_name] = [int(component) for component in value]
    return normalized


def save_calibration_store(colors: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, list[int]] = {}
    for color_name in CALIBRATION_COLORS:
        value = colors.get(color_name)
        if (
            isinstance(value, list)
            and len(value) == 3
            and all(isinstance(component, (int, float)) for component in value)
        ):
            normalized[color_name] = [int(component) for component in value]

    return update_app_state(
        {
            "calibration": {
                "colors": normalized,
                "lastUpdatedAt": now_iso(),
            }
        }
    )


def set_calibration_color(color_name: str, bgr: list[int]) -> dict[str, Any]:
    if color_name not in CALIBRATION_COLORS:
        raise ValueError(f"Unsupported calibration color: {color_name}")
    colors = load_calibration_store()
    colors[color_name] = [int(component) for component in bgr]
    return save_calibration_store(colors)


def clear_calibration_color(color_name: str) -> dict[str, Any]:
    if color_name not in CALIBRATION_COLORS:
        raise ValueError(f"Unsupported calibration color: {color_name}")
    colors = load_calibration_store()
    colors.pop(color_name, None)
    return save_calibration_store(colors)


def clear_all_calibration_data() -> dict[str, Any]:
    return save_calibration_store({})


def load_evaluation_state() -> dict[str, Any]:
    state = load_app_state()
    return _ensure_evaluation_state(state)


def update_evaluation_metadata(
    *,
    trial_id: str | None = None,
    lighting_condition: str | None = None,
    start_new: bool = False,
) -> dict[str, Any]:
    state = load_app_state()
    evaluation = _ensure_evaluation_state(state)

    if start_new:
        _archive_current_trial(evaluation)
        previous_client_info = (
            evaluation.get("currentTrial", {}).get("clientInfo", {})
            if isinstance(evaluation.get("currentTrial"), dict)
            else {}
        )
        evaluation["currentTrial"] = default_evaluation_trial()
        if isinstance(previous_client_info, dict):
            _deep_update(evaluation["currentTrial"]["clientInfo"], previous_client_info)

    trial = _ensure_current_trial(evaluation)
    _ensure_trial_identity(trial)

    if trial_id is not None:
        trial["trialId"] = str(trial_id).strip()
    if lighting_condition is not None:
        trial["lightingCondition"] = str(lighting_condition).strip()

    if not trial.get("trialStartedAt"):
        trial["trialStartedAt"] = now_iso()

    _record_trial_event(trial, "trial_metadata_updated")
    return save_app_state(state)


def reset_evaluation_trial_data(*, preserve_metadata: bool = True) -> dict[str, Any]:
    state = load_app_state()
    evaluation = _ensure_evaluation_state(state)
    trial = _ensure_current_trial(evaluation)

    preserved_client_info = trial.get("clientInfo", {}) if isinstance(trial.get("clientInfo"), dict) else {}
    preserved_trial_id = trial.get("trialId", "") if preserve_metadata else ""
    preserved_lighting = trial.get("lightingCondition", "") if preserve_metadata else ""
    preserved_trial_started_at = trial.get("trialStartedAt") if preserve_metadata else None

    evaluation["currentTrial"] = default_evaluation_trial()
    next_trial = _ensure_current_trial(evaluation)
    if preserve_metadata:
        next_trial["trialId"] = preserved_trial_id
        next_trial["lightingCondition"] = preserved_lighting
        next_trial["trialStartedAt"] = preserved_trial_started_at or now_iso()
    if isinstance(preserved_client_info, dict):
        _deep_update(next_trial["clientInfo"], preserved_client_info)

    _record_trial_event(next_trial, "trial_workflow_reset")
    return save_app_state(state)


def record_evaluation_client_info(
    *,
    user_agent: str | None = None,
    app_version: str | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    state = load_app_state()
    trial = _ensure_current_trial(_ensure_evaluation_state(state))

    client_info = trial.setdefault("clientInfo", {})
    client_info["userAgent"] = user_agent or client_info.get("userAgent")
    client_info["appVersion"] = app_version or client_info.get("appVersion")
    client_info["platform"] = platform or client_info.get("platform")

    return save_app_state(state)


def record_evaluation_preview_metrics(
    *,
    fps_approx: float | None,
    source: str = "browser",
    target_fps: float | None = None,
) -> dict[str, Any]:
    state = load_app_state()
    trial = _ensure_current_trial(_ensure_evaluation_state(state))

    trial["previewFpsApprox"] = None if fps_approx is None else round(float(fps_approx), 2)
    trial["previewFpsSource"] = source
    if target_fps is not None:
        trial["previewTargetFps"] = round(float(target_fps), 2)

    return save_app_state(state)


def record_evaluation_error(source: str, message: str) -> dict[str, Any]:
    state = load_app_state()
    trial = _ensure_current_trial(_ensure_evaluation_state(state))

    errors = trial.setdefault("errors", [])
    next_error = {
        "at": now_iso(),
        "source": source,
        "message": message,
    }
    if not errors or errors[-1] != next_error:
        errors.append(next_error)
    _record_trial_event(trial, "error_recorded", source=source, message=message)
    return save_app_state(state)


def record_evaluation_scan_capture(
    *,
    slot: str,
    scanned_faces: Mapping[str, Any],
    effective_faces: Mapping[str, Any],
    summary: Mapping[str, Any],
    calibration_enabled: bool,
) -> dict[str, Any]:
    state = load_app_state()
    trial = _ensure_current_trial(_ensure_evaluation_state(state))

    _ensure_trial_identity(trial)
    if not trial.get("scanStartedAt"):
        trial["scanStartedAt"] = now_iso()

    trial["calibrationEnabled"] = bool(calibration_enabled)
    _sync_trial_faces(trial, scanned_faces, effective_faces)

    captured_face_count = int(summary.get("capturedFaceCount", 0) or 0)
    if captured_face_count >= len(FACE_ORDER) and not trial.get("scanCompletedAt"):
        trial["scanCompletedAt"] = now_iso()

    if captured_face_count >= len(FACE_ORDER) and trial.get("initialValidation") is None:
        trial["initialValidation"] = _build_validation_snapshot(summary)

    _record_trial_event(trial, "face_captured", slot=slot, capturedFaceCount=captured_face_count)
    return save_app_state(state)


def record_evaluation_validation(summary: Mapping[str, Any], *, phase: str = "final") -> dict[str, Any]:
    state = load_app_state()
    trial = _ensure_current_trial(_ensure_evaluation_state(state))

    snapshot = _build_validation_snapshot(summary)
    if phase == "initial" and trial.get("initialValidation") is None:
        trial["initialValidation"] = snapshot
    elif phase == "initial":
        trial["initialValidation"] = snapshot
    else:
        trial["finalValidation"] = snapshot

    _record_trial_event(trial, "validation_recorded", phase=phase, valid=snapshot["deepValidation"]["ok"])
    return save_app_state(state)


def record_evaluation_solver_result(
    *,
    kind: str,
    success: bool,
    move_count: int,
    error: str | None = None,
) -> dict[str, Any]:
    state = load_app_state()
    trial = _ensure_current_trial(_ensure_evaluation_state(state))
    trial["solver"] = {
        "kind": kind,
        "success": bool(success),
        "moveCount": int(move_count),
        "error": error,
        "solvedAt": now_iso(),
    }
    _record_trial_event(
        trial,
        "solver_recorded",
        kind=kind,
        success=bool(success),
        moveCount=int(move_count),
    )
    return save_app_state(state)


def scanned_cube_state_from_store() -> CubeState:
    state = load_app_state()
    faces = state.get("scanner", {}).get("faces", {})
    if not isinstance(faces, dict):
        faces = {slot: None for slot in FACE_ORDER}
    return CubeState.from_faces_dict(faces)


def cube_state_from_store() -> CubeState:
    state = load_app_state()
    scanned_faces = state.get("scanner", {}).get("faces", {})
    overrides = state.get("corrections", {}).get("overrides", {})
    effective_faces = merged_faces_from_state(scanned_faces if isinstance(scanned_faces, dict) else {}, overrides if isinstance(overrides, dict) else {})
    return CubeState.from_faces_dict(effective_faces)


def merged_faces_from_state(scanned_faces: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    cube_state = CubeState.from_faces_dict(scanned_faces)
    faces = cube_state.to_faces_dict()
    for key, color in overrides.items():
        parsed = _parse_override_key(key)
        if parsed is None:
            continue
        slot, row, col = parsed
        if slot not in faces or faces[slot] is None:
            continue
        faces[slot][row][col] = color
    return faces


def manual_edit_mask(overrides: Mapping[str, Any]) -> dict[str, list[list[bool]]]:
    mask = {slot: [[False] * 3 for _ in range(3)] for slot in FACE_ORDER}
    for key in overrides.keys():
        parsed = _parse_override_key(key)
        if parsed is None:
            continue
        slot, row, col = parsed
        mask[slot][row][col] = True
    return mask


def apply_manual_edit(slot: str, row: int, col: int, color: str) -> dict[str, Any]:
    if slot not in FACE_ORDER:
        raise ValueError(f"Invalid face slot: {slot}")
    if row not in range(3) or col not in range(3):
        raise ValueError("Sticker coordinates must be within 0..2")
    if row == 1 and col == 1:
        raise ValueError("Center stickers are locked.")
    if color not in EDITABLE_COLORS:
        raise ValueError(f"Unsupported color: {color}")

    state = load_app_state()
    scanned_faces = state.get("scanner", {}).get("faces", {})
    if slot not in scanned_faces or scanned_faces[slot] is None:
        raise ValueError("Cannot edit a face that has not been captured yet.")

    corrections = state.setdefault("corrections", {"overrides": {}, "history": [], "lastEditedAt": None})
    overrides = corrections.setdefault("overrides", {})
    history = corrections.setdefault("history", [])

    effective_faces = merged_faces_from_state(scanned_faces, overrides)
    previous_color = effective_faces[slot][row][col]
    if previous_color == color:
        return save_app_state(state)

    key = _override_key(slot, row, col)
    scanned_color = scanned_faces[slot][row][col]
    if color == scanned_color:
        overrides.pop(key, None)
    else:
        overrides[key] = color

    history.append(
        {
            "slot": slot,
            "row": row,
            "col": col,
            "previousColor": previous_color,
            "newColor": color,
            "editedAt": now_iso(),
        }
    )
    corrections["lastEditedAt"] = now_iso()
    state["solves"] = {"standard": None, "cfop": None}
    _refresh_evaluation_after_manual_change(state)
    return save_app_state(state)


def undo_manual_edit() -> dict[str, Any]:
    state = load_app_state()
    corrections = state.setdefault("corrections", {"overrides": {}, "history": [], "lastEditedAt": None})
    overrides = corrections.setdefault("overrides", {})
    history = corrections.setdefault("history", [])
    scanned_faces = state.get("scanner", {}).get("faces", {})

    if not history:
        return save_app_state(state)

    last_edit = history.pop()
    slot = last_edit["slot"]
    row = last_edit["row"]
    col = last_edit["col"]
    previous_color = last_edit["previousColor"]
    key = _override_key(slot, row, col)

    scanned_color = None
    if isinstance(scanned_faces, dict) and scanned_faces.get(slot) is not None:
        scanned_color = scanned_faces[slot][row][col]

    if previous_color == scanned_color:
        overrides.pop(key, None)
    else:
        overrides[key] = previous_color

    corrections["lastEditedAt"] = now_iso() if history else None
    state["solves"] = {"standard": None, "cfop": None}
    _refresh_evaluation_after_manual_change(state)
    return save_app_state(state)


def reset_manual_edits() -> dict[str, Any]:
    state = load_app_state()
    state["corrections"] = {"overrides": {}, "history": [], "lastEditedAt": None}
    state["solves"] = {"standard": None, "cfop": None}
    _refresh_evaluation_after_manual_change(state)
    return save_app_state(state)


def clear_manual_edits_for_slot(slot: str) -> dict[str, Any]:
    state = load_app_state()
    corrections = state.setdefault("corrections", {"overrides": {}, "history": [], "lastEditedAt": None})
    overrides = corrections.setdefault("overrides", {})
    history = corrections.setdefault("history", [])

    for key in [key for key in list(overrides.keys()) if key.startswith(f"{slot}:")]:
        overrides.pop(key, None)
    corrections["history"] = [entry for entry in history if entry.get("slot") != slot]
    corrections["lastEditedAt"] = now_iso() if corrections["history"] else None
    state["solves"] = {"standard": None, "cfop": None}
    _refresh_evaluation_after_manual_change(state)
    return save_app_state(state)


def clear_all_manual_edits() -> dict[str, Any]:
    return reset_manual_edits()


def summarize_cube_state(cube_state: CubeState) -> dict[str, Any]:
    basic_ok, basic_errors = cube_state.validate()
    deep_result = cube_state.validate_deep() if cube_state.is_complete() else None

    facelet_string = None
    if cube_state.is_complete():
        try:
            facelet_string = cube_state.to_facelet_string()
        except Exception:
            facelet_string = None

    return {
        "complete": cube_state.is_complete(),
        "capturedFaceCount": sum(1 for slot in FACE_ORDER if cube_state.faces[slot] is not None),
        "capturedFaces": {slot: cube_state.faces[slot] is not None for slot in FACE_ORDER},
        "faces": cube_state.to_faces_dict(),
        "basicValidation": {
            "ok": basic_ok,
            "errors": basic_errors,
        },
        "deepValidation": {
            "ok": False if deep_result is None else deep_result.is_valid,
            "errors": [] if deep_result is None else deep_result.errors,
            "warnings": [] if deep_result is None else deep_result.warnings,
        },
        "faceletString": facelet_string,
    }


def _override_key(slot: str, row: int, col: int) -> str:
    return f"{slot}:{row}:{col}"


def _parse_override_key(key: str) -> tuple[str, int, int] | None:
    try:
        slot, row, col = key.split(":", 2)
        return slot, int(row), int(col)
    except Exception:
        return None


def _ensure_evaluation_state(state: dict[str, Any]) -> dict[str, Any]:
    evaluation = state.setdefault("evaluation", {"currentTrial": default_evaluation_trial(), "history": []})
    if not isinstance(evaluation, dict):
        evaluation = {"currentTrial": default_evaluation_trial(), "history": []}
        state["evaluation"] = evaluation

    if not isinstance(evaluation.get("history"), list):
        evaluation["history"] = []

    trial = default_evaluation_trial()
    current_trial = evaluation.get("currentTrial")
    if isinstance(current_trial, dict):
        _deep_update(trial, current_trial)
    evaluation["currentTrial"] = trial
    return evaluation


def _ensure_current_trial(evaluation: dict[str, Any]) -> dict[str, Any]:
    current_trial = evaluation.get("currentTrial")
    if not isinstance(current_trial, dict):
        current_trial = default_evaluation_trial()
        evaluation["currentTrial"] = current_trial
    return current_trial


def _ensure_trial_identity(trial: dict[str, Any]) -> None:
    if not trial.get("trialId"):
        trial["trialId"] = f"trial-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    if not trial.get("trialStartedAt"):
        trial["trialStartedAt"] = now_iso()


def _trial_has_activity(trial: Mapping[str, Any]) -> bool:
    return any(
        [
            trial.get("scanStartedAt"),
            trial.get("scanCompletedAt"),
            trial.get("manualCorrections"),
            trial.get("initialValidation"),
            trial.get("finalValidation"),
            trial.get("errors"),
            trial.get("events"),
            (trial.get("solver", {}) if isinstance(trial.get("solver"), Mapping) else {}).get("solvedAt"),
        ]
    )


def _archive_current_trial(evaluation: dict[str, Any]) -> None:
    current_trial = _ensure_current_trial(evaluation)
    if not _trial_has_activity(current_trial):
        return
    archived = default_evaluation_trial()
    _deep_update(archived, current_trial)
    history = evaluation.setdefault("history", [])
    if isinstance(history, list):
        history.append(archived)


def _record_trial_event(trial: dict[str, Any], event_type: str, **payload: Any) -> None:
    events = trial.setdefault("events", [])
    if not isinstance(events, list):
        events = []
        trial["events"] = events
    event = {"at": now_iso(), "kind": event_type}
    for key, value in payload.items():
        event[key] = value
    events.append(event)


def _normalize_faces_dict(faces: Mapping[str, Any]) -> dict[str, Any]:
    return CubeState.from_faces_dict(faces).to_faces_dict()


def _build_validation_snapshot(summary: Mapping[str, Any]) -> dict[str, Any]:
    basic_validation = summary.get("basicValidation", {}) if isinstance(summary.get("basicValidation"), Mapping) else {}
    deep_validation = summary.get("deepValidation", {}) if isinstance(summary.get("deepValidation"), Mapping) else {}
    return {
        "recordedAt": now_iso(),
        "complete": bool(summary.get("complete")),
        "capturedFaceCount": int(summary.get("capturedFaceCount", 0) or 0),
        "basicValidation": {
            "ok": bool(basic_validation.get("ok")),
            "errors": list(basic_validation.get("errors", []) or []),
        },
        "deepValidation": {
            "ok": bool(deep_validation.get("ok")),
            "errors": list(deep_validation.get("errors", []) or []),
            "warnings": list(deep_validation.get("warnings", []) or []),
        },
        "faceletString": summary.get("faceletString"),
    }


def _sync_trial_faces(
    trial: dict[str, Any],
    scanned_faces: Mapping[str, Any],
    effective_faces: Mapping[str, Any],
) -> None:
    recognized = trial.setdefault("recognizedStickerColors", {})
    recognized["scannedFaces"] = _normalize_faces_dict(scanned_faces)
    recognized["effectiveFaces"] = _normalize_faces_dict(effective_faces)


def _refresh_evaluation_after_manual_change(state: dict[str, Any]) -> None:
    evaluation = _ensure_evaluation_state(state)
    trial = _ensure_current_trial(evaluation)
    _ensure_trial_identity(trial)

    scanned_faces = state.get("scanner", {}).get("faces", {})
    overrides = state.get("corrections", {}).get("overrides", {})
    effective_faces = merged_faces_from_state(
        scanned_faces if isinstance(scanned_faces, Mapping) else {},
        overrides if isinstance(overrides, Mapping) else {},
    )
    summary = summarize_cube_state(CubeState.from_faces_dict(effective_faces))

    _sync_trial_faces(
        trial,
        scanned_faces if isinstance(scanned_faces, Mapping) else {},
        effective_faces,
    )
    trial["manualCorrections"] = list(state.get("corrections", {}).get("history", []) or [])
    calibration_state = state.get("calibration", {}) if isinstance(state.get("calibration"), Mapping) else {}
    calibration_colors = calibration_state.get("colors", {}) if isinstance(calibration_state.get("colors"), Mapping) else {}
    trial["calibrationEnabled"] = bool(calibration_colors)
    trial["finalValidation"] = _build_validation_snapshot(summary)
    _record_trial_event(
        trial,
        "manual_correction_updated",
        manualCorrectionCount=len(trial["manualCorrections"]),
        deepValid=trial["finalValidation"]["deepValidation"]["ok"],
    )


def _deep_update(base: dict[str, Any], patch: Mapping[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)  # type: ignore[index]
        else:
            base[key] = value
