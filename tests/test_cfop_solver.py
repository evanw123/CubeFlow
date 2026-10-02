from __future__ import annotations

from cube_backend.cfop_analyzer import get_human_orientation_setup_text, to_cfop_working_facelets
from cube_backend.cfop_models import CFOPSolveResult
from cube_backend.cfop_solver import (
    build_cfop_playback_session,
    format_cfop_solution,
    solve_cfop,
    solve_cfop_from_facelets,
)
from cube_backend.cubie_model import CubieCube


SOLVED_FACELETS = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"


def test_cfop_orientation_is_white_bottom_green_front():
    oriented = to_cfop_working_facelets(SOLVED_FACELETS)

    assert oriented[27:36] == "UUUUUUUUU"
    assert oriented[18:27] == "FFFFFFFFF"


def test_cfop_setup_text_is_explicit():
    assert get_human_orientation_setup_text() == "Hold the cube with WHITE on bottom and GREEN facing you."


def test_cfop_solver_delegates_to_pycube_adapter(monkeypatch):
    sentinel = CFOPSolveResult(
        success=True,
        error=None,
        failing_stage=None,
        failing_slot=None,
        failing_case_id=None,
        setup_text="Hold the cube with WHITE on bottom and GREEN facing you.",
        stages=[],
        cross_moves=[],
        f2l_slot_results=[],
        oll_result=None,
        pll_result=None,
        auf_moves=[],
        full_moves=[],
        full_move_string="",
        final_facelets=SOLVED_FACELETS,
    )

    monkeypatch.setattr("cube_backend.cfop_solver.solve_cfop_with_pycube", lambda facelets: sentinel)

    result = solve_cfop_from_facelets(SOLVED_FACELETS)

    assert result is sentinel


def test_cfop_beta_path_returns_valid_move_list():
    cube = CubieCube.solved()
    cube.apply_alg(["R", "U", "R'", "U'"])

    result = solve_cfop(cube)

    assert result.success is True
    assert result.full_moves == ["U", "R", "U'", "R'"]
    assert result.final_facelets == SOLVED_FACELETS


def test_cfop_beta_uses_coarse_pycube_stage_metadata():
    cube = CubieCube.solved()
    cube.apply_alg(["F", "R", "U", "R'", "U'", "F'"])

    result = solve_cfop(cube)

    assert result.success is True
    assert [stage.name for stage in result.stages] == [
        "White Cross",
        "F2L",
        "OLL",
        "PLL",
    ]

    assert result.segmentation_source == "solver_metadata"
    assert result.segmentation_verified is True
    assert result.segmentation_warning is None


def test_playback_launch_uses_returned_move_list_without_crashing():
    cube = CubieCube.solved()
    cube.apply_alg(["R", "U", "R'", "U'"])
    result = solve_cfop(cube)

    session = build_cfop_playback_session(cube.to_facelet_string(), result)

    assert session["moves"] == result.full_moves
    assert session["title"] == "CFOP Beta Playback"


def test_failed_cfop_result_does_not_build_playback():
    result = solve_cfop_from_facelets("U" * 54)

    assert result.success is False
    try:
        build_cfop_playback_session(SOLVED_FACELETS, result)
    except ValueError as exc:
        assert "CFOP solve failed" in str(exc)
    else:
        raise AssertionError("CFOP playback session should not be built for a failed solve.")


def test_format_cfop_solution_includes_setup_text():
    cube = CubieCube.solved()
    cube.apply_alg(["R", "U", "R'", "U'"])

    result = solve_cfop(cube)
    formatted = format_cfop_solution(result)

    assert "Hold the cube with WHITE on bottom and GREEN facing you." in formatted
    assert "White Cross:" in formatted
    assert "Combined:" in formatted
