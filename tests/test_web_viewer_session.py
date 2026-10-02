from __future__ import annotations

from cube_backend.cube_state import CubeState
from cube_backend.solver_bridge import SolveResult
from cube_backend.web_viewer_session import build_web_viewer_session
from cube_backend.viewer_orientation import map_internal_move_to_viewer


SOLVED_FACELETS = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"


def test_current_viewer_session_returns_single_snapshot_frame():
    cube_state = CubeState.from_facelet_string(SOLVED_FACELETS)

    session = build_web_viewer_session("current", cube_state)

    assert session["mode"] == "current"
    assert len(session["frames"]) == 1
    assert session["moves"] == []
    assert session["frames"][0]["U"][1][1] == "YELLOW"
    assert session["frames"][0]["D"][1][1] == "WHITE"
    assert session["frames"][0]["F"][1][1] == "GREEN"
    assert session["frames"][0]["R"][1][1] == "ORANGE"
    assert session["frames"][0]["L"][1][1] == "RED"


def test_standard_viewer_session_builds_playback_frames(monkeypatch):
    cube_state = CubeState.from_facelet_string(SOLVED_FACELETS)

    monkeypatch.setattr(
        "cube_backend.web_viewer_session.solve_cube_state",
        lambda cube: SolveResult(
            success=True,
            moves="R",
            move_list=["R"],
            error=None,
            facelets=cube.to_facelet_string(),
        ),
    )

    session = build_web_viewer_session("standard", cube_state)

    assert session["mode"] == "standard"
    assert session["moves"] == ["L"]
    assert len(session["frames"]) == 2
    assert session["stages"] == []


def test_viewer_move_mapping_targets_canonical_faces():
    assert map_internal_move_to_viewer("D") == "U"
    assert map_internal_move_to_viewer("U") == "D"
    assert map_internal_move_to_viewer("F") == "F"
    assert map_internal_move_to_viewer("R") == "L"
    assert map_internal_move_to_viewer("L") == "R"


def test_cfop_viewer_session_has_four_stages_and_solved_final_frame():
    cube = CubeState.from_facelet_string(SOLVED_FACELETS)
    scrambled = cube.to_cubie_cube()
    scrambled.apply_alg("F R U R' U' F'")
    cube = CubeState.from_facelet_string(scrambled.to_facelet_string())

    session = build_web_viewer_session("cfop", cube)

    assert [stage["label"] for stage in session["stages"]] == ["White Cross", "F2L", "OLL", "PLL"]
    assert [move for stage in session["stages"] for move in stage["moves"]] == session["moves"]
    assert session["segmentationSource"] == "solver_metadata"
    assert session["segmentationVerified"] is True
    assert session["frames"][-1]["U"][1][1] == "YELLOW"
    assert session["frames"][-1]["D"][1][1] == "WHITE"
    assert all(
        sticker == session["frames"][-1][face][1][1]
        for face in ("U", "R", "F", "D", "L", "B")
        for row in session["frames"][-1][face]
        for sticker in row
    )
