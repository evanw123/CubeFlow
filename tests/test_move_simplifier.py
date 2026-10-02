from __future__ import annotations

from cube_backend.move_simplifier import combine_adjacent_moves, simplify_move_string, simplify_moves


def test_move_simplifier_removes_cancellations():
    assert simplify_moves(["B", "B'"]) == []
    assert simplify_moves(["L'", "L'"]) == ["L2"]
    assert simplify_moves(["U", "U", "U"]) == ["U'"]
    assert simplify_moves(["R2", "R2"]) == []


def test_move_simplifier_handles_cube_rotations():
    assert simplify_moves(["y", "y'"]) == []
    assert simplify_moves(["y", "y"]) == ["y2"]
    assert simplify_moves(["y", "y", "y"]) == ["y'"]


def test_combine_adjacent_moves():
    assert combine_adjacent_moves("R", "R") == ["R2"]
    assert combine_adjacent_moves("R", "R2") == ["R'"]
    assert combine_adjacent_moves("R2", "R2") == []
    assert combine_adjacent_moves("R", "U") is None


def test_simplify_move_string():
    assert simplify_move_string("B B' L' L' U U U R2 R2 y y y") == "L2 U' y'"
