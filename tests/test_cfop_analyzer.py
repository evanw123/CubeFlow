from __future__ import annotations

from cube_backend.cfop_analyzer import (
    analyze_cfop,
    is_oll_solved,
    to_white_cross_working_facelets,
)
from cube_backend.cubie_model import CubieCube


SOLVED_FACELETS = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"


def test_solved_cube_cfop_analysis():
    analysis = analyze_cfop(CubieCube.solved())

    assert analysis.cross.solved is True
    assert analysis.cross.solved_count == 4
    assert analysis.f2l_slots_solved == 4
    assert analysis.oll_solved is True
    assert analysis.pll_solved is True
    assert analysis.fully_solved is True


def test_simple_scramble_analysis_runs():
    cube = CubieCube.solved()
    cube.apply_alg("R U R' U'")

    analysis = analyze_cfop(cube)

    assert 0 <= analysis.cross.solved_count <= 4
    assert len(analysis.f2l_pairs) == 4


def test_white_cross_can_stay_solved_while_cube_is_unsolved():
    cube = CubieCube.solved()
    cube.apply_move("D")

    analysis = analyze_cfop(cube)

    assert analysis.cross.solved is True
    assert analysis.cross.solved_count == 4
    assert analysis.fully_solved is False
    assert analysis.pll_solved is False


def test_is_oll_solved_false_after_non_oll_state():
    cube = CubieCube.solved()
    cube.apply_move("R")

    assert is_oll_solved(cube) is False


def test_pair_states_have_valid_slot_names():
    analysis = analyze_cfop(CubieCube.solved())
    slots = [pair_state.slot for pair_state in analysis.f2l_pairs]

    assert slots == ["FR", "FL", "BL", "BR"]


def test_working_facelet_helper_swaps_white_and_yellow_roles():
    working_facelets = to_white_cross_working_facelets(SOLVED_FACELETS)

    assert working_facelets[0:9] == "DDDDDDDDD"
    assert working_facelets[27:36] == "UUUUUUUUU"
