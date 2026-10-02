from __future__ import annotations

from cube_backend.app_state import (
    apply_manual_edit,
    cube_state_from_store,
    reset_app_state,
    scanned_cube_state_from_store,
    undo_manual_edit,
    update_app_state,
)
from cube_backend.cube_state import CubeState


SOLVED_FACELETS = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"


def test_manual_edits_overlay_scanned_state_without_replacing_it():
    reset_app_state()
    solved = CubeState.from_facelet_string(SOLVED_FACELETS)
    update_app_state({"scanner": {"faces": solved.to_faces_dict()}})

    apply_manual_edit("F", 0, 0, "BLUE")

    effective = cube_state_from_store()
    scanned = scanned_cube_state_from_store()

    assert effective.faces["F"][0][0] == "BLUE"
    assert scanned.faces["F"][0][0] == "GREEN"


def test_undo_manual_edit_restores_original_scanned_color():
    reset_app_state()
    solved = CubeState.from_facelet_string(SOLVED_FACELETS)
    update_app_state({"scanner": {"faces": solved.to_faces_dict()}})

    apply_manual_edit("R", 0, 0, "GREEN")
    undo_manual_edit()

    effective = cube_state_from_store()
    assert effective.faces["R"][0][0] == "RED"
