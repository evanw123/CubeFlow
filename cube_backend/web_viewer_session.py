from __future__ import annotations

from .cfop_solver import solve_cfop_from_cube_state
from .cube_state import CubeState
from .cubie_model import CubieCube
from .playback_session import build_playback_session
from .solver_bridge import solve_cube_state
from .viewer_snapshot import cube_state_to_view_snapshot, facelet_string_to_view_snapshot
from .viewer_orientation import (
    CANONICAL_VIEWER_ORIENTATION,
    CANONICAL_VIEWER_SETUP_TEXT,
    map_internal_moves_to_viewer,
)


class ViewerSessionError(ValueError):
    pass


SPEED_OPTIONS = [0.5, 1.0, 1.5, 2.0]


def build_web_viewer_session(mode: str, cube_state: CubeState) -> dict:
    if mode == "current":
        return {
            "mode": "current",
            "title": "Current Cube",
            "beta": False,
            "setupText": CANONICAL_VIEWER_SETUP_TEXT,
            "orientation": CANONICAL_VIEWER_ORIENTATION.copy(),
            "moves": [],
            "stages": [],
            "frames": [cube_state_to_view_snapshot(cube_state)],
            "speedOptions": SPEED_OPTIONS,
        }

    if not cube_state.is_complete():
        raise ViewerSessionError("Capture all 6 faces before opening playback.")

    facelets = cube_state.to_facelet_string()

    if mode == "standard":
        solve_result = solve_cube_state(cube_state)
        if not solve_result.success:
            raise ViewerSessionError(solve_result.error or "Standard solve failed.")
        internal_moves = solve_result.move_list[:]
        moves = map_internal_moves_to_viewer(internal_moves)
        stages = []
        title = "Standard Solve Playback"
        setup_text = CANONICAL_VIEWER_SETUP_TEXT
        beta = False
        segmentation_source = None
        segmentation_verified = False
        segmentation_warning = None
    elif mode == "cfop":
        cfop_result = solve_cfop_from_cube_state(cube_state)
        if not cfop_result.success:
            raise ViewerSessionError(cfop_result.error or "CFOP Beta could not solve this cube yet.")
        internal_moves = cfop_result.full_moves[:]
        moves = cfop_result.display_moves[:] or map_internal_moves_to_viewer(internal_moves)
        stages = [
            {
                "id": (stage.case_id or stage.name).lower(),
                "name": stage.name,
                "label": stage.name,
                "start_index": start,
                "end_index": end,
                "move_count": len(stage.moves),
                "moves": stage.display_moves[:],
                "verified": stage.success,
                "rotation_prompt": " ".join(stage.cube_rotation),
                "display_moves": " ".join(stage.display_moves) if stage.display_moves else stage.move_string,
                "description": stage.description,
            }
            for stage, start, end in _stage_ranges(cfop_result.stages)
        ]
        title = "CFOP Beta Playback"
        setup_text = cfop_result.setup_text
        beta = True
        segmentation_source = cfop_result.segmentation_source
        segmentation_verified = cfop_result.segmentation_verified
        segmentation_warning = cfop_result.segmentation_warning
    else:
        raise ViewerSessionError(f"Unknown viewer mode: {mode}")

    session = build_playback_session(facelets=facelets, moves=moves, title=title, stages=stages or None)
    frames = build_playback_frames(facelets, internal_moves)

    return {
        "mode": mode,
        "title": title,
        "beta": beta,
        "setupText": setup_text,
        "orientation": CANONICAL_VIEWER_ORIENTATION.copy(),
        "moves": session["moves"],
        "stages": stages,
        "frames": frames,
        "speedOptions": SPEED_OPTIONS,
        "segmentationSource": segmentation_source,
        "segmentationVerified": segmentation_verified,
        "segmentationWarning": segmentation_warning,
    }


def build_playback_frames(facelets: str, moves: list[str]) -> list[dict]:
    cube = CubieCube.from_facelet_string(facelets)
    frames = [facelet_string_to_view_snapshot(facelets)]
    for move in moves:
        cube.apply_move(move)
        frames.append(facelet_string_to_view_snapshot(cube.to_facelet_string()))
    return frames


def _stage_ranges(stages) -> list[tuple[object, int, int]]:
    cursor = 0
    pairs = []
    for stage in stages:
        start = cursor
        cursor += len(stage.moves)
        pairs.append((stage, start, cursor))
    return pairs
