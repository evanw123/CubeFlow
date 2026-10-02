from __future__ import annotations

import json
from pathlib import Path

from .viewer_orientation import canonicalize_view_snapshot


FACE_NAMES = ["U", "R", "F", "D", "L", "B"]
FACELET_ORDER = ["U", "R", "F", "D", "L", "B"]

FACELET_TO_COLOR = {
    "U": "WHITE",
    "R": "RED",
    "F": "GREEN",
    "D": "YELLOW",
    "L": "ORANGE",
    "B": "BLUE",
}

ALLOWED_STICKER_VALUES = {
    "WHITE",
    "YELLOW",
    "RED",
    "ORANGE",
    "BLUE",
    "GREEN",
    "UNKNOWN",
    None,
}


def cube_state_to_view_snapshot(cube_state) -> dict[str, list[list[str | None]]]:
    """Convert scanner faces into the canonical white-bottom viewer mapping."""
    snapshot: dict[str, list[list[str | None]]] = {}

    for face_name in FACE_NAMES:
        face_grid = cube_state.faces.get(face_name)
        if face_grid is None:
            snapshot[face_name] = [[None for _ in range(3)] for _ in range(3)]
            continue

        snapshot[face_name] = [
            [_normalize_snapshot_value(value) for value in row]
            for row in face_grid
        ]

    return canonicalize_view_snapshot(snapshot)


def facelet_string_to_view_snapshot(facelets: str) -> dict[str, list[list[str]]]:
    """Convert URFDLB facelets into the canonical white-bottom viewer mapping."""
    _validate_facelet_string_for_view(facelets)

    snapshot: dict[str, list[list[str]]] = {}
    offset = 0
    for face_name in FACELET_ORDER:
        face_chars = facelets[offset:offset + 9]
        snapshot[face_name] = [
            [FACELET_TO_COLOR[face_chars[row * 3 + col]] for col in range(3)]
            for row in range(3)
        ]
        offset += 9

    return canonicalize_view_snapshot(snapshot)


def validate_view_snapshot(snapshot: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if not isinstance(snapshot, dict):
        return False, ["Snapshot must be a dictionary keyed by face name."]

    missing_faces = [face_name for face_name in FACE_NAMES if face_name not in snapshot]
    if missing_faces:
        errors.append(f"Snapshot missing faces: {missing_faces}")

    extra_faces = sorted(set(snapshot.keys()) - set(FACE_NAMES))
    if extra_faces:
        errors.append(f"Snapshot has unexpected faces: {extra_faces}")

    for face_name in FACE_NAMES:
        if face_name not in snapshot:
            continue

        face_grid = snapshot[face_name]
        if not isinstance(face_grid, list) or len(face_grid) != 3:
            errors.append(f"Face {face_name} must be a 3x3 list.")
            continue

        for row_index, row in enumerate(face_grid):
            if not isinstance(row, list) or len(row) != 3:
                errors.append(f"Face {face_name} row {row_index} must have length 3.")
                continue

            for col_index, value in enumerate(row):
                normalized = _normalize_snapshot_value(value)
                if normalized not in ALLOWED_STICKER_VALUES:
                    errors.append(
                        f"Invalid sticker value at {face_name}[{row_index}][{col_index}]: {value!r}"
                    )

    return len(errors) == 0, errors


def save_view_snapshot(snapshot: dict, path: str) -> None:
    is_valid, errors = validate_view_snapshot(snapshot)
    if not is_valid:
        raise ValueError("; ".join(errors))

    target = Path(path)
    target.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")


def load_view_snapshot(path: str) -> dict:
    target = Path(path)
    snapshot = json.loads(target.read_text(encoding="utf-8"))
    is_valid, errors = validate_view_snapshot(snapshot)
    if not is_valid:
        raise ValueError("; ".join(errors))
    return snapshot


def _validate_facelet_string_for_view(facelets: str) -> None:
    if len(facelets) != 54:
        raise ValueError(f"Facelet string must have length 54, got {len(facelets)}")

    invalid_chars = sorted(set(facelets) - set(FACELET_TO_COLOR.keys()))
    if invalid_chars:
        raise ValueError(f"Invalid facelet characters: {invalid_chars}")


def _normalize_snapshot_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value.upper()
    return value
