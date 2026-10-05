from __future__ import annotations

import cv2
import numpy as np
import os
import subprocess
import sys
import tempfile
import time

from cube_backend.app_state import (
    clear_all_calibration_data,
    clear_calibration_color,
    clear_all_manual_edits,
    clear_manual_edits_for_slot,
    load_calibration_store,
    now_iso,
    pop_pending_commands,
    record_evaluation_error,
    record_evaluation_scan_capture,
    record_evaluation_solver_result,
    record_evaluation_validation,
    reset_evaluation_trial_data,
    save_scan_preview_bytes,
    set_calibration_color,
    summarize_cube_state,
    update_app_state,
)
from cube_backend.cubie_model import CubieCube
from cube_backend.cfop_analyzer import analyze_cfop
from cube_backend.cfop_solver import (
    build_cfop_playback_session,
    build_cfop_playback_stages,
    format_cfop_solution,
    solve_cfop_from_cube_state,
    solve_white_cross,
)
from cube_backend.color_recognition import (
    DISPLAY_MAP,
    all_face_stable,
    classify_from_calibration,
    extract_stable_face_grid,
    median_bgr_from_patch,
    reset_sticker_history,
    get_stable_label,
)
from cube_backend.cube_state import CubeState
from cube_backend.f2l_cases import classify_all_f2l_cases
from cube_backend.move_utils import parse_alg
from cube_backend.playback_session import build_playback_session, save_playback_session
from cube_backend.solver_bridge import solve_cube_state
from cube_backend.validator import validate_cube_state
from cube_backend.viewer_snapshot import cube_state_to_view_snapshot, save_view_snapshot

print("Starting Rubik scanner with backend cube state...")

# =========================================================
# Utility functions
# =========================================================

SLOT_TO_CENTER_COLOR = {
    "F": "GREEN",
    "R": "RED",
    "B": "BLUE",
    "L": "ORANGE",
    "U": "WHITE",
    "D": "YELLOW",
}

COLOR_TO_FACELET = {
    "WHITE": "U",
    "RED": "R",
    "GREEN": "F",
    "YELLOW": "D",
    "ORANGE": "L",
    "BLUE": "B",
}

FACELET_ORDER = ["U", "R", "F", "D", "L", "B"]

WEB_PREVIEW_MAX_FPS = 12
WEB_PREVIEW_WIDTH = 520
WEB_PREVIEW_JPEG_QUALITY = 58
WEB_STATE_MAX_FPS = 2
WEB_PERF_LOG_INTERVAL = 5.0


def get_sticker_patch(sample_frame, center_x, center_y, sample_size):
    height, width, _ = sample_frame.shape

    sx1 = center_x - sample_size // 2
    sy1 = center_y - sample_size // 2
    sx2 = center_x + sample_size // 2
    sy2 = center_y + sample_size // 2

    sx1 = max(0, sx1)
    sy1 = max(0, sy1)
    sx2 = min(width, sx2)
    sy2 = min(height, sy2)

    patch = sample_frame[sy1:sy2, sx1:sx2]
    return patch, (sx1, sy1, sx2, sy2)


def get_center_patch_multi(sample_frame, center_x, center_y):
    height, width, _ = sample_frame.shape

    center_sample_size = 8
    offsets = [
        (-34, 0), (34, 0),
        (0, -34), (0, 34),
        (-24, -24), (24, -24),
        (-24, 24), (24, 24)
    ]

    patches = []
    rects = []

    for dx, dy in offsets:
        ox = center_x + dx
        oy = center_y + dy

        sx1 = ox - center_sample_size // 2
        sy1 = oy - center_sample_size // 2
        sx2 = ox + center_sample_size // 2
        sy2 = oy + center_sample_size // 2

        sx1 = max(0, sx1)
        sy1 = max(0, sy1)
        sx2 = min(width, sx2)
        sy2 = min(height, sy2)

        patch = sample_frame[sy1:sy2, sx1:sx2]
        if patch.size > 0:
            patches.append(patch)
            rects.append((sx1, sy1, sx2, sy2))

    if not patches:
        return np.array([0, 0, 0], dtype=np.uint8), []

    all_pixels = np.vstack([p.reshape(-1, 3) for p in patches])
    med = np.median(all_pixels, axis=0).astype(np.uint8)
    return med, rects


def resize_for_web_preview(frame, max_width):
    height, width = frame.shape[:2]
    if width <= max_width:
        return frame
    scale = max_width / float(width)
    target_size = (max_width, max(1, int(height * scale)))
    return cv2.resize(frame, target_size, interpolation=cv2.INTER_AREA)


def launch_3d_viewer(snapshot: dict) -> None:
    viewer_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cube_viewer_3d.py")

    try:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
            snapshot_path = temp_file.name

        save_view_snapshot(snapshot, snapshot_path)
        subprocess.Popen([sys.executable, viewer_script, "--snapshot", snapshot_path])
        print(f"Opened 3D viewer with snapshot: {snapshot_path}")
    except Exception as exc:
        print(f"Could not launch 3D viewer: {exc}")


def launch_playback_viewer(session: dict) -> None:
    viewer_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cube_viewer_3d.py")

    try:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
            session_path = temp_file.name

        save_playback_session(session, session_path)
        subprocess.Popen([sys.executable, viewer_script, "--session", session_path])
        print(f"Opened animated 3D playback: {session_path}")
    except Exception as exc:
        print(f"Could not launch animated 3D viewer: {exc}")


def get_cfop_analysis_with_cases(cube_state):
    cube = cube_state.to_cubie_cube()
    analysis = analyze_cfop(cube)
    cases = classify_all_f2l_cases(analysis.f2l_pairs)
    return analysis, cases


