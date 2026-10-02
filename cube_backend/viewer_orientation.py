from __future__ import annotations

from .move_utils import normalize_move_token


CANONICAL_VIEWER_ORIENTATION = {
    "top": "YELLOW",
    "bottom": "WHITE",
    "front": "GREEN",
    "right": "ORANGE",
    "left": "RED",
    "back": "BLUE",
}

CANONICAL_VIEWER_SETUP_TEXT = (
    "Hold the cube with WHITE on the bottom, GREEN facing you, and RED on the left."
)

# The stored model uses U=white, D=yellow, F=green, R=red, and L=orange.
# Rotate it 180 degrees around the Green/Blue axis to put white on the bottom.
# This is a rigid cube rotation, so it also moves red from right to left.
_VIEWER_MOVE_BASE = {
    "U": "D",
    "D": "U",
    "F": "F",
    "B": "B",
    "R": "L",
    "L": "R",
    "u": "d",
    "d": "u",
    "f": "f",
    "b": "b",
    "r": "l",
    "l": "r",
    "M": "M",
    "E": "E",
    "S": "S",
    "x": "x",
    "y": "y",
    "z": "z",
}

# Middle slices and whole-cube rotations around axes reversed by the z2 setup
# need their direction inverted. Outer and wide moves change face names instead.
_VIEWER_DIRECTION_FLIP = {"M", "E", "x", "y"}


def canonicalize_view_snapshot(snapshot: dict) -> dict:
    """Rotate a stored snapshot into the physical white-bottom hold."""
    canonical = {
        face: [[None for _ in range(3)] for _ in range(3)]
        for face in ("U", "R", "F", "D", "L", "B")
    }

    for source_face, source_grid in snapshot.items():
        for row in range(3):
            for col in range(3):
                position, normal = _facelet_to_coordinate(source_face, row, col)
                viewer_position = _rotate_z2(position)
                viewer_normal = _rotate_z2(normal)
                viewer_face, viewer_row, viewer_col = _coordinate_to_facelet(
                    viewer_position,
                    viewer_normal,
                )
                canonical[viewer_face][viewer_row][viewer_col] = source_grid[row][col]

    return canonical


def map_internal_move_to_viewer(move: str) -> str:
    normalized = normalize_move_token(move)
    base = normalized[0]
    suffix = normalized[1:]
    viewer_base = _VIEWER_MOVE_BASE[base]

    if base in _VIEWER_DIRECTION_FLIP:
        suffix = _invert_suffix(suffix)

    return normalize_move_token(viewer_base + suffix)


def map_internal_moves_to_viewer(moves: list[str]) -> list[str]:
    return [map_internal_move_to_viewer(move) for move in moves]


def map_viewer_move_to_internal(move: str) -> str:
    # A 180-degree setup rotation is its own inverse.
    return map_internal_move_to_viewer(move)


def map_viewer_moves_to_internal(moves: list[str]) -> list[str]:
    return [map_viewer_move_to_internal(move) for move in moves]


def _rotate_z2(vector: tuple[int, int, int]) -> tuple[int, int, int]:
    x, y, z = vector
    return -x, -y, z


def _facelet_to_coordinate(
    face: str,
    row: int,
    col: int,
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    if face == "F":
        return (col - 1, 1 - row, 1), (0, 0, 1)
    if face == "B":
        return (1 - col, 1 - row, -1), (0, 0, -1)
    if face == "R":
        return (1, 1 - row, 1 - col), (1, 0, 0)
    if face == "L":
        return (-1, 1 - row, col - 1), (-1, 0, 0)
    if face == "U":
        return (col - 1, 1, row - 1), (0, 1, 0)
    if face == "D":
        return (col - 1, -1, 1 - row), (0, -1, 0)
    raise ValueError(f"Unsupported face: {face}")


def _coordinate_to_facelet(
    position: tuple[int, int, int],
    normal: tuple[int, int, int],
) -> tuple[str, int, int]:
    x, y, z = position
    if normal == (0, 0, 1):
        return "F", 1 - y, x + 1
    if normal == (0, 0, -1):
        return "B", 1 - y, 1 - x
    if normal == (1, 0, 0):
        return "R", 1 - y, 1 - z
    if normal == (-1, 0, 0):
        return "L", 1 - y, z + 1
    if normal == (0, 1, 0):
        return "U", z + 1, x + 1
    if normal == (0, -1, 0):
        return "D", 1 - z, x + 1
    raise ValueError(f"Unsupported face normal: {normal}")


def _invert_suffix(suffix: str) -> str:
    if suffix == "2":
        return "2"
    if suffix == "'":
        return ""
    return "'"
