from __future__ import annotations

from cube_backend.cubie_model import CubieCube
from cube_backend.move_utils import invert_alg
from cube_backend.validator import validate_facelet_string


SOLVED_FACELETS = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"


def test_solved_cube_round_trip_facelets_to_cubies_to_facelets():
    cube = CubieCube.from_facelet_string(SOLVED_FACELETS)
    assert cube.to_facelet_string() == SOLVED_FACELETS


def test_facelet_round_trip_preserves_all_colors_after_algorithm():
    cube = CubieCube.solved()
    cube.apply_alg("R U R' U'")
    facelets = cube.to_facelet_string()

    round_tripped = CubieCube.from_facelet_string(facelets).to_facelet_string()
    assert round_tripped == facelets


def test_applying_u_four_times_returns_solved():
    cube = CubieCube.solved()
    for _ in range(4):
        cube.apply_move("U")
    assert cube.to_facelet_string() == SOLVED_FACELETS


def test_applying_r_four_times_returns_solved():
    cube = CubieCube.solved()
    for _ in range(4):
        cube.apply_move("R")
    assert cube.to_facelet_string() == SOLVED_FACELETS


def test_applying_f_four_times_returns_solved():
    cube = CubieCube.solved()
    for _ in range(4):
        cube.apply_move("F")
    assert cube.to_facelet_string() == SOLVED_FACELETS


def test_applying_alg_then_inverse_returns_solved():
    cube = CubieCube.solved()
    algorithm = "R U R' U'"
    cube.apply_alg(algorithm)
    cube.apply_alg(invert_alg(algorithm))
    assert cube.to_facelet_string() == SOLVED_FACELETS


def test_applying_r_u_r_prime_u_prime_changes_the_solved_cube():
    cube = CubieCube.solved()
    cube.apply_alg("R U R' U'")
    assert cube.to_facelet_string() != SOLVED_FACELETS


def test_sequence_facelets_are_still_a_valid_54_character_cube_string():
    cube = CubieCube.solved()
    cube.apply_alg("F2 L D' B R2 U")
    facelets = cube.to_facelet_string()

    assert len(facelets) == 54
    validation = validate_facelet_string(facelets)
    assert validation.is_valid is True