def print_cfop_report(analysis, cases):
    case_by_slot = {case.slot: case for case in cases}

    print("\n=== CFOP ANALYSIS ===")
    print(f"White Cross solved: {analysis.cross.solved}")
    print(f"White Cross edges solved: {analysis.cross.solved_count}/4")
    print(f"Solved White Cross edges: {analysis.cross.solved_edges}")
    print(f"Unsolved White Cross edges: {analysis.cross.unsolved_edges}")
    print("")
    print(f"F2L solved slots: {analysis.f2l_slots_solved}/4")

    for pair_state in analysis.f2l_pairs:
        pair_case = case_by_slot[pair_state.slot]
        print("")
        print(f"Slot {pair_state.slot}:")
        print(f"  corner position: {pair_state.corner_position}")
        print(f"  edge position: {pair_state.edge_position}")
        print(f"  paired: {pair_state.paired}")
        print(f"  inserted: {pair_state.inserted}")
        print(f"  solved: {pair_state.solved}")
        print(f"  case: {pair_case.code}")
        print(f"  description: {pair_case.description}")

    print("")
    print(f"OLL solved (Yellow): {analysis.oll_solved}")
    print(f"PLL solved (Yellow): {analysis.pll_solved}")
    print(f"Cube solved: {analysis.fully_solved}")


def print_cfop_solve_summary(result):
    print(format_cfop_solution(result))
    if not result.success:
        print("")
        print("CFOP failure:")
        print(f"  Failed stage: {result.failing_stage}")
        print(f"  Failed slot: {result.failing_slot}")
        print(f"  Failed case: {result.failing_case_id}")
        print(f"  Error: {result.error}")
        return

    oll_stage = next((stage for stage in result.stages if stage.name == "Yellow OLL"), None)
    pll_stage = next((stage for stage in result.stages if stage.name == "Yellow PLL"), None)

    print("")
    print("CFOP summary:")
    print(f"  White Cross moves: {len(result.cross_moves)}")
    print(f"  F2L total moves: {sum(len(stage.moves) for stage in result.f2l_slot_results)}")
    print(f"  OLL case: {'' if oll_stage is None or oll_stage.case_id is None else oll_stage.case_id}")
    print(f"  PLL case: {'' if pll_stage is None or pll_stage.case_id is None else pll_stage.case_id}")
    print(f"  Total moves: {len(result.full_moves)}")


def prepare_cfop_playback_session(cube_state):
    if not cube_state.is_complete():
        return None, "Cannot open CFOP playback: cube is incomplete. Capture all 6 faces first."

    cfop_result = solve_cfop_from_cube_state(cube_state)
    if not cfop_result.success:
        detail = cfop_result.error or "CFOP solve failed."
        if cfop_result.failing_stage:
            slot_text = "" if cfop_result.failing_slot is None else f" {cfop_result.failing_slot}"
            case_text = "" if cfop_result.failing_case_id is None else f" case {cfop_result.failing_case_id}"
            detail = (
                f"CFOP solve failed at {cfop_result.failing_stage}{slot_text}{case_text}: "
                f"{cfop_result.error or 'unsupported stage state'}"
            )
        return None, detail

    try:
        session = build_cfop_playback_session(
            facelets=cube_state.to_facelet_string(),
            result=cfop_result,
            title="CFOP Solution Playback",
        )
    except Exception as exc:
        return None, f"Could not prepare CFOP playback: {exc}"

    return session, None


def _capture_face_count() -> int:
    return sum(1 for slot in ["F", "R", "B", "L", "U", "D"] if cube_state.faces[slot] is not None)


def _calibration_snapshot() -> dict[str, list[int]]:
    snapshot: dict[str, list[int]] = {}
    for color_name, value in calibration.items():
        if hasattr(value, "tolist"):
            snapshot[color_name] = [int(component) for component in value.tolist()]
        else:
            snapshot[color_name] = [int(component) for component in value]
    return snapshot


def _build_standard_solve_payload(solve_result) -> dict:
    return {
        "kind": "standard",
        "status": "success" if solve_result.success else "error",
        "beta": False,
        "title": "Standard Solve",
        "error": solve_result.error,
        "moves": solve_result.move_list,
        "moveCount": len(solve_result.move_list),
        "moveString": solve_result.moves,
        "formatted": solve_result.moves if solve_result.success else None,
        "facelets": solve_result.facelets,
        "lastSolvedAt": now_iso(),
    }


def _build_cfop_solve_payload(cfop_result) -> dict:
    return {
        "kind": "cfop",
        "status": "success" if cfop_result.success else "error",
        "beta": True,
        "title": "CFOP Beta",
        "error": cfop_result.error,
        "failingStage": cfop_result.failing_stage,
        "failingSlot": cfop_result.failing_slot,
        "failingCaseId": cfop_result.failing_case_id,
        "setupText": cfop_result.setup_text,
        "moveCount": len(cfop_result.full_moves),
        "moveString": cfop_result.full_move_string,
        "moves": cfop_result.full_moves,
        "stages": [
            {
                "name": stage.name,
                "slot": stage.slot,
                "caseId": stage.case_id,
                "description": stage.description,
                "rotation": stage.cube_rotation,
                "displayMoves": stage.display_moves,
                "success": stage.success,
                "error": stage.error,
            }
            for stage in cfop_result.stages
        ],
        "lastSolvedAt": now_iso(),
    }


