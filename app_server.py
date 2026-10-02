from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from cube_backend.app_state import (
    CALIBRATION_COLORS,
    LAST_PLAYBACK_SESSION_PATH,
    LAST_VIEW_SNAPSHOT_PATH,
    REPO_ROOT,
    SCAN_PREVIEW_PATH,
    apply_manual_edit,
    clear_all_calibration_data,
    clear_calibration_color,
    clear_all_manual_edits,
    cube_state_from_store,
    enqueue_command,
    load_calibration_store,
    load_app_state,
    load_evaluation_state,
    load_settings,
    manual_edit_mask,
    now_iso,
    record_evaluation_client_info,
    record_evaluation_error,
    record_evaluation_preview_metrics,
    record_evaluation_solver_result,
    record_evaluation_validation,
    reset_app_state,
    save_app_state,
    save_settings,
    scanned_cube_state_from_store,
    set_calibration_color,
    summarize_cube_state,
    update_evaluation_metadata,
    undo_manual_edit,
    update_app_state,
)
from cube_backend.cfop_solver import build_cfop_playback_session, solve_cfop_from_cube_state
from cube_backend.cube_state import FACE_ORDER
from cube_backend.move_utils import parse_alg
from cube_backend.playback_session import build_playback_session, save_playback_session
from cube_backend.solver_bridge import format_solution_for_display
from cube_backend.web_viewer_session import ViewerSessionError, build_web_viewer_session
from cube_backend.viewer_snapshot import cube_state_to_view_snapshot, save_view_snapshot

HOST = "127.0.0.1"
PORT = 8765
DIST_DIR = REPO_ROOT / "webapp" / "dist"
WEBAPP_DIR = REPO_ROOT / "webapp"
VIEWER_SCRIPT = REPO_ROOT / "cube_viewer_3d.py"
SCANNER_SCRIPT = REPO_ROOT / "camera_test.py"

SHORTCUTS = [
    {"key": "Space", "label": "Capture face"},
    {"key": "N / P", "label": "Next / previous face"},
    {"key": "X / Z", "label": "Clear face / reset cube"},
    {"key": "O", "label": "Standard solve"},
    {"key": "Y", "label": "CFOP Beta solve"},
    {"key": "3 / 4 / 5", "label": "Open 3D / standard playback / CFOP playback"},
    {"key": "H", "label": "Toggle CFOP analysis overlay"},
    {"key": "Viewer ← / →", "label": "Previous / next move"},
    {"key": "Viewer Space / K", "label": "Play / pause playback"},
    {"key": "Viewer Home / End", "label": "Jump to start / solved state"},
    {"key": "Viewer R / Esc", "label": "Reset view / pause playback"},
]

SCANNER_STATE_POLL_MS = 1000
SCANNER_PREVIEW_TARGET_FPS = 12
SERVER_PERF_LOG_INTERVAL = 5.0
SCANNER_STATE_STALE_SECONDS = 3.0
SCANNER_PREVIEW_STALE_SECONDS = 3.0

_PREVIEW_CACHE_LOCK = threading.Lock()
_PREVIEW_CACHE = {
    "mtime_ns": None,
    "bytes": None,
}
_SERVER_METRICS_LOCK = threading.Lock()
_SERVER_METRICS = {
    "scanner_state": {"count": 0, "total_ms": 0.0, "bytes": 0, "last_log_at": time.monotonic()},
    "app_state": {"count": 0, "total_ms": 0.0, "bytes": 0, "last_log_at": time.monotonic()},
}


def _safe_module_version(module_name: str) -> str | None:
    try:
        module = __import__(module_name)
    except Exception:
        return None
    return getattr(module, "__version__", None) or "installed"


