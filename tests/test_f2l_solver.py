from __future__ import annotations

import cube_backend.solver_bridge as solver_bridge

from cube_backend.cfop_analyzer import is_f2l_slot_solved
from cube_backend.cfop_solver import is_white_cross_solved
from cube_backend.cubie_model import CubieCube
from cube_backend.f2l_algorithms import map_slot_algorithm_from_fr, rotate_algorithm_for_slot, slot_to_y_rotation_prompt
from cube_backend.f2l_solver import analyze_single_f2l_pair, solve_single_f2l_slot


FR_INSERT_SCRAMBLE = ["R'", "D", "R"]
FL_INSERT_SCRAMBLE = ["F'", "D", "F"]
BL_INSERT_SCRAMBLE = ["L'", "D", "L"]
BR_INSERT_SCRAMBLE = ["R", "D", "R'"]
PAIRED_FL_CASE = ["F'", "D'", "F"]
FL_CORNER_TOP_EDGE_MIDDLE = ["F", "L2", "F'", "L2"]
BR_PAIRED_PROBE = ["D", "R2", "D", "R", "D", "R", "D", "R'", "D", "R'", "D", "R'"]


def _build_br_probe_cube() -> CubieCube:
    cube = CubieCube.solved()
    cube.apply_alg(BR_PAIRED_PROBE)
    solve_single_f2l_slot(cube, "FR", [], debug=False)
    solve_single_f2l_slot(cube, "FL", ["FR"], debug=False)
    solve_single_f2l_slot(cube, "BL", ["FR", "FL"], debug=False)
    return cube


def test_f2l_solver_solves_fr_with_simple_insert():
    cube = CubieCube.solved()
    cube.apply_alg(FR_INSERT_SCRAMBLE)

    stage = solve_single_f2l_slot(cube, "FR", [])

    assert stage.success is True
    assert stage.case_id == "SEPARATE_TOP"
    assert stage.cube_rotation == []
    assert stage.display_moves == ["R'", "U'", "R"]
    assert is_white_cross_solved(cube) is True
    assert is_f2l_slot_solved(cube, "FR") is True


def test_f2l_solver_solves_fl_using_rotation_prompt_and_simple_insert():
    cube = CubieCube.solved()
    cube.apply_alg(FL_INSERT_SCRAMBLE)

    stage = solve_single_f2l_slot(cube, "FL", ["FR"])

    assert stage.success is True
    assert stage.case_id == "SEPARATE_TOP"
    assert stage.cube_rotation == ["y"]
    assert stage.display_moves == ["R'", "U'", "R"]
    assert "Pair: R' U' R" in stage.instruction_lines
    assert is_f2l_slot_solved(cube, "FL") is True


def test_f2l_solver_preserves_previous_slots():
    cube = CubieCube.solved()
    cube.apply_alg(FR_INSERT_SCRAMBLE)
    solve_single_f2l_slot(cube, "FR", [])
    cube.apply_alg(FL_INSERT_SCRAMBLE)
    solve_single_f2l_slot(cube, "FL", ["FR"])
    cube.apply_alg(BL_INSERT_SCRAMBLE)

    stage = solve_single_f2l_slot(cube, "BL", ["FR", "FL"])

    assert stage.success is True
    assert is_white_cross_solved(cube) is True
    assert is_f2l_slot_solved(cube, "FR") is True
    assert is_f2l_slot_solved(cube, "FL") is True
    assert is_f2l_slot_solved(cube, "BL") is True


def test_paired_fl_case_no_longer_crashes():
    cube = CubieCube.solved()
    cube.apply_alg(PAIRED_FL_CASE)

    stage = solve_single_f2l_slot(cube, "FL", ["FR"])

    assert stage.success is True or (
        stage.success is False and stage.error is not None and "Unsupported" in stage.error
    )


def test_detailed_case_classification_distinguishes_paired_variants():
    wrong_slot_cube = CubieCube.solved()
    wrong_slot_cube.apply_alg(PAIRED_FL_CASE)
    wrong_slot_case = analyze_single_f2l_pair(wrong_slot_cube, "FL")

    insertable_cube = wrong_slot_cube.copy()
    insertable_cube.apply_alg(["D"])
    insertable_case = analyze_single_f2l_pair(insertable_cube, "FL")

    misoriented_cube = _build_br_probe_cube()
    misoriented_cube.apply_alg(["D2"])
    misoriented_case = analyze_single_f2l_pair(misoriented_cube, "BR")

    assert wrong_slot_case.normalized_case_id == "PAIRED_ABOVE_WRONG_SLOT"
    assert insertable_case.normalized_case_id == "PAIRED_INSERTABLE_BACK"
    assert misoriented_case.normalized_case_id == "PAIRED_TOP_MISORIENTED"


def test_slot_normalization_maps_fr_algorithms_to_fl_correctly():
    assert slot_to_y_rotation_prompt("FL") == ["y"]
    assert map_slot_algorithm_from_fr("FL", ["U", "R", "U'", "R'"]) == ["U", "F", "U'", "F'"]
    assert rotate_algorithm_for_slot("FR", "BL", ["R", "U", "R'"]) == ["L", "U", "L'"]


def test_f2l_solver_handles_fl_corner_top_edge_middle_case():
    cube = CubieCube.solved()
    cube.apply_alg(FL_CORNER_TOP_EDGE_MIDDLE)

    stage = solve_single_f2l_slot(cube, "FL", ["FR"])

    assert stage.success is True
    assert is_white_cross_solved(cube) is True
    assert is_f2l_slot_solved(cube, "FL") is True


def test_f2l_is_pair_insertion_not_rest_of_cube_search(monkeypatch):
    def _raise(*args, **kwargs):
        raise AssertionError("generic solver must not be called from F2L")

    monkeypatch.setattr(solver_bridge, "solve_facelet_string", _raise)
    monkeypatch.setattr(solver_bridge, "solve_cube_state", _raise)

    cube = CubieCube.solved()
    cube.apply_alg(PAIRED_FL_CASE)

    stage = solve_single_f2l_slot(cube, "FL", ["FR"])

    assert stage.success is True or (
        stage.success is False and stage.error is not None and "Unsupported" in stage.error
    )
