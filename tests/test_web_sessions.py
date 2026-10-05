from __future__ import annotations

import uuid

from app_server import build_frontend_state, solve_standard
from cube_backend.app_state import load_app_state, reset_app_state, set_calibration_color, update_app_state
from cube_backend.cube_state import CubeState
from cube_backend.web_sessions import WEB_SESSION_STORE


SOLVED_FACELETS = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"


def new_session_id() -> str:
    return str(uuid.uuid4())


def test_browser_sessions_isolate_calibration_cube_and_solve_state():
    first = new_session_id()
    second = new_session_id()
    solved = CubeState.from_facelet_string(SOLVED_FACELETS)

    with WEB_SESSION_STORE.activate(first):
        reset_app_state()
        set_calibration_color("GREEN", [0, 180, 0])
        update_app_state({"scanner": {"faces": solved.to_faces_dict()}})
        result = solve_standard()
        assert result["status"] == "success"

    with WEB_SESSION_STORE.activate(second):
        reset_app_state()
        state = build_frontend_state()
        assert state["calibration"]["capturedCount"] == 0
        assert state["review"]["capturedFaceCount"] == 0
        assert state["solves"]["standard"] is None

    with WEB_SESSION_STORE.activate(first):
        state = load_app_state()
        assert state["calibration"]["colors"]["GREEN"] == [0, 180, 0]
        assert state["solves"]["standard"]["status"] == "success"


def test_solver_operates_on_requesting_session_cube():
    session_id = new_session_id()
    with WEB_SESSION_STORE.activate(session_id):
        reset_app_state()
        solved = CubeState.from_facelet_string(SOLVED_FACELETS)
        update_app_state({"scanner": {"faces": solved.to_faces_dict()}})
        result = solve_standard()
        assert result["status"] == "success"
        assert result["moveCount"] == len(result["moves"])
        assert load_app_state()["solves"]["standard"]["status"] == "success"