def _build_system_info_payload(state: dict | None = None) -> dict:
    if state is None:
        state = load_app_state()

    scanner = state.get("scanner", {}) if isinstance(state.get("scanner"), dict) else {}
    evaluation = state.get("evaluation", {}) if isinstance(state.get("evaluation"), dict) else {}
    current_trial = evaluation.get("currentTrial", {}) if isinstance(evaluation.get("currentTrial"), dict) else {}
    client_info = current_trial.get("clientInfo", {}) if isinstance(current_trial.get("clientInfo"), dict) else {}

    try:
        import cv2  # type: ignore
        opencv_version = getattr(cv2, "__version__", "installed")
    except Exception:
        opencv_version = None

    return {
        "generatedAt": now_iso(),
        "pythonVersion": sys.version.replace("\n", " "),
        "opencvVersion": opencv_version,
        "browser": {
            "userAgent": client_info.get("userAgent"),
            "appVersion": client_info.get("appVersion"),
            "platform": client_info.get("platform"),
        },
        "camera": {
            "resolution": scanner.get("cameraResolution"),
            "deviceIndex": load_settings().get("cameraDeviceIndex", 0),
        },
        "preview": {
            "configuredTargetFps": scanner.get("previewTargetFps", SCANNER_PREVIEW_TARGET_FPS),
            "approxDisplayedFps": current_trial.get("previewFpsApprox"),
            "fpsSource": current_trial.get("previewFpsSource"),
            "stillEndpoint": scanner.get("previewStillUrl", "/api/scanner/preview.jpg"),
            "streamEndpoint": scanner.get("previewUrl", "/api/scanner/preview.mjpeg"),
        },
        "solvers": {
            "standard": {
                "engine": "kociemba",
                "version": _safe_module_version("kociemba"),
            },
            "cfopBeta": {
                "engine": "PyCube-Solver",
                "version": "vendored",
            },
        },
        "app": {
            "name": state.get("app", {}).get("name", "CubeFlow"),
            "mode": state.get("app", {}).get("mode", "normal"),
            "serverVersion": AppHandler.server_version,
        },
    }


def _build_evaluation_payload(state: dict) -> dict:
    evaluation = state.get("evaluation", {}) if isinstance(state.get("evaluation"), dict) else load_evaluation_state()
    return {
        **evaluation,
        "exportUrls": {
            "json": "/api/evaluation/export.json",
            "csv": "/api/evaluation/export.csv",
            "system": "/api/evaluation/system-info.json",
        },
        "systemInfo": _build_system_info_payload(state),
    }


def _trial_rows_for_export(state: dict) -> list[dict]:
    evaluation = state.get("evaluation", {}) if isinstance(state.get("evaluation"), dict) else load_evaluation_state()
    trials = []
    history = evaluation.get("history", [])
    if isinstance(history, list):
        trials.extend([trial for trial in history if isinstance(trial, dict)])
    current_trial = evaluation.get("currentTrial")
    if isinstance(current_trial, dict):
        trials.append(current_trial)
    return trials


def _build_evaluation_export_payload(state: dict) -> dict:
    return {
        "generatedAt": now_iso(),
        "app": {
            "name": state.get("app", {}).get("name", "CubeFlow"),
            "lastUpdatedAt": state.get("app", {}).get("lastUpdatedAt"),
        },
        "evaluation": state.get("evaluation", {}) if isinstance(state.get("evaluation"), dict) else load_evaluation_state(),
        "systemInfo": _build_system_info_payload(state),
    }


def _build_faces_json(faces: dict | None) -> str:
    return json.dumps(faces or {}, separators=(",", ":"), sort_keys=True)


def _build_evaluation_csv_text(state: dict) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "trial_id",
            "lighting_condition",
            "trial_started_at",
            "scan_started_at",
            "scan_completed_at",
            "calibration_enabled",
            "manual_correction_count",
            "initial_basic_valid",
            "initial_deep_valid",
            "final_basic_valid",
            "final_deep_valid",
            "solver_kind",
            "solver_success",
            "solution_move_count",
            "preview_fps_approx",
            "preview_target_fps",
            "errors",
            "browser_user_agent",
            "browser_app_version",
            "browser_platform",
            "recognized_scanned_faces",
            "recognized_effective_faces",
        ],
    )
    writer.writeheader()

    for trial in _trial_rows_for_export(state):
        initial_validation = trial.get("initialValidation", {}) if isinstance(trial.get("initialValidation"), dict) else {}
        final_validation = trial.get("finalValidation", {}) if isinstance(trial.get("finalValidation"), dict) else {}
        solver = trial.get("solver", {}) if isinstance(trial.get("solver"), dict) else {}
        client_info = trial.get("clientInfo", {}) if isinstance(trial.get("clientInfo"), dict) else {}
        recognized = trial.get("recognizedStickerColors", {}) if isinstance(trial.get("recognizedStickerColors"), dict) else {}
        writer.writerow(
            {
                "trial_id": trial.get("trialId", ""),
                "lighting_condition": trial.get("lightingCondition", ""),
                "trial_started_at": trial.get("trialStartedAt", ""),
                "scan_started_at": trial.get("scanStartedAt", ""),
                "scan_completed_at": trial.get("scanCompletedAt", ""),
                "calibration_enabled": bool(trial.get("calibrationEnabled")),
                "manual_correction_count": len(trial.get("manualCorrections", []) or []),
                "initial_basic_valid": (initial_validation.get("basicValidation", {}) or {}).get("ok"),
                "initial_deep_valid": (initial_validation.get("deepValidation", {}) or {}).get("ok"),
                "final_basic_valid": (final_validation.get("basicValidation", {}) or {}).get("ok"),
                "final_deep_valid": (final_validation.get("deepValidation", {}) or {}).get("ok"),
                "solver_kind": solver.get("kind"),
                "solver_success": solver.get("success"),
                "solution_move_count": solver.get("moveCount"),
                "preview_fps_approx": trial.get("previewFpsApprox"),
                "preview_target_fps": trial.get("previewTargetFps"),
                "errors": json.dumps(trial.get("errors", []) or [], separators=(",", ":")),
                "browser_user_agent": client_info.get("userAgent"),
                "browser_app_version": client_info.get("appVersion"),
                "browser_platform": client_info.get("platform"),
                "recognized_scanned_faces": _build_faces_json(recognized.get("scannedFaces")),
                "recognized_effective_faces": _build_faces_json(recognized.get("effectiveFaces")),
            }
        )

    return output.getvalue()