def _sync_app_shell_state(
    *,
    step: dict,
    target_slot: str,
    expected_center_color: str,
    center_label: str,
    face_is_stable: bool,
    center_matches_expected: bool,
    capture_status: str,
    stable_grid,
    current_center_bgr,
    preview_updated_at: str | None,
    preview_export_fps: float | None,
    camera_resolution: dict[str, int] | None,
) -> None:
    summary = summarize_cube_state(cube_state)
    deep_validation = summary["deepValidation"]
    captured_face_count = summary["capturedFaceCount"]

    if captured_face_count == 0:
        last_scan_status = "No scan yet"
    elif not summary["complete"]:
        last_scan_status = f"{captured_face_count} of 6 faces captured"
    elif deep_validation["ok"]:
        last_scan_status = "Cube validated and solver-ready"
    elif summary["basicValidation"]["ok"]:
        last_scan_status = "Cube captured, review needed"
    else:
        last_scan_status = "Cube needs review"

    update_app_state(
        {
            "scanner": {
                "running": True,
                "currentStepIndex": current_scan_index,
                "currentSlot": target_slot,
                "instruction": f"Show {step['front_color']} face",
                "orientationHint": f"Keep {step['up_color']} on top",
                "captureStatus": capture_status,
                "captureStatusTone": "success" if face_is_stable and center_matches_expected else "danger" if face_is_stable else "warning",
                "captureReady": bool(face_is_stable and center_matches_expected),
                "faceStable": face_is_stable,
                "centerMatches": center_matches_expected,
                "centerLabel": center_label,
                "expectedCenter": expected_center_color,
                "currentCenterBgr": None if current_center_bgr is None else [int(component) for component in current_center_bgr.tolist()],
                "previewUpdatedAt": preview_updated_at,
                "cameraResolution": camera_resolution,
                "previewExportFpsApprox": None if preview_export_fps is None else round(float(preview_export_fps), 2),
                "capturedFaces": summary["capturedFaces"],
                "faces": summary["faces"],
                "lastCapturedAt": last_capture_timestamp,
                "lastCapturedSlot": last_capture_slot,
                "lastCaptureMessage": None if last_capture_slot is None else f"{last_capture_slot} captured",
                "liveRecognitionGrid": [[stable_grid[r][c][0] for c in range(3)] for r in range(3)],
                "liveRecognitionStableGrid": [[bool(stable_grid[r][c][1]) for c in range(3)] for r in range(3)],
                "advanced": {
                    "counts": dict(cube_state.color_counts()),
                    "calibration": _calibration_snapshot(),
                    "validationErrors": summary["basicValidation"]["errors"],
                    "deepValidationErrors": deep_validation["errors"],
                    "deepValidationWarnings": deep_validation["warnings"],
                    "solverReady": deep_validation["ok"],
                    "cfopReady": last_cfop_probe_ready,
                },
            },
            "review": {
                **summary,
                "lastValidatedAt": last_validation_timestamp,
            },
            "recent": {
                "lastScanStatus": last_scan_status,
                "lastScanTimestamp": last_capture_timestamp,
            },
        }
    )


def _capture_calibration_color(color_name: str, center_bgr) -> None:
    if center_bgr is None:
        print("No center sample available for calibration.")
        return
    calibration[color_name] = center_bgr.copy()
    set_calibration_color(color_name, [int(component) for component in center_bgr.tolist()])
    print(f"Saved calibration for {color_name}: {center_bgr.tolist()}")


def _clear_calibration_color(color_name: str) -> None:
    calibration.pop(color_name, None)
    clear_calibration_color(color_name)
    print(f"Cleared calibration for {color_name}.")


def _clear_all_calibration() -> None:
    calibration.clear()
    clear_all_calibration_data()
    print("Calibration cleared.")


def _next_step() -> None:
    global current_scan_index, sticker_history
    current_scan_index = min(current_scan_index + 1, len(scan_steps) - 1)
    sticker_history = reset_sticker_history(maxlen=7)
    print(f"Moved to scan step: {scan_steps[current_scan_index]['slot']}")


def _previous_step() -> None:
    global current_scan_index, sticker_history
    current_scan_index = max(current_scan_index - 1, 0)
    sticker_history = reset_sticker_history(maxlen=7)
    print(f"Moved to scan step: {scan_steps[current_scan_index]['slot']}")


def _clear_current_face(target_slot: str) -> None:
    global sticker_history, last_cfop_probe_facelets, last_cfop_probe_ready
    cube_state.clear_face(target_slot)
    clear_manual_edits_for_slot(target_slot)
    update_app_state({"solves": {"standard": None, "cfop": None}})
    sticker_history = reset_sticker_history(maxlen=7)
    last_cfop_probe_facelets = None
    last_cfop_probe_ready = False
    print(f"Cleared face slot {target_slot}")


def _reset_cube() -> None:
    global sticker_history, last_cfop_probe_facelets, last_cfop_probe_ready, last_capture_timestamp, last_validation_timestamp, last_capture_slot
    cube_state.clear_all()
    clear_all_manual_edits()
    reset_evaluation_trial_data(preserve_metadata=True)
    sticker_history = reset_sticker_history(maxlen=7)
    last_cfop_probe_facelets = None
    last_cfop_probe_ready = False
    last_capture_timestamp = None
    last_validation_timestamp = None
    last_capture_slot = None
    update_app_state({"solves": {"standard": None, "cfop": None}})
    print("Cleared all captured faces.")


def _run_validation() -> None:
    global last_validation_timestamp
    ok, errors = cube_state.validate()
    deep_result = cube_state.validate_deep()
    last_validation_timestamp = now_iso()

    print("\n=== BASIC VALIDATION ===")
    print("VALID" if ok else "INVALID")
    if errors:
        for err in errors:
            print("-", err)
    elif cube_state.is_complete():
        print("Facelet string:")
        print(cube_state.to_facelet_string())

    print("\n=== DEEP VALIDATION ===")
    print("VALID" if deep_result.is_valid else "INVALID")
    if deep_result.errors:
        for err in deep_result.errors:
            print("-", err)
    if deep_result.warnings:
        for warning in deep_result.warnings:
            print("!", warning)
    if deep_result.facelets:
        print("Facelet string:")
        print(deep_result.facelets)
    record_evaluation_validation(summarize_cube_state(cube_state), phase="final")


