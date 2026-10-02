from __future__ import annotations

import importlib.util

import pytest

from cube_backend.solver_bridge import solve_facelet_string
from cube_backend.validator import validate_cube_state, validate_facelet_string


SOLVED_FACELETS = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"


def set_facelets(facelets: str, updates: dict[int, str]) -> str:
    chars = list(facelets)
    for index, value in updates.items():
        chars[index] = value
    return "".join(chars)


def test_solved_cube_is_valid():
    result = validate_facelet_string(SOLVED_FACELETS)
    assert result.is_valid is True
    assert result.solver_ready is True
    assert result.errors == []


def test_invalid_length():
    result = validate_facelet_string(SOLVED_FACELETS[:-1])
    assert result.is_valid is False
    assert "length 54" in result.errors[0]


def test_invalid_characters():
    invalid_facelets = set_facelets(SOLVED_FACELETS, {0: "X"})
    result = validate_facelet_string(invalid_facelets)
    assert result.is_valid is False
    assert any("Invalid facelet characters" in error for error in result.errors)


def test_invalid_color_counts():
    invalid_facelets = set_facelets(SOLVED_FACELETS, {0: "U", 9: "U"})
    result = validate_facelet_string(invalid_facelets)
    assert result.is_valid is False
    assert any("Facelet counts invalid" in error for error in result.errors)


def test_single_edge_flip_is_invalid():
    flipped = set_facelets(SOLVED_FACELETS, {7: "F", 19: "U"})
    result = validate_facelet_string(flipped)
    assert result.is_valid is False
    assert any("Edge flip sum invalid" in error for error in result.errors)


def test_single_corner_twist_is_invalid():
    twisted = set_facelets(SOLVED_FACELETS, {8: "R", 9: "F", 20: "U"})
    result = validate_facelet_string(twisted)
    assert result.is_valid is False
    assert any("Corner twist sum invalid" in error for error in result.errors)


def test_two_edge_swap_is_invalid():
    swapped = set_facelets(
        SOLVED_FACELETS,
        {
            7: "U",
            19: "L",
            3: "U",
            37: "F",
        },
    )
    result = validate_facelet_string(swapped)
    assert result.is_valid is False
    assert any("Permutation parity mismatch" in error for error in result.errors)


def test_validate_cube_state_wrapper():
    class DummyCubeState:
        def to_facelet_string(self) -> str:
            return SOLVED_FACELETS

    result = validate_cube_state(DummyCubeState())
    assert result.is_valid is True
    assert result.solver_ready is True


@pytest.mark.skipif(importlib.util.find_spec("kociemba") is None, reason="kociemba not installed")
def test_solver_bridge_with_solved_cube():
    result = solve_facelet_string(SOLVED_FACELETS)
    assert result.success is True
    assert result.error is None
    assert result.moves is not None