def _build_calibration_payload(state: dict) -> dict:
    calibration_state = state.get("calibration", {}) if isinstance(state.get("calibration"), dict) else {}
    colors = load_calibration_store()
    rows = [
        {
            "name": color_name,
            "captured": color_name in colors,
            "sampleBgr": colors.get(color_name),
        }
        for color_name in CALIBRATION_COLORS
    ]
    return {
        "colors": colors,
        "rows": rows,
        "capturedCount": len(colors),
        "allCaptured": len(colors) == len(CALIBRATION_COLORS),
        "lastUpdatedAt": calibration_state.get("lastUpdatedAt"),
    }


def build_frontend_state() -> dict:
    state = load_app_state()
    settings = load_settings()
    scanned_cube_state = scanned_cube_state_from_store()
    cube_state = cube_state_from_store()
    summary = summarize_cube_state(cube_state)
    scanned_summary = summarize_cube_state(scanned_cube_state)
    overrides = state.get("corrections", {}).get("overrides", {})
    manual_mask = manual_edit_mask(overrides if isinstance(overrides, dict) else {})
    manual_edit_count = len(overrides) if isinstance(overrides, dict) else 0

    state["settings"] = settings
    state["review"] = {
        **state.get("review", {}),
        **summary,
        "scannedFaces": scanned_summary["faces"],
        "manualMask": manual_mask,
        "manualEditCount": manual_edit_count,
        "editableColors": ["WHITE", "YELLOW", "RED", "ORANGE", "BLUE", "GREEN", "UNKNOWN"],
        "centersLocked": True,
        "lastValidatedAt": state.get("review", {}).get("lastValidatedAt"),
    }
    state["scanner"]["capturedFaces"] = summary["capturedFaces"]
    state["scanner"]["faces"] = summary["faces"]
    state["scanner"]["scannedFaces"] = scanned_summary["faces"]
    state["scanner"]["manualEditCount"] = manual_edit_count
    scanner_health = _compute_scanner_health(state)
    state["scanner"]["previewUrl"] = "/api/scanner/preview.mjpeg"
    state["scanner"]["previewUpdatedAt"] = state["scanner"].get("previewUpdatedAt")
    state["scanner"]["lastUpdatedAt"] = state.get("app", {}).get("lastUpdatedAt")
    state["scanner"].update(scanner_health)
    state["scanner"]["capturedFaceCount"] = summary["capturedFaceCount"]
    state["scanner"]["previewStillUrl"] = "/api/scanner/preview.jpg"
    state["scanner"]["previewTargetFps"] = 10
    state["calibration"] = _build_calibration_payload(state)
    state["evaluation"] = _build_evaluation_payload(state)
    state["scanner"].setdefault("advanced", {})
    state["scanner"]["advanced"]["calibration"] = state["calibration"]["colors"]
    state["home"] = {
        "heroTitle": "Scan. Validate. Solve.",
        "heroSubtitle": "Use your camera to capture a cube, review the state, and solve it with a stable or experimental workflow.",
        "primaryAction": "Scan Cube",
        "secondaryActions": ["Review Last Scan", "Open 3D Viewer", "Settings"],
        "betaNote": "CFOP Beta is experimental and may fail on some cases.",
        "lastValidationLabel": _build_last_validation_label(summary),
        "lastScannedAt": state.get("recent", {}).get("lastScanTimestamp"),
    }
    state["labs"] = {
        "cfopBeta": {
            "enabled": settings.get("betaFeaturesEnabled", True),
            "label": "CFOP Beta",
            "description": "Experimental. Incomplete case coverage.",
        }
    }
    state["shortcuts"] = SHORTCUTS
    return state