def _run_standard_solve() -> None:
    if not cube_state.is_complete():
        print("Cannot solve: cube is incomplete. Capture all 6 faces first.")
        record_evaluation_solver_result(
            kind="standard",
            success=False,
            move_count=0,
            error="Capture all 6 faces before solving.",
        )
        record_evaluation_error("standard-solve", "Capture all 6 faces before solving.")
        update_app_state(
            {
                "solves": {
                    "standard": {
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
                }
            }
        )
        return

    solve_result = cube_state.solve()
    print("\n=== SOLVER ===")
    print("SUCCESS" if solve_result.success else "FAILURE")
    print("Facelet string:")
    print(solve_result.facelets)
    if solve_result.success:
        print("Solution:")
        print(solve_result.moves if solve_result.moves else "(cube already solved)")
    else:
        print("Error:")
        print(solve_result.error)

    record_evaluation_solver_result(
        kind="standard",
        success=solve_result.success,
        move_count=len(solve_result.move_list),
        error=solve_result.error,
    )
    if not solve_result.success and solve_result.error:
        record_evaluation_error("standard-solve", solve_result.error)
    update_app_state({"solves": {"standard": _build_standard_solve_payload(solve_result)}})


def _run_cfop_solve() -> None:
    if not cube_state.is_complete():
        print("Cannot CFOP solve: cube is incomplete. Capture all 6 faces first.")
        update_app_state(
            {
                "solves": {
                    "cfop": {
                        "kind": "cfop",
                        "status": "incomplete",
                        "beta": True,
                        "title": "CFOP Beta",
                        "error": "Capture all 6 faces before solving.",
                        "moves": [],
                        "moveCount": 0,
                        "moveString": "",
                        "lastSolvedAt": now_iso(),
                    }
                }
            }
        )
        return

    try:
        cfop_result = solve_cfop_from_cube_state(cube_state)
        print_cfop_solve_summary(cfop_result)
        update_app_state({"solves": {"cfop": _build_cfop_solve_payload(cfop_result)}})
    except Exception as exc:
        print(f"Could not run CFOP solver: {exc}")
        update_app_state(
            {
                "solves": {
                    "cfop": {
                        "kind": "cfop",
                        "status": "error",
                        "beta": True,
                        "title": "CFOP Beta",
                        "error": str(exc),
                        "moves": [],
                        "moveCount": 0,
                        "moveString": "",
                        "lastSolvedAt": now_iso(),
                    }
                }
            }
        )


def _run_cfop_analysis() -> None:
    if not cube_state.is_complete():
        print("Cannot analyze CFOP: cube is incomplete. Capture all 6 faces first.")
        return

    try:
        analysis, cases = get_cfop_analysis_with_cases(cube_state)
        print_cfop_report(analysis, cases)
    except Exception as exc:
        print(f"Could not analyze CFOP state: {exc}")


def _toggle_cfop_overlay() -> None:
    global cfop_overlay_enabled
    cfop_overlay_enabled = not cfop_overlay_enabled
    print(f"CFOP overlay {'enabled' if cfop_overlay_enabled else 'disabled'}.")


def _open_current_viewer() -> None:
    snapshot = cube_state_to_view_snapshot(cube_state)
    launch_3d_viewer(snapshot)
    update_app_state({"viewer": {"lastOpenedMode": "current", "lastOpenedAt": now_iso(), "lastSessionTitle": "Current Cube"}})


def _open_standard_playback() -> None:
    if not cube_state.is_complete():
        print("Cannot open playback: cube is incomplete. Capture all 6 faces first.")
        return

    deep_result = cube_state.validate_deep()
    if not deep_result.is_valid:
        print("Cannot open playback: deep validation failed.")
        for err in deep_result.errors:
            print("-", err)
        return

    solve_result = cube_state.solve()
    if not solve_result.success:
        print("Cannot open playback: solver failed.")
        if solve_result.error:
            print(solve_result.error)
        return

    try:
        moves = solve_result.move_list or parse_alg(solve_result.moves or "")
        session = build_playback_session(
            facelets=deep_result.facelets,
            moves=moves,
            title="Scanner Solution Playback",
        )
        launch_playback_viewer(session)
        update_app_state({"viewer": {"lastOpenedMode": "standard-playback", "lastOpenedAt": now_iso(), "lastSessionTitle": "Standard Solution Playback"}})
    except Exception as exc:
        print(f"Could not prepare playback session: {exc}")


def _open_cfop_playback() -> None:
    try:
        session, error_message = prepare_cfop_playback_session(cube_state)
        if session is None:
            print("Cannot open CFOP playback:")
            print(error_message or "CFOP solve failed.")
        else:
            launch_playback_viewer(session)
            update_app_state({"viewer": {"lastOpenedMode": "cfop-playback", "lastOpenedAt": now_iso(), "lastSessionTitle": "CFOP Beta Playback"}})
    except Exception as exc:
        print(f"Could not prepare CFOP playback: {exc}")


def _capture_current_face(
    *,
    face_is_stable: bool,
    center_matches_expected: bool,
    center_label: str,
    expected_center_color: str,
    stable_grid,
) -> None:
    global current_scan_index, sticker_history, last_capture_timestamp, last_validation_timestamp, last_capture_slot

    if not face_is_stable:
        print("Cannot capture: face is not fully stable yet.")
        return
    if not center_matches_expected:
        print(f"Cannot capture: center is {center_label}, expected {expected_center_color}.")
        return

    captured_slot = scan_steps[current_scan_index]["slot"]
    clear_manual_edits_for_slot(captured_slot)
    captured_face = extract_stable_face_grid(stable_grid)
    cube_state.set_face(captured_slot, captured_face)
    update_app_state({"solves": {"standard": None, "cfop": None}})
    last_capture_timestamp = now_iso()
    last_capture_slot = captured_slot

    print(f"\nCaptured face {captured_slot}:")
    for row in captured_face:
        print(row)

    if cube_state.is_complete():
        ok, errors = cube_state.validate()
        last_validation_timestamp = now_iso()
        print("\n=== BACKEND VALIDATION AFTER CAPTURE ===")
        print("VALID" if ok else "INVALID")
        if errors:
            for err in errors:
                print("-", err)
        else:
            print("Facelet string:")
            print(cube_state.to_facelet_string())

    if current_scan_index < len(scan_steps) - 1:
        current_scan_index += 1
        print(f"Next scan step: {scan_steps[current_scan_index]['slot']}")
    else:
        print("All guided scan steps completed.")

    summary = summarize_cube_state(cube_state)
    record_evaluation_scan_capture(
        slot=captured_slot,
        scanned_faces=cube_state.to_faces_dict(),
        effective_faces=cube_state.to_faces_dict(),
        summary=summary,
        calibration_enabled=bool(calibration),
    )
    if summary["complete"]:
        record_evaluation_validation(summary, phase="initial")

    sticker_history = reset_sticker_history(maxlen=7)


def _process_remote_commands(
    *,
    target_slot: str,
    face_is_stable: bool,
    center_matches_expected: bool,
    center_label: str,
    expected_center_color: str,
    stable_grid,
    current_center_bgr,
) -> bool:
    should_close = False
    for command in pop_pending_commands():
        action = command.get("action")
        payload = command.get("payload") if isinstance(command.get("payload"), dict) else {}
        if not isinstance(action, str):
            continue

        if action == "capture":
            _capture_current_face(
                face_is_stable=face_is_stable,
                center_matches_expected=center_matches_expected,
                center_label=center_label,
                expected_center_color=expected_center_color,
                stable_grid=stable_grid,
            )
        elif action == "next-step":
            _next_step()
        elif action == "previous-step":
            _previous_step()
        elif action == "clear-face":
            _clear_current_face(target_slot)
        elif action == "reset-cube":
            _reset_cube()
        elif action == "validate":
            _run_validation()
        elif action == "solve-standard":
            _run_standard_solve()
        elif action == "solve-cfop":
            _run_cfop_solve()
        elif action == "analyze-cfop":
            _run_cfop_analysis()
        elif action == "toggle-cfop-overlay":
            _toggle_cfop_overlay()
        elif action == "open-viewer":
            _open_current_viewer()
        elif action == "open-standard-playback":
            _open_standard_playback()
        elif action == "open-cfop-playback":
            _open_cfop_playback()
        elif action == "capture-calibration":
            color_name = str(payload.get("color", "")).upper()
            if color_name in key_to_color.values():
                _capture_calibration_color(color_name, current_center_bgr)
        elif action == "clear-calibration":
            color_name = str(payload.get("color", "")).upper()
            if color_name in key_to_color.values():
                _clear_calibration_color(color_name)
        elif action == "clear-all-calibration":
            _clear_all_calibration()
        elif action == "close-scanner":
            should_close = True

    return should_close


# =========================================================
# Backend cube state
# =========================================================
def draw_face_net(frame, cube_state, origin_x, origin_y, tile_size=18, gap=2, active_slot=None):
    """
    Draw a 2D cube net:
            U
         L  F  R  B
            D
    """
    layout = {
        "U": (1, 0),
        "L": (0, 1),
        "F": (1, 1),
        "R": (2, 1),
        "B": (3, 1),
        "D": (1, 2),
    }

    face_pixels = 3 * tile_size + 2 * gap
    panel_w = 4 * face_pixels + 60
    panel_h = 3 * face_pixels + 60

    cv2.rectangle(
        frame,
        (origin_x - 15, origin_y - 25),
        (origin_x - 15 + panel_w, origin_y - 25 + panel_h),
        (40, 40, 40),
        -1
    )

    cv2.putText(
        frame,
        "Cube Net",
        (origin_x, origin_y - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2
    )

    for slot, (grid_col, grid_row) in layout.items():
        face = cube_state.faces.get(slot)

        face_x = origin_x + grid_col * (face_pixels + 12)
        face_y = origin_y + grid_row * (face_pixels + 12)

        if active_slot == slot:
            cv2.rectangle(
                frame,
                (face_x - 4, face_y - 18),
                (face_x + face_pixels + 4, face_y + face_pixels + 4),
                (255, 255, 255),
                2
            )

        cv2.putText(
            frame,
            slot,
            (face_x + tile_size, face_y - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )

        for r in range(3):
            for c in range(3):
                x = face_x + c * (tile_size + gap)
                y = face_y + r * (tile_size + gap)

                if face is None:
                    color_name = "UNKNOWN"
                else:
                    color_name = face[r][c]

                fill = DISPLAY_MAP.get(color_name, DISPLAY_MAP["UNKNOWN"])

                cv2.rectangle(frame, (x, y), (x + tile_size, y + tile_size), fill, -1)
                cv2.rectangle(frame, (x, y), (x + tile_size, y + tile_size), (0, 0, 0), 1)

# =========================================================
# Guided scan state machine
# =========================================================

scan_steps = [
    {
        "slot": "F",
        "front_color": "GREEN",
        "up_color": "WHITE",
        "instruction": "Scan FRONT: hold GREEN front, WHITE on top",
    },
    {
        "slot": "R",
        "front_color": "RED",
        "up_color": "WHITE",
        "instruction": "Scan RIGHT: hold RED front, WHITE on top",
    },
    {
        "slot": "B",
        "front_color": "BLUE",
        "up_color": "WHITE",
        "instruction": "Scan BACK: hold BLUE front, WHITE on top",
    },
    {
        "slot": "L",
        "front_color": "ORANGE",
        "up_color": "WHITE",
        "instruction": "Scan LEFT: hold ORANGE front, WHITE on top",
    },
    {
        "slot": "U",
        "front_color": "WHITE",
        "up_color": "BLUE",
        "instruction": "Scan UP: hold WHITE front, BLUE on top",
    },
    {
        "slot": "D",
        "front_color": "YELLOW",
        "up_color": "GREEN",
        "instruction": "Scan DOWN: hold YELLOW front, GREEN on top",
    },
]

current_scan_index = 0
cube_state = CubeState()

# =========================================================
# Calibration storage
# =========================================================

calibration = {
    color_name: np.array(sample_bgr, dtype=np.uint8)
    for color_name, sample_bgr in load_calibration_store().items()
}

key_to_color = {
    ord('u'): "WHITE",
    ord('d'): "YELLOW",
    ord('f'): "GREEN",
    ord('b'): "BLUE",
    ord('r'): "RED",
    ord('l'): "ORANGE",
}

# =========================================================
# Camera setup
# =========================================================

cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)

if not cap.isOpened():
    print("Error: Could not open camera.")
    exit()

sticker_history = reset_sticker_history(maxlen=7)
last_validation_ok = False
last_validation_errors = []
cfop_overlay_enabled = False
last_cfop_probe_facelets = None
last_cfop_probe_ready = False
last_preview_updated_at = None
last_capture_timestamp = None
last_validation_timestamp = None
last_capture_slot = None
last_preview_export_at = 0.0
last_state_export_at = 0.0
last_perf_log_at = time.monotonic()
preview_export_count = 0
state_export_count = 0
preview_resize_total_ms = 0.0
preview_encode_total_ms = 0.0
preview_write_total_ms = 0.0
preview_last_size_bytes = 0
state_export_total_ms = 0.0
preview_fps_approx = None

update_app_state(
    {
        "scanner": {
            "running": True,
            "currentStepIndex": current_scan_index,
            "currentSlot": scan_steps[current_scan_index]["slot"],
            "instruction": f"Show {scan_steps[current_scan_index]['front_color']} face",
            "orientationHint": f"Keep {scan_steps[current_scan_index]['up_color']} on top",
        }
    }
)

while True:
    ret, frame = cap.read()
    if not ret:
        print("Error: Could not read frame.")
        break

    sample_frame = frame.copy()
    preview_frame = frame.copy()
    draw_frame = frame.copy()

    height, width, _ = frame.shape
    camera_resolution = {"width": int(width), "height": int(height)}

    box_size = 300
    x1 = width // 2 - box_size // 2
    y1 = height // 2 - box_size // 2
    x2 = x1 + box_size
    y2 = y1 + box_size
    cell_size = box_size // 3

    step = scan_steps[current_scan_index]
    target_slot = step["slot"]
    expected_center_color = step["front_color"]

    cv2.rectangle(draw_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    for i in range(1, 3):
        cv2.line(draw_frame, (x1 + i * cell_size, y1), (x1 + i * cell_size, y2), (0, 255, 0), 2)
        cv2.line(draw_frame, (x1, y1 + i * cell_size), (x2, y1 + i * cell_size), (0, 255, 0), 2)
    cv2.rectangle(preview_frame, (x1, y1), (x2, y2), (76, 216, 136), 2)
    for i in range(1, 3):
        cv2.line(preview_frame, (x1 + i * cell_size, y1), (x1 + i * cell_size, y2), (76, 216, 136), 2)
        cv2.line(preview_frame, (x1, y1 + i * cell_size), (x2, y1 + i * cell_size), (76, 216, 136), 2)

    cv2.putText(
        draw_frame,
        "Calibration: u=white d=yellow f=green b=blue r=red l=orange c=clear",
        (20, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (0, 255, 0),
        2
    )

    cv2.putText(
        draw_frame,
        "Guided scan: SPACE=capture n=next p=prev x=clear face z=clear cube v=validate o=general solve y=CFOP solve 3=3D viewer 4=play solution 3D 5=play CFOP 3D g=CFOP analyze h=toggle CFOP overlay",
        (20, 52),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (0, 255, 0),
        2
    )

    cv2.putText(
        draw_frame,
        step["instruction"],
        (20, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (0, 255, 255),
        2
    )

    cv2.putText(
        draw_frame,
        f"Expected center: {expected_center_color}   Slot: {target_slot}",
        (20, 106),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (255, 255, 255),
        2
    )

    current_center_bgr = None
    stable_grid = [[("UNKNOWN", False) for _ in range(3)] for _ in range(3)]

    for row in range(3):
        for col in range(3):
            cell_x1 = x1 + col * cell_size
            cell_y1 = y1 + row * cell_size
            cell_x2 = cell_x1 + cell_size
            cell_y2 = cell_y1 + cell_size

            center_x = (cell_x1 + cell_x2) // 2
            center_y = (cell_y1 + cell_y2) // 2

            if row == 1 and col == 1:
                measured_bgr, rects = get_center_patch_multi(sample_frame, center_x, center_y)

                for (sx1, sy1, sx2, sy2) in rects:
                    cv2.rectangle(draw_frame, (sx1, sy1), (sx2, sy2), (255, 255, 255), 1)

                current_center_bgr = measured_bgr
            else:
                patch, (sx1, sy1, sx2, sy2) = get_sticker_patch(sample_frame, center_x, center_y, 20)
                measured_bgr = median_bgr_from_patch(patch)
                cv2.rectangle(draw_frame, (sx1, sy1), (sx2, sy2), (255, 255, 255), 1)

            color_name, display_color, debug_text = classify_from_calibration(measured_bgr, calibration)

            if color_name != "UNKNOWN":
                sticker_history[row][col].append(color_name)

            stable_label, is_stable = get_stable_label(sticker_history[row][col], min_count=5)
            stable_grid[row][col] = (stable_label, is_stable)

            border_color = (0, 255, 0) if is_stable else (0, 0, 255)

            cv2.circle(draw_frame, (center_x, center_y), 25, display_color, -1)
            cv2.circle(draw_frame, (center_x, center_y), 25, border_color, 2)

            cv2.putText(
                draw_frame,
                stable_label,
                (cell_x1 + 5, cell_y2 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1
            )

            cv2.putText(
                draw_frame,
                debug_text,
                (cell_x1 + 5, cell_y1 + 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (255, 255, 255),
                1
            )

    face_is_stable = all_face_stable(stable_grid)
    center_label, center_is_stable = stable_grid[1][1]
    center_matches_expected = (center_label == expected_center_color)

    if face_is_stable and center_matches_expected:
        capture_status = "READY TO CAPTURE"
        capture_color = (0, 255, 0)
    elif face_is_stable and not center_matches_expected:
        capture_status = f"STABLE BUT CENTER IS {center_label}, EXPECTED {expected_center_color}"
        capture_color = (0, 0, 255)
    else:
        capture_status = "WAITING FOR STABLE FACE"
        capture_color = (0, 165, 255)

    cv2.putText(
        draw_frame,
        capture_status,
        (20, y2 + 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        capture_color,
        2
    )

    calib_y = 140
    cv2.putText(
        draw_frame,
        "Calibration:",
        (20, calib_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2
    )
    calib_y += 24

    for name in ["WHITE", "YELLOW", "GREEN", "BLUE", "RED", "ORANGE"]:
        status = "OK" if name in calibration else "--"
        cv2.putText(
            draw_frame,
            f"{name}: {status}",
            (20, calib_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )
        calib_y += 20

    status_x = width - 220
    status_y = 30

    cv2.putText(
        draw_frame,
        "Captured Faces:",
        (status_x, status_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2
    )
    status_y += 28

    for slot in ["F", "R", "B", "L", "U", "D"]:
        status = "OK" if cube_state.faces[slot] is not None else "--"
        color = (0, 255, 0) if cube_state.faces[slot] is not None else (180, 180, 180)
        label = f"> {slot}: {status}" if slot == target_slot else f"  {slot}: {status}"

        cv2.putText(
            draw_frame,
            label,
            (status_x, status_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2 if slot == target_slot else 1
        )
        status_y += 24

    counts = cube_state.color_counts()
    status_y += 8
    cv2.putText(
        draw_frame,
        "Counts:",
        (status_x, status_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2
    )
    status_y += 24

    for color_name in ["WHITE", "YELLOW", "GREEN", "BLUE", "RED", "ORANGE"]:
        count = counts.get(color_name, 0)
        cv2.putText(
            draw_frame,
            f"{color_name[:3]}: {count}",
            (status_x, status_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )
        status_y += 20

    if current_center_bgr is not None:
        b, g, r = [int(x) for x in current_center_bgr]
        cv2.putText(
            draw_frame,
            f"Center BGR: ({b},{g},{r})",
            (20, calib_y + 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )

    if cube_state.is_complete():
        ok, errors = cube_state.validate()
        deep_result = cube_state.validate_deep()
        last_validation_ok = ok
        last_validation_errors = errors

        if deep_result.facelets != last_cfop_probe_facelets:
            if deep_result.is_valid:
                try:
                    probe_stage = solve_white_cross(cube_state.to_cubie_cube())
                    last_cfop_probe_ready = probe_stage.success
                except Exception:
                    last_cfop_probe_ready = False
            else:
                last_cfop_probe_ready = False
            last_cfop_probe_facelets = deep_result.facelets

        validation_text = "VALID CUBE STATE" if ok else "INVALID CUBE STATE"
        validation_color = (0, 255, 0) if ok else (0, 0, 255)

        cv2.putText(
            draw_frame,
            validation_text,
            (20, height - 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            validation_color,
            2
        )

        deep_text = "SOLVER READY" if deep_result.is_valid else "DEEP INVALID"
        deep_color = (0, 255, 0) if deep_result.is_valid else (0, 0, 255)
        cv2.putText(
            draw_frame,
            deep_text,
            (20, height - 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            deep_color,
            2
        )

        solver_ready_text = (
            f"Kociemba ready: {'yes' if deep_result.is_valid else 'no'}   "
            f"CFOP ready: {'yes' if last_cfop_probe_ready else 'no'}"
        )
        cv2.putText(
            draw_frame,
            solver_ready_text,
            (20, height - 115),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (255, 255, 255),
            1
        )

        if ok:
            try:
                facelet_string = cube_state.to_facelet_string()
                cv2.putText(
                    draw_frame,
                    f"54-char export ready ({len(facelet_string)})",
                    (20, height - 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 255),
                    1
                )
            except Exception as e:
                cv2.putText(
                    draw_frame,
                    f"Export error: {str(e)}",
                    (20, height - 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    1
                )

        if cfop_overlay_enabled:
            try:
                analysis, _ = get_cfop_analysis_with_cases(cube_state)
                cv2.putText(
                    draw_frame,
                    f"White Cross: {analysis.cross.solved_count}/4   F2L: {analysis.f2l_slots_solved}/4",
                    (20, height - 150),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.52,
                    (255, 255, 255),
                    1
                )
                cv2.putText(
                    draw_frame,
                    f"OLL (Yellow): {'yes' if analysis.oll_solved else 'no'}   PLL (Yellow): {'yes' if analysis.pll_solved else 'no'}",
                    (20, height - 125),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.52,
                    (255, 255, 255),
                    1
                )
            except Exception:
                cv2.putText(
                    draw_frame,
                    "CFOP ERROR",
                    (20, height - 150),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.52,
                    (0, 0, 255),
                    1
                )
    draw_face_net(
        draw_frame,
        cube_state,
        origin_x=width - 320,
        origin_y=height - 240,
        tile_size=18,
        gap=2,
        active_slot=target_slot
    )
    
    loop_now = time.monotonic()

    if loop_now - last_preview_export_at >= 1.0 / WEB_PREVIEW_MAX_FPS:
        resize_started_at = time.monotonic()
        preview_export_frame = resize_for_web_preview(preview_frame, WEB_PREVIEW_WIDTH)
        preview_resize_total_ms += (time.monotonic() - resize_started_at) * 1000.0

        encode_started_at = time.monotonic()
        encoded, encoded_image = cv2.imencode(
            ".jpg",
            preview_export_frame,
            [cv2.IMWRITE_JPEG_QUALITY, WEB_PREVIEW_JPEG_QUALITY],
        )
        preview_encode_total_ms += (time.monotonic() - encode_started_at) * 1000.0

        if encoded:
            write_started_at = time.monotonic()
            preview_bytes = encoded_image.tobytes()
            save_scan_preview_bytes(preview_bytes)
            preview_write_total_ms += (time.monotonic() - write_started_at) * 1000.0
            preview_last_size_bytes = len(preview_bytes)
            last_preview_updated_at = now_iso()
            last_preview_export_at = loop_now
            preview_export_count += 1

    if loop_now - last_state_export_at >= 1.0 / WEB_STATE_MAX_FPS:
        state_started_at = time.monotonic()
        _sync_app_shell_state(
            step=step,
            target_slot=target_slot,
            expected_center_color=expected_center_color,
            center_label=center_label,
            face_is_stable=face_is_stable,
            center_matches_expected=center_matches_expected,
            capture_status=capture_status,
            stable_grid=stable_grid,
            current_center_bgr=current_center_bgr,
            preview_updated_at=last_preview_updated_at,
            preview_export_fps=preview_fps_approx,
            camera_resolution=camera_resolution,
        )
        state_export_total_ms += (time.monotonic() - state_started_at) * 1000.0
        last_state_export_at = loop_now
        state_export_count += 1

    if loop_now - last_perf_log_at >= WEB_PERF_LOG_INTERVAL:
        preview_hz = preview_export_count / max(WEB_PERF_LOG_INTERVAL, 0.001)
        preview_fps_approx = preview_hz
        state_hz = state_export_count / max(WEB_PERF_LOG_INTERVAL, 0.001)
        avg_resize_ms = preview_resize_total_ms / preview_export_count if preview_export_count else 0.0
        avg_encode_ms = preview_encode_total_ms / preview_export_count if preview_export_count else 0.0
        avg_write_ms = preview_write_total_ms / preview_export_count if preview_export_count else 0.0
        avg_state_ms = state_export_total_ms / state_export_count if state_export_count else 0.0
        print(
            "[web-preview] "
            f"fps={preview_hz:.1f} size={preview_last_size_bytes/1024:.1f}KB "
            f"resize={avg_resize_ms:.1f}ms encode={avg_encode_ms:.1f}ms write={avg_write_ms:.1f}ms "
            f"state_hz={state_hz:.1f} state_write={avg_state_ms:.1f}ms"
        )
        last_perf_log_at = loop_now
        preview_export_count = 0
        state_export_count = 0
        preview_resize_total_ms = 0.0
        preview_encode_total_ms = 0.0
        preview_write_total_ms = 0.0
        state_export_total_ms = 0.0

    if _process_remote_commands(
        target_slot=target_slot,
        face_is_stable=face_is_stable,
        center_matches_expected=center_matches_expected,
        center_label=center_label,
        expected_center_color=expected_center_color,
        stable_grid=stable_grid,
        current_center_bgr=current_center_bgr,
    ):
        print("Close requested from app shell.")
        break

    cv2.imshow("Rubik Scanner", draw_frame)

    key = cv2.waitKey(1) & 0xFF

    if key == 27:
        print("ESC pressed. Closing.")
        break

    if key == ord('c'):
        _clear_all_calibration()

    if key in key_to_color and current_center_bgr is not None:
        color_name = key_to_color[key]
        _capture_calibration_color(color_name, current_center_bgr)

    if key == ord('n'):
        _next_step()

    if key == ord('p'):
        _previous_step()

    if key == ord('x'):
        _clear_current_face(target_slot)

    if key == ord('z'):
        _reset_cube()

    if key == ord('v'):
        _run_validation()

    if key == ord('o'):
        _run_standard_solve()

    if key == ord('y'):
        _run_cfop_solve()

    if key == ord('g'):
        _run_cfop_analysis()

    if key == ord('h'):
        _toggle_cfop_overlay()

    if key == ord('3'):
        _open_current_viewer()

    if key == ord('4'):
        _open_standard_playback()

    if key == ord('5'):
        _open_cfop_playback()

    if key == 32:  # SPACE
        _capture_current_face(
            face_is_stable=face_is_stable,
            center_matches_expected=center_matches_expected,
            center_label=center_label,
            expected_center_color=expected_center_color,
            stable_grid=stable_grid,
        )

cap.release()
cv2.destroyAllWindows()
update_app_state({"scanner": {"running": False}})
print("Program ended.")
