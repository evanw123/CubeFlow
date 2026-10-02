from __future__ import annotations

from cube_backend.cfop_analyzer import is_cube_solved
from cube_backend.cubie_model import CubieCube
from cube_backend.move_utils import invert_alg, parse_alg
from cube_backend.oll_algorithms import (
    _compile_human_last_layer_moves_to_global as compile_oll,  # type: ignore
    is_oll_solved,
    recognize_oll,
    solve_oll,
)
from cube_backend.pll_algorithms import (
    _compile_human_last_layer_moves_to_global as compile_pll,  # type: ignore
    apply_final_auf_if_needed,
    recognize_pll,
    solve_pll,
)


OLL_45 = parse_alg("F R U R' U' F'")
OLL_57 = parse_alg("R U R' U' M' U R U' r'")
PLL_UA = parse_alg("M2 U M U2 M' U M2")
PLL_AA = parse_alg("x L2 D2 L' U' L D2 L' U L'")


def test_oll_solver_only_runs_after_f2l():
    cube = CubieCube.solved()
    cube.apply_alg(["R'", "D", "R"])

    stage = solve_oll(cube)

    assert stage.success is False
    assert "F2L" in (stage.error or "")


def test_pll_solver_only_runs_after_oll():
    cube = CubieCube.solved()
    cube.apply_alg(invert_alg(compile_oll(OLL_45)))

    stage = solve_pll(cube)

    assert stage.success is False
    assert "OLL" in (stage.error or "")


def test_oll_solver_handles_more_than_simple_cases():
    for case_id, algorithm in [("OLL_45", OLL_45), ("OLL_57", OLL_57)]:
        cube = CubieCube.solved()
        cube.apply_alg(invert_alg(compile_oll(algorithm)))

        recognized_case_id, auf_turns = recognize_oll(cube)
        stage = solve_oll(cube)

        assert recognized_case_id == case_id
        assert auf_turns == 0
        assert stage.success is True
        assert stage.case_id == case_id
        assert stage.display_moves == algorithm
        assert is_oll_solved(cube) is True


def test_pll_solver_handles_more_than_simple_cases():
    for case_id, algorithm in [("Ua", PLL_UA), ("Aa", PLL_AA)]:
        cube = CubieCube.solved()
        cube.apply_alg(invert_alg(compile_pll(algorithm)))

        recognized_case_id, auf_turns = recognize_pll(cube)
        stage = solve_pll(cube)
        final_auf = apply_final_auf_if_needed(cube)

        assert recognized_case_id == case_id
        assert auf_turns == 0
        assert stage.success is True
        assert stage.case_id == case_id
        assert stage.display_moves == algorithm
        assert final_auf == []
        assert is_cube_solved(cube) is True