def build_scanner_state() -> dict:
    state = load_app_state()
    settings = load_settings()
    scanned_cube_state = scanned_cube_state_from_store()
    cube_state = cube_state_from_store()
    summary = summarize_cube_state(cube_state)
    scanned_summary = summarize_cube_state(scanned_cube_state)
    scanner_health = _compute_scanner_health(state)
    overrides = state.get("corrections", {}).get("overrides", {})
    manual_mask = manual_edit_mask(overrides if isinstance(overrides, dict) else {})
    calibration_payload = _build_calibration_payload(state)

    return {
        "app": {
            "name": state.get("app", {}).get("name", "CubeFlow"),
            "subtitle": state.get("app", {}).get("subtitle", "Scan, validate, and solve your Rubik's cube."),
            "mode": state.get("app", {}).get("mode", "normal"),
            "lastUpdatedAt": state.get("app", {}).get("lastUpdatedAt"),
        },
        "settings": settings,
        "scanner": {
            **state.get("scanner", {}),
            **scanner_health,
            "capturedFaces": summary["capturedFaces"],
            "faces": summary["faces"],
            "scannedFaces": scanned_summary["faces"],
            "manualMask": manual_mask,
            "capturedFaceCount": summary["capturedFaceCount"],
            "previewUrl": "/api/scanner/preview.mjpeg",
            "previewStillUrl": "/api/scanner/preview.jpg",
            "previewTargetFps": 10,
            "statePollMs": SCANNER_STATE_POLL_MS,
            "lastUpdatedAt": state.get("app", {}).get("lastUpdatedAt"),
            "advanced": {
                **(state.get("scanner", {}).get("advanced", {}) if isinstance(state.get("scanner", {}).get("advanced", {}), dict) else {}),
                "calibration": calibration_payload["colors"],
            },
        },
        "calibration": calibration_payload,
        "evaluation": _build_evaluation_payload(state),
        "review": {
            **summary,
            "scannedFaces": scanned_summary["faces"],
            "manualMask": manual_mask,
            "manualEditCount": len(overrides) if isinstance(overrides, dict) else 0,
            "editableColors": ["WHITE", "YELLOW", "RED", "ORANGE", "BLUE", "GREEN", "UNKNOWN"],
            "centersLocked": True,
            "lastValidatedAt": state.get("review", {}).get("lastValidatedAt"),
        },
        "recent": state.get("recent", {}),
    }


def solve_standard() -> dict:
    cube_state = cube_state_from_store()
    summary = summarize_cube_state(cube_state)
    record_evaluation_validation(summary, phase="final")
    if not cube_state.is_complete():
        result = {
            "kind": "standard",
            "status": "incomplete",
            "beta": False,
            "title": "Standard Solve",
            "error": "Capture all 6 faces before solving.",
            "moves": [],
            "moveCount": 0,
            "moveString": "",
            "formatted": None,
            "lastSolvedAt": now_iso(),
        }
        record_evaluation_solver_result(kind="standard", success=False, move_count=0, error=result["error"])
        record_evaluation_error("standard-solve", result["error"])
    else:
        solve_result = cube_state.solve()
        result = {
            "kind": "standard",
            "status": "success" if solve_result.success else "error",
            "beta": False,
            "title": "Standard Solve",
            "error": solve_result.error,
            "moves": solve_result.move_list,
            "moveCount": len(solve_result.move_list),
            "moveString": solve_result.moves,
            "formatted": format_solution_for_display(solve_result),
            "facelets": solve_result.facelets,
            "lastSolvedAt": now_iso(),
        }
        record_evaluation_solver_result(
            kind="standard",
            success=solve_result.success,
            move_count=len(solve_result.move_list),
            error=solve_result.error,
        )
        if not solve_result.success and solve_result.error:
            record_evaluation_error("standard-solve", solve_result.error)
    update_app_state({"solves": {"standard": result}})
    return result


