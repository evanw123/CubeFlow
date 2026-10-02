from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .cubie_model import CubieCube
from .solver_bridge import SolveResult, solve_cube_state
from .validator import ValidationResult, validate_cube_state

SLOT_TO_CENTER_COLOR = {
    "F": "GREEN",
    "R": "RED",
    "B": "BLUE",
    "L": "ORANGE",
    "U": "WHITE",
    "D": "YELLOW",
}

COLOR_TO_FACELET = {
    "WHITE": "U",
    "RED": "R",
    "GREEN": "F",
    "YELLOW": "D",
    "ORANGE": "L",
    "BLUE": "B",
}

FACELET_ORDER = ["U", "R", "F", "D", "L", "B"]
FACE_ORDER = ["F", "R", "B", "L", "U", "D"]
FACE_TO_SLOT = {"U": "U", "R": "R", "F": "F", "D": "D", "L": "L", "B": "B"}

FaceGrid = List[List[str]]
FaceMap = Dict[str, Optional[FaceGrid]]


@dataclass
class CubeState:
    faces: FaceMap = field(default_factory=lambda: {slot: None for slot in FACE_ORDER})

    def set_face(self, slot: str, grid: FaceGrid) -> None:
        if slot not in self.faces:
            raise ValueError(f"Invalid slot: {slot}")
        if len(grid) != 3 or any(len(row) != 3 for row in grid):
            raise ValueError("Face grid must be 3x3")
        self.faces[slot] = [row[:] for row in grid]

    def clear_face(self, slot: str) -> None:
        if slot not in self.faces:
            raise ValueError(f"Invalid slot: {slot}")
        self.faces[slot] = None

    def clear_all(self) -> None:
        for slot in self.faces:
            self.faces[slot] = None

    def is_complete(self) -> bool:
        return all(self.faces[slot] is not None for slot in self.faces)

    def color_counts(self) -> Counter:
        counts = Counter()
        for grid in self.faces.values():
            if grid is None:
                continue
            for row in grid:
                for color in row:
                    counts[color] += 1
        return counts

    def get_center(self, slot: str) -> str | None:
        grid = self.faces.get(slot)
        if grid is None:
            return None
        return grid[1][1]

    def validate(self) -> tuple[bool, list[str]]:
        errors: list[str] = []

        for slot in FACE_ORDER:
            if self.faces[slot] is None:
                errors.append(f"Missing face: {slot}")

        if errors:
            return False, errors

        for slot, expected_center in SLOT_TO_CENTER_COLOR.items():
            actual_center = self.get_center(slot)
            if actual_center != expected_center:
                errors.append(
                    f"Center mismatch for {slot}: expected {expected_center}, got {actual_center}"
                )

        counts = self.color_counts()

        if counts.get("UNKNOWN", 0) > 0:
            errors.append(f"Found UNKNOWN stickers: {counts['UNKNOWN']}")

        expected_colors = ["WHITE", "YELLOW", "RED", "ORANGE", "BLUE", "GREEN"]
        for color in expected_colors:
            actual = counts.get(color, 0)
            if actual != 9:
                errors.append(f"Color count for {color}: expected 9, got {actual}")

        extra_colors = set(counts.keys()) - set(expected_colors) - {"UNKNOWN"}
        for color in extra_colors:
            errors.append(f"Unexpected color label present: {color}")

        return len(errors) == 0, errors

    def validate_deep(self) -> ValidationResult:
        return validate_cube_state(self)

    def solve(self) -> SolveResult:
        return solve_cube_state(self)

    def to_cubie_cube(self) -> CubieCube:
        return CubieCube.from_facelet_string(self.to_facelet_string())

    def to_facelet_string(self) -> str:
        if not self.is_complete():
            raise ValueError("CubeState incomplete")

        chars: list[str] = []
        for slot in FACELET_ORDER:
            grid = self.faces[slot]
            assert grid is not None
            for row in grid:
                for color in row:
                    if color not in COLOR_TO_FACELET:
                        raise ValueError(f"Cannot export color: {color}")
                    chars.append(COLOR_TO_FACELET[color])
        return "".join(chars)

    def to_faces_dict(self) -> FaceMap:
        return {
            slot: None if grid is None else [row[:] for row in grid]
            for slot, grid in self.faces.items()
        }

    @classmethod
    def from_facelet_string(cls, facelets: str) -> "CubeState":
        if len(facelets) != 54:
            raise ValueError(f"Facelet string must have length 54, got {len(facelets)}")

        cube_state = cls()
        offset = 0
        for slot in FACELET_ORDER:
            chars = facelets[offset:offset + 9]
            cube_state.faces[slot] = [
                [next(color for color, facelet in COLOR_TO_FACELET.items() if facelet == chars[row * 3 + col]) for col in range(3)]
                for row in range(3)
            ]
            offset += 9
        return cube_state

    @classmethod
    def from_faces_dict(cls, faces: FaceMap | dict[str, list[list[str]] | None]) -> "CubeState":
        cube_state = cls()
        for slot in FACE_ORDER:
            grid = faces.get(slot)
            cube_state.faces[slot] = None if grid is None else [row[:] for row in grid]
        return cube_state
