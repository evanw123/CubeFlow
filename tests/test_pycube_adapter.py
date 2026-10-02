from __future__ import annotations

import sys
import types

import pytest

from cube_backend.cubie_model import CubieCube
from cube_backend.cfop_segmenter import f2l_complete, oll_complete, pll_complete, white_cross_complete
from cube_backend.pycube_adapter import facelets_to_pycube_faces, pycube_available, solve_cfop_with_pycube
from cube_backend.solver_bridge import solve_facelet_string


SOLVED_FACELETS = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"


def test_pycube_is_available():
    assert pycube_available() is True


def test_facelets_to_pycube_faces_converts_solved_cube():
    faces = facelets_to_pycube_faces(SOLVED_FACELETS)

    assert faces[0] == [["G"] * 3 for _ in range(3)]
    assert faces[1] == [["O"] * 3 for _ in range(3)]
    assert faces[2] == [["B"] * 3 for _ in range(3)]
    assert faces[3] == [["R"] * 3 for _ in range(3)]
    assert faces[4] == [["W"] * 3 for _ in range(3)]
    assert faces[5] == [["Y"] * 3 for _ in range(3)]


def test_solved_cube_returns_zero_moves():
    result = solve_cfop_with_pycube(SOLVED_FACELETS)

    assert result.success is True
    assert result.full_moves == []
    assert result.final_facelets == SOLVED_FACELETS


def test_cfop_beta_returns_valid_move_list_for_easy_scramble():
    cube = CubieCube.solved()
    cube.apply_alg(["F", "R", "U", "R'", "U'", "F'"])

    result = solve_cfop_with_pycube(cube.to_facelet_string())

    assert result.success is True
    assert result.full_moves
    replay = CubieCube.from_facelet_string(cube.to_facelet_string())
    replay.apply_alg(result.full_moves)
    assert replay.to_facelet_string() == SOLVED_FACELETS


def test_cfop_metadata_has_exactly_four_verified_stages():
    cube = CubieCube.solved()
    cube.apply_alg("R2 U F' L2 D B R' U2")
    original_facelets = cube.to_facelet_string()

    result = solve_cfop_with_pycube(original_facelets)

    assert result.success is True
    assert [stage.name for stage in result.stages] == ["White Cross", "F2L", "OLL", "PLL"]
    assert [move for stage in result.stages for move in stage.moves] == result.full_moves
    assert result.segmentation_source == "solver_metadata"
    assert result.segmentation_verified is True

    replay = CubieCube.from_facelet_string(original_facelets)
    predicates = [white_cross_complete, f2l_complete, oll_complete, pll_complete]
    for stage, predicate in zip(result.stages, predicates):
        replay.apply_alg(stage.moves)
        assert predicate(replay) is True

    assert replay.to_facelet_string() == SOLVED_FACELETS


@pytest.mark.parametrize(
    "scramble",
    [
        "F R U R' U' F'",
        "R2 U F' L2 D B R' U2",
        "F2 L D' B2 R U' F L2",
    ],
)
def test_real_scrambles_have_verified_cfop_milestones(scramble):
    cube = CubieCube.solved()
    cube.apply_alg(scramble)
    original_facelets = cube.to_facelet_string()

    result = solve_cfop_with_pycube(original_facelets)

    assert result.success is True
    assert result.segmentation_source == "solver_metadata"
    assert result.segmentation_verified is True
    assert result.segmentation_warning is None

    replay = CubieCube.from_facelet_string(original_facelets)
    predicates = [white_cross_complete, f2l_complete, oll_complete, pll_complete]
    for stage, predicate in zip(result.stages, predicates):
        replay.apply_alg(stage.moves)
        assert predicate(replay) is True


def test_standard_solve_still_works(monkeypatch):
    fake_module = types.SimpleNamespace(solve=lambda facelets: "R U R' U'")
    monkeypatch.setitem(sys.modules, "kociemba", fake_module)

    cube = CubieCube.solved()
    cube.apply_alg(["R", "U", "R'", "U'"])

    result = solve_facelet_string(cube.to_facelet_string())

    assert result.success is True
    assert result.move_list == ["R", "U", "R'", "U'"]