def solve_cfop() -> dict:
    cube_state = cube_state_from_store()
    summary = summarize_cube_state(cube_state)
    record_evaluation_validation(summary, phase="final")
    result = solve_cfop_from_cube_state(cube_state)
    payload = {
        "kind": "cfop",
        "status": "success" if result.success else "error",
        "beta": True,
        "title": "CFOP Beta",
        "poweredBy": "PyCube-Solver",
        "error": result.error,
        "failingStage": result.failing_stage,
        "failingSlot": result.failing_slot,
        "failingCaseId": result.failing_case_id,
        "setupText": result.setup_text,
        "orientationInstruction": result.setup_text,
        "orientation": result.orientation,
        "moveCount": len(result.full_moves),
        "totalMoveCount": len(result.full_moves),
        "moveString": result.display_move_string or result.full_move_string,
        "moves": result.display_moves or result.full_moves,
        "allMoves": result.display_moves or result.full_moves,
        "internalMoves": result.full_moves,
        "segmentationSource": result.segmentation_source,
        "segmentationVerified": result.segmentation_verified,
        "segmentationWarning": result.segmentation_warning,
        "stages": [
            {
                "id": (stage.case_id or stage.name).lower(),
                "name": stage.name,
                "label": stage.name,
                "slot": stage.slot,
                "caseId": stage.case_id,
                "description": stage.description,
                "rotation": stage.cube_rotation,
                "displayMoves": stage.display_moves,
                "moves": stage.display_moves,
                "moveCount": len(stage.moves),
                "startIndex": sum(len(previous.moves) for previous in result.stages[:index]),
                "endIndex": sum(len(previous.moves) for previous in result.stages[:index + 1]),
                "success": stage.success,
                "error": stage.error,
            }
            for index, stage in enumerate(result.stages)
        ],
        "lastSolvedAt": now_iso(),
    }
    record_evaluation_solver_result(
        kind="cfop-beta",
        success=result.success,
        move_count=len(result.full_moves),
        error=result.error,
    )
    if not result.success and result.error:
        record_evaluation_error("cfop-beta", result.error)
    update_app_state({"solves": {"cfop": payload}})
    return payload


def open_current_viewer() -> dict:
    cube_state = cube_state_from_store()
    snapshot = cube_state_to_view_snapshot(cube_state)
    save_view_snapshot(snapshot, str(LAST_VIEW_SNAPSHOT_PATH))
    subprocess.Popen([sys.executable, str(VIEWER_SCRIPT), "--snapshot", str(LAST_VIEW_SNAPSHOT_PATH)], cwd=str(REPO_ROOT))
    update_app_state({"viewer": {"lastOpenedMode": "current", "lastOpenedAt": now_iso(), "lastSessionTitle": "Current Cube"}})
    return {"ok": True}


def open_standard_playback() -> dict:
    cube_state = cube_state_from_store()
    solve_result = cube_state.solve()
    if not solve_result.success:
        return {"ok": False, "error": solve_result.error or "Standard solve failed."}
    session = build_playback_session(
        facelets=solve_result.facelets,
        moves=solve_result.move_list or parse_alg(solve_result.moves or ""),
        title="Standard Solution Playback",
    )
    save_playback_session(session, str(LAST_PLAYBACK_SESSION_PATH))
    subprocess.Popen([sys.executable, str(VIEWER_SCRIPT), "--session", str(LAST_PLAYBACK_SESSION_PATH)], cwd=str(REPO_ROOT))
    update_app_state({"viewer": {"lastOpenedMode": "standard-playback", "lastOpenedAt": now_iso(), "lastSessionTitle": "Standard Solution Playback"}})
    return {"ok": True}


def open_cfop_playback() -> dict:
    cube_state = cube_state_from_store()
    result = solve_cfop_from_cube_state(cube_state)
    if not result.success:
        return {
            "ok": False,
            "error": result.error or "CFOP Beta could not solve this cube yet.",
            "failingStage": result.failing_stage,
            "failingSlot": result.failing_slot,
            "failingCaseId": result.failing_case_id,
        }
    session = build_cfop_playback_session(cube_state.to_facelet_string(), result, title="CFOP Beta Playback")
    save_playback_session(session, str(LAST_PLAYBACK_SESSION_PATH))
    subprocess.Popen([sys.executable, str(VIEWER_SCRIPT), "--session", str(LAST_PLAYBACK_SESSION_PATH)], cwd=str(REPO_ROOT))
    update_app_state({"viewer": {"lastOpenedMode": "cfop-playback", "lastOpenedAt": now_iso(), "lastSessionTitle": "CFOP Beta Playback"}})
    return {"ok": True}


def _compute_scanner_health(state: dict) -> dict:
    scanner_state = state.get("scanner", {})
    app_state = state.get("app", {})
    last_state_update = app_state.get("lastUpdatedAt")
    last_preview_update = scanner_state.get("previewUpdatedAt")

    state_available = _is_recent_iso(last_state_update, SCANNER_STATE_STALE_SECONDS)
    preview_available = SCAN_PREVIEW_PATH.exists() and _is_recent_iso(last_preview_update, SCANNER_PREVIEW_STALE_SECONDS)
    process_running = bool(scanner_state.get("running")) and state_available

    last_error = None
    if scanner_state.get("running") and not state_available:
        last_error = "Scanner state looks stale."
    elif process_running and not preview_available:
        last_error = "Preview stream is waiting for fresh frames."

    return {
        "processRunning": process_running,
        "previewAvailable": preview_available,
        "stateAvailable": state_available,
        "lastError": last_error,
    }


