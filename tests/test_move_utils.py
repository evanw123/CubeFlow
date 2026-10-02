from __future__ import annotations

import pytest

from cube_backend.move_utils import invert_alg, invert_move, parse_alg


def test_parse_simple_algorithm():
    assert parse_alg("R U R' U'") == ["R", "U", "R'", "U'"]


def test_parse_with_extra_whitespace():
    assert parse_alg("  F2   L   D'  ") == ["F2", "L", "D'"]


def test_parse_extended_notation():
    assert parse_alg("x M2 r U' z'") == ["x", "M2", "r", "U'", "z'"]


def test_invert_single_move():
    assert invert_move("R") == "R'"
    assert invert_move("U'") == "U"
    assert invert_move("F2") == "F2"
    assert invert_move("M") == "M'"


def test_invert_full_algorithm():
    assert invert_alg("R U") == ["U'", "R'"]


def test_reject_invalid_tokens():
    with pytest.raises(ValueError):
        parse_alg("Rw")

    assert parse_alg("") == []