def _is_recent_iso(value: str | None, max_age_seconds: float) -> bool:
    if not value:
        return False
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError:
        return False
    return (datetime.now(timestamp.tzinfo) - timestamp).total_seconds() <= max_age_seconds


def _get_latest_preview_bytes() -> tuple[bytes | None, int | None]:
    if not SCAN_PREVIEW_PATH.exists():
        return None, None

    try:
        stat = SCAN_PREVIEW_PATH.stat()
    except FileNotFoundError:
        return None, None

    with _PREVIEW_CACHE_LOCK:
        if _PREVIEW_CACHE["mtime_ns"] == stat.st_mtime_ns and _PREVIEW_CACHE["bytes"] is not None:
            return _PREVIEW_CACHE["bytes"], stat.st_mtime_ns

        frame_bytes = SCAN_PREVIEW_PATH.read_bytes()
        _PREVIEW_CACHE["mtime_ns"] = stat.st_mtime_ns
        _PREVIEW_CACHE["bytes"] = frame_bytes
        return frame_bytes, stat.st_mtime_ns


def _log_server_metric(label: str, duration_ms: float, payload_size: int) -> None:
    with _SERVER_METRICS_LOCK:
        metric = _SERVER_METRICS[label]
        metric["count"] += 1
        metric["total_ms"] += duration_ms
        metric["bytes"] += payload_size
        now = time.monotonic()
        if now - metric["last_log_at"] >= SERVER_PERF_LOG_INTERVAL:
            avg_ms = metric["total_ms"] / metric["count"] if metric["count"] else 0.0
            avg_kb = (metric["bytes"] / metric["count"] / 1024.0) if metric["count"] else 0.0
            rate = metric["count"] / SERVER_PERF_LOG_INTERVAL
            print(f"[app-server] {label} rate={rate:.1f}/s avg={avg_ms:.1f}ms payload={avg_kb:.1f}KB")
            metric["count"] = 0
            metric["total_ms"] = 0.0
            metric["bytes"] = 0
            metric["last_log_at"] = now


class AppHandler(BaseHTTPRequestHandler):
    server_version = "CubeFlowHTTP/0.1"

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/state":
            started_at = time.monotonic()
            payload = build_frontend_state()
            return self._send_json(payload, log_label="app_state", started_at=started_at)
        if path == "/api/scanner/state":
            started_at = time.monotonic()
            payload = build_scanner_state()
            return self._send_json(payload, log_label="scanner_state", started_at=started_at)
        if path == "/api/scanner/preview.mjpeg":
            return self._stream_preview_mjpeg()
        if path == "/api/scanner/preview.jpg":
            return self._send_scanner_preview_jpeg()
        if path == "/api/settings":
            return self._send_json(load_settings())
        if path == "/api/assets/scan-preview.jpg":
            return self._send_file(SCAN_PREVIEW_PATH, "image/jpeg")
        if path == "/api/calibration":
            return self._send_json({"ok": True, "calibration": _build_calibration_payload(load_app_state())})
        if path == "/api/evaluation":
            state = load_app_state()
            return self._send_json({"ok": True, "evaluation": _build_evaluation_payload(state)})
        if path == "/api/evaluation/export.json":
            state = load_app_state()
            return self._send_json_download(
                _build_evaluation_export_payload(state),
                filename=f"cubeflow-evaluation-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json",
            )
        if path == "/api/evaluation/export.csv":
            state = load_app_state()
            return self._send_text_download(
                _build_evaluation_csv_text(state),
                content_type="text/csv; charset=utf-8",
                filename=f"cubeflow-evaluation-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv",
            )
        if path == "/api/evaluation/system-info.json":
            state = load_app_state()
            return self._send_json_download(
                _build_system_info_payload(state),
                filename=f"cubeflow-system-info-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json",
            )
        if path == "/api/shortcuts":
            return self._send_json({"items": SHORTCUTS})
        if path == "/health":
            return self._send_json({"ok": True, "service": "CubeFlow app server"})

        return self._serve_static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_json_body()

        if path == "/api/settings":
            merged = save_settings(body)
            update_app_state({"app": {"mode": "advanced" if merged.get("debugMode") else "normal"}})
            return self._send_json({"ok": True, "settings": merged})

        if path == "/api/state/reset":
            reset_app_state()
            return self._send_json({"ok": True, "state": build_frontend_state()})

        if path == "/api/evaluation/trial":
            trial_id = body.get("trialId")
            lighting_condition = body.get("lightingCondition")
            start_new = bool(body.get("startNew"))
            update_evaluation_metadata(
                trial_id=None if trial_id is None else str(trial_id),
                lighting_condition=None if lighting_condition is None else str(lighting_condition),
                start_new=start_new,
            )
            return self._send_json({"ok": True, "state": build_frontend_state()})

        if path == "/api/evaluation/client-info":
            record_evaluation_client_info(
                user_agent=body.get("userAgent"),
                app_version=body.get("appVersion"),
                platform=body.get("platform"),
            )
            return self._send_json({"ok": True})

        if path == "/api/evaluation/preview-metrics":
            record_evaluation_preview_metrics(
                fps_approx=body.get("fpsApprox"),
                target_fps=body.get("targetFps"),
                source=str(body.get("source", "browser")),
            )
            return self._send_json({"ok": True})

        if path == "/api/actions/launch-scanner":
            current_state = load_app_state()
            scanner_health = _compute_scanner_health(current_state)
            if scanner_health.get("processRunning"):
                return self._send_json({"ok": True, "alreadyRunning": True})
            subprocess.Popen([sys.executable, str(SCANNER_SCRIPT)], cwd=str(REPO_ROOT))
            update_app_state({"scanner": {"running": True}})
            return self._send_json({"ok": True})

        if path == "/api/actions/open-viewer":
            return self._send_json(open_current_viewer())

        if path == "/api/actions/command":
            action = body.get("action")
            payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
            if not isinstance(action, str) or not action:
                return self._send_json({"ok": False, "error": "Command action is required."}, status=HTTPStatus.BAD_REQUEST)
            command = enqueue_command(action, payload)
            return self._send_json({"ok": True, "command": command})

        if path == "/api/calibration/capture":
            color_name = str(body.get("color", "")).upper()
            state = load_app_state()
            scanner_health = _compute_scanner_health(state)
            current_bgr = state.get("scanner", {}).get("currentCenterBgr")
            if color_name not in CALIBRATION_COLORS:
                return self._send_json({"ok": False, "error": "Calibration color is required."}, status=HTTPStatus.BAD_REQUEST)
            if not scanner_health.get("processRunning"):
                return self._send_json(
                    {"ok": False, "error": "Launch the scanner before capturing calibration from the website."},
                    status=HTTPStatus.BAD_REQUEST,
                )
            if not (
                isinstance(current_bgr, list)
                and len(current_bgr) == 3
                and all(isinstance(component, (int, float)) for component in current_bgr)
            ):
                return self._send_json(
                    {"ok": False, "error": "No current center sample is available. Point a center sticker at the scanner first."},
                    status=HTTPStatus.BAD_REQUEST,
            )
            set_calibration_color(color_name, [int(component) for component in current_bgr])
            enqueue_command("capture-calibration", {"color": color_name})
            return self._send_json({"ok": True, "state": build_scanner_state()})

        if path == "/api/calibration/clear":
            color_name = str(body.get("color", "")).upper()
            if color_name not in CALIBRATION_COLORS:
                return self._send_json({"ok": False, "error": "Calibration color is required."}, status=HTTPStatus.BAD_REQUEST)
            clear_calibration_color(color_name)
            if _compute_scanner_health(load_app_state()).get("processRunning"):
                enqueue_command("clear-calibration", {"color": color_name})
            return self._send_json({"ok": True, "state": build_scanner_state()})

        if path == "/api/calibration/clear_all":
            clear_all_calibration_data()
            if _compute_scanner_health(load_app_state()).get("processRunning"):
                enqueue_command("clear-all-calibration", {})
            return self._send_json({"ok": True, "state": build_scanner_state()})

        if path == "/api/cube/edit":
            try:
                slot = str(body.get("slot", "")).upper()
                row = int(body.get("row"))
                col = int(body.get("col"))
                color = str(body.get("color", "")).upper()
                apply_manual_edit(slot, row, col, color)
            except Exception as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return self._send_json({"ok": True, "state": build_frontend_state()})

        if path == "/api/cube/undo":
            undo_manual_edit()
            return self._send_json({"ok": True, "state": build_frontend_state()})

        if path == "/api/cube/reset-edits":
            clear_all_manual_edits()
            return self._send_json({"ok": True, "state": build_frontend_state()})

        if path == "/api/solve/standard":
            return self._send_json({"ok": True, "result": solve_standard()})

        if path == "/api/solve/cfop":
            return self._send_json({"ok": True, "result": solve_cfop()})

        if path == "/api/viewer/session":
            mode = str(body.get("mode", "current"))
            try:
                session = build_web_viewer_session(mode, cube_state_from_store())
            except ViewerSessionError as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return self._send_json({"ok": True, "session": session})

        if path == "/api/playback/standard":
            return self._send_json(open_standard_playback())

        if path == "/api/playback/cfop":
            return self._send_json(open_cfop_playback())

        return self._send_json({"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args):
        return

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            payload = json.loads(raw.decode("utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _serve_static(self, path: str):
        if DIST_DIR.exists():
            if path == "/":
                target = DIST_DIR / "index.html"
            else:
                target = DIST_DIR / path.lstrip("/")
                if not target.exists() or target.is_dir():
                    target = DIST_DIR / "index.html"
            if target.exists() and target.is_file():
                content_type = _content_type_for(target)
                return self._send_file(target, content_type)

        if WEBAPP_DIR.exists():
            if path == "/":
                target = WEBAPP_DIR / "index.html"
            else:
                target = WEBAPP_DIR / path.lstrip("/")
                if not target.exists() or target.is_dir():
                    target = WEBAPP_DIR / "index.html"
            if target.exists() and target.is_file():
                content_type = _content_type_for(target)
                return self._send_file(target, content_type)

        return self._send_json(
            {
                "ok": False,
                "error": "Frontend files not found. Start the app shell from webapp/ or build it first.",
            },
            status=HTTPStatus.NOT_FOUND,
        )

    def _send_json(
        self,
        payload: dict,
        status: HTTPStatus = HTTPStatus.OK,
        log_label: str | None = None,
        started_at: float | None = None,
    ):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
        if log_label is not None and started_at is not None:
            _log_server_metric(log_label, (time.monotonic() - started_at) * 1000.0, len(raw))

    def _send_json_download(self, payload: dict, filename: str):
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_text_download(self, payload: str, *, content_type: str, filename: str):
        raw = payload.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self._send_cors_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_file(self, path: Path, content_type: str):
        if not path.exists() or not path.is_file():
            return self._send_json({"ok": False, "error": "File not found"}, status=HTTPStatus.NOT_FOUND)
        raw = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._send_cors_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_scanner_preview_jpeg(self):
        frame_bytes, _mtime_ns = _get_latest_preview_bytes()
        if not frame_bytes:
            return self._send_json({"ok": False, "error": "Preview not available"}, status=HTTPStatus.NOT_FOUND)
        self.send_response(HTTPStatus.OK)
        self._send_cors_headers()
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(frame_bytes)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(frame_bytes)

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _stream_preview_mjpeg(self):
        boundary = "frame"
        self.send_response(HTTPStatus.OK)
        self._send_cors_headers()
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={boundary}")
        self.end_headers()

        last_mtime_ns = None
        frames_sent = 0
        bytes_sent = 0
        last_log_at = time.monotonic()

        try:
            while True:
                frame_bytes, mtime_ns = _get_latest_preview_bytes()
                if not frame_bytes:
                    time.sleep(0.1)
                    continue

                if last_mtime_ns == mtime_ns:
                    time.sleep(1.0 / max(SCANNER_PREVIEW_TARGET_FPS, 1))
                    continue

                self.wfile.write(f"--{boundary}\r\n".encode("utf-8"))
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(frame_bytes)}\r\n\r\n".encode("utf-8"))
                self.wfile.write(frame_bytes)
                self.wfile.write(b"\r\n")
                self.wfile.flush()

                last_mtime_ns = mtime_ns
                frames_sent += 1
                bytes_sent += len(frame_bytes)

                now = time.monotonic()
                if now - last_log_at >= SERVER_PERF_LOG_INTERVAL:
                    fps = frames_sent / SERVER_PERF_LOG_INTERVAL
                    avg_kb = (bytes_sent / frames_sent / 1024.0) if frames_sent else 0.0
                    print(f"[app-server] scanner_preview fps={fps:.1f} payload={avg_kb:.1f}KB")
                    frames_sent = 0
                    bytes_sent = 0
                    last_log_at = now
        except (BrokenPipeError, ConnectionResetError):
            return None
        except Exception as exc:
            print(f"[app-server] preview stream error: {exc}")
            return None


def _content_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".html": "text/html; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(suffix, "application/octet-stream")


def _build_last_validation_label(summary: dict) -> str:
    if not summary["capturedFaceCount"]:
        return "No scan yet"
    if not summary["complete"]:
        return f"{summary['capturedFaceCount']} of 6 faces captured"
    if summary["deepValidation"]["ok"]:
        return "Cube validated and solver-ready"
    if summary["basicValidation"]["ok"]:
        return "Face colors captured, deeper validation needed"
    return "Cube needs review"


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"CubeFlow app server running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
