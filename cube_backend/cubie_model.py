from __future__ import annotations

from dataclasses import dataclass

from .move_utils import normalize_move_token, parse_alg
from .validator import (
    CORNER_COLORS,
    CORNER_FACELETS,
    EDGE_COLORS,
    EDGE_FACELETS,
    parse_facelets_to_cubies,
)


SOLVED_FACELETS = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"
FACE_NAMES = ["U", "R", "F", "D", "L", "B"]
CENTER_FACELETS = {
    4: "U",
    13: "R",
    22: "F",
    31: "D",
    40: "L",
    49: "B",
}

# Face geometry is defined explicitly so facelet rotation, viewer geometry,
# and face orientation all stay auditable and consistent.
FACE_TO_AXIS_INFO = {
    "U": {"normal": (0, 1, 0), "up": (0, 0, -1)},
    "R": {"normal": (1, 0, 0), "up": (0, 1, 0)},
    "F": {"normal": (0, 0, 1), "up": (0, 1, 0)},
    "D": {"normal": (0, -1, 0), "up": (0, 0, 1)},
    "L": {"normal": (-1, 0, 0), "up": (0, 1, 0)},
    "B": {"normal": (0, 0, -1), "up": (0, 1, 0)},
}


@dataclass
class CubieCube:
    corner_perm: list[int]
    corner_ori: list[int]
    edge_perm: list[int]
    edge_ori: list[int]

    @classmethod
    def solved(cls) -> "CubieCube":
        return cls(
            corner_perm=list(range(8)),
            corner_ori=[0] * 8,
            edge_perm=list(range(12)),
            edge_ori=[0] * 12,
        )

    @classmethod
    def from_facelet_string(cls, facelets: str) -> "CubieCube":
        parsed = parse_facelets_to_cubies(facelets)
        return cls(
            corner_perm=parsed.corner_perm[:],
            corner_ori=parsed.corner_ori[:],
            edge_perm=parsed.edge_perm[:],
            edge_ori=parsed.edge_ori[:],
        )

    @classmethod
    def from_dict(cls, data: dict) -> "CubieCube":
        return cls(
            corner_perm=list(data["corner_perm"]),
            corner_ori=list(data["corner_ori"]),
            edge_perm=list(data["edge_perm"]),
            edge_ori=list(data["edge_ori"]),
        )

    def copy(self) -> "CubieCube":
        return CubieCube(
            corner_perm=self.corner_perm[:],
            corner_ori=self.corner_ori[:],
            edge_perm=self.edge_perm[:],
            edge_ori=self.edge_ori[:],
        )

    def to_facelet_string(self) -> str:
        facelets = ["?"] * 54

        # Center stickers never move in the facelet model, so seed them first.
        for index, face_name in CENTER_FACELETS.items():
            facelets[index] = face_name

        for position_index, facelet_indices in enumerate(CORNER_FACELETS):
            cubie_index = self.corner_perm[position_index]
            orientation = self.corner_ori[position_index]
            colors = CORNER_COLORS[cubie_index]

            facelets[facelet_indices[orientation % 3]] = colors[0]
            facelets[facelet_indices[(orientation + 1) % 3]] = colors[1]
            facelets[facelet_indices[(orientation + 2) % 3]] = colors[2]

        for position_index, facelet_indices in enumerate(EDGE_FACELETS):
            cubie_index = self.edge_perm[position_index]
            orientation = self.edge_ori[position_index]
            colors = EDGE_COLORS[cubie_index]

            if orientation == 0:
                facelets[facelet_indices[0]] = colors[0]
                facelets[facelet_indices[1]] = colors[1]
            else:
                facelets[facelet_indices[0]] = colors[1]
                facelets[facelet_indices[1]] = colors[0]

        return "".join(facelets)

    def multiply(self, other: "CubieCube") -> "CubieCube":
        """
        Compose this cube with another cube state.

        The returned cube is equivalent to:
        - start from this cube
        - then apply the transformation encoded by 'other'
        """
        result = CubieCube.solved()

        for position_index in range(8):
            source_index = other.corner_perm[position_index]
            result.corner_perm[position_index] = self.corner_perm[source_index]
            result.corner_ori[position_index] = (
                self.corner_ori[source_index] + other.corner_ori[position_index]
            ) % 3

        for position_index in range(12):
            source_index = other.edge_perm[position_index]
            result.edge_perm[position_index] = self.edge_perm[source_index]
            result.edge_ori[position_index] = (
                self.edge_ori[source_index] + other.edge_ori[position_index]
            ) % 2

        return result

    def apply_times(self, base_move: "CubieCube", n: int) -> None:
        for _ in range(n % 4):
            updated = self.multiply(base_move)
            self.corner_perm = updated.corner_perm
            self.corner_ori = updated.corner_ori
            self.edge_perm = updated.edge_perm
            self.edge_ori = updated.edge_ori

    def apply_move(self, move: str) -> None:
        normalized = normalize_move_token(move)
        expanded_moves = expand_move_token(normalized)

        for expanded_move in expanded_moves:
            base_move = MOVE_CUBES[expanded_move[0]]

            if expanded_move.endswith("2"):
                turns = 2
            elif expanded_move.endswith("'"):
                turns = 3
            else:
                turns = 1

            self.apply_times(base_move, turns)

    def apply_alg(self, alg: str | list[str]) -> None:
        moves = parse_alg(alg) if isinstance(alg, str) else [normalize_move_token(move) for move in alg]
        for move in moves:
            self.apply_move(move)

    def as_dict(self) -> dict:
        return {
            "corner_perm": self.corner_perm[:],
            "corner_ori": self.corner_ori[:],
            "edge_perm": self.edge_perm[:],
            "edge_ori": self.edge_ori[:],
        }


def _build_facelet_descriptors() -> tuple[list[dict], dict]:
    descriptors: list[dict] = []
    descriptor_to_index: dict[tuple[tuple[int, int, int], tuple[int, int, int]], int] = {}

    for face_offset, face_name in enumerate(FACE_NAMES):
        face_info = FACE_TO_AXIS_INFO[face_name]
        normal = face_info["normal"]
        up = face_info["up"]
        right = _cross(up, normal)

        for row in range(3):
            for col in range(3):
                u_center = -2 + col * 2
                v_center = 2 - row * 2
                center = _add(_scale(normal, 3), _add(_scale(right, u_center), _scale(up, v_center)))
                descriptor = {
                    "face": face_name,
                    "row": row,
                    "col": col,
                    "center": center,
                    "normal": normal,
                }
                index = face_offset * 9 + row * 3 + col
                descriptors.append(descriptor)
                descriptor_to_index[(center, normal)] = index

    return descriptors, descriptor_to_index


def _clockwise_turns_for_face(face_name: str) -> int:
    face_info = FACE_TO_AXIS_INFO[face_name]
    normal = face_info["normal"]
    up = face_info["up"]
    right = _cross(up, normal)
    axis_name = _axis_name_from_normal(normal)

    if _rotate_vector_90(up, axis_name, 1) == right:
        return 1
    if _rotate_vector_90(up, axis_name, -1) == right:
        return -1
    raise ValueError(f"Could not determine clockwise rotation for face {face_name}")


def _apply_face_turn_to_facelets(facelets: str, face_name: str) -> str:
    descriptors = FACELET_DESCRIPTORS
    turned = ["?"] * 54

    normal = FACE_TO_AXIS_INFO[face_name]["normal"]
    axis_name = _axis_name_from_normal(normal)
    axis_index = "xyz".index(axis_name)
    layer_sign = normal[axis_index]
    turns = _clockwise_turns_for_face(face_name)

    for old_index, descriptor in enumerate(descriptors):
        center = descriptor["center"]
        sticker_normal = descriptor["normal"]

        if center[axis_index] * layer_sign > 1:
            new_center = _rotate_vector_90(center, axis_name, turns)
            new_normal = _rotate_vector_90(sticker_normal, axis_name, turns)
        else:
            new_center = center
            new_normal = sticker_normal

        new_index = FACELET_DESCRIPTOR_TO_INDEX[(new_center, new_normal)]
        turned[new_index] = facelets[old_index]

    return "".join(turned)


def _build_base_move_cube(face_name: str) -> CubieCube:
    moved_facelets = _apply_face_turn_to_facelets(SOLVED_FACELETS, face_name)
    return CubieCube.from_facelet_string(moved_facelets)


def _apply_axis_turn_to_facelets(
    facelets: str,
    axis_name: str,
    selector,
    turns: int,
) -> str:
    turned = ["?"] * 54
    axis_index = "xyz".index(axis_name)

    for old_index, descriptor in enumerate(FACELET_DESCRIPTORS):
        center = descriptor["center"]
        sticker_normal = descriptor["normal"]

        if selector(center[axis_index]):
            new_center = _rotate_vector_90(center, axis_name, turns)
            new_normal = _rotate_vector_90(sticker_normal, axis_name, turns)
        else:
            new_center = center
            new_normal = sticker_normal

        new_index = FACELET_DESCRIPTOR_TO_INDEX[(new_center, new_normal)]
        turned[new_index] = facelets[old_index]

    return "".join(turned)


def _build_slice_move_cube(slice_name: str) -> CubieCube:
    slice_to_config = {
        "M": ("x", lambda coordinate: coordinate == 0, -1),
        "E": ("y", lambda coordinate: coordinate == 0, 1),
        "S": ("z", lambda coordinate: coordinate == 0, -1),
    }
    axis_name, selector, turns = slice_to_config[slice_name]
    moved_facelets = _apply_axis_turn_to_facelets(SOLVED_FACELETS, axis_name, selector, turns)
    return CubieCube.from_facelet_string(moved_facelets)


def _compose_suffix(move: str, suffix: str) -> str:
    normalized = normalize_move_token(move)
    base_face = normalized[0]

    if normalized.endswith("2"):
        base_turns = 2
    elif normalized.endswith("'"):
        base_turns = 3
    else:
        base_turns = 1

    if suffix == "2":
        suffix_turns = 2
    elif suffix == "'":
        suffix_turns = 3
    else:
        suffix_turns = 1

    total_turns = (base_turns * suffix_turns) % 4
    if total_turns == 0:
        return ""
    if total_turns == 1:
        return base_face
    if total_turns == 2:
        return base_face + "2"
    return base_face + "'"


ALIASED_BASE_MOVES = {
    "x": ["R", "M'", "L'"],
    "y": ["U", "E'", "D'"],
    "z": ["F", "S", "B'"],
    "r": ["R", "M'"],
    "l": ["L", "M"],
    "u": ["U", "E'"],
    "d": ["D", "E"],
    "f": ["F", "S"],
    "b": ["B", "S'"],
}


def expand_move_token(move: str) -> list[str]:
    normalized = normalize_move_token(move)
    face = normalized[0]
    suffix = normalized[1:]

    if face in MOVE_CUBES:
        return [normalized]

    if face not in ALIASED_BASE_MOVES:
        raise ValueError(f"Unsupported move token: {move}")

    expanded: list[str] = []
    for base_move in ALIASED_BASE_MOVES[face]:
        combined = _compose_suffix(base_move, suffix)
        if combined:
            expanded.append(combined)
    return expanded


def _axis_name_from_normal(normal: tuple[int, int, int]) -> str:
    if normal[0] != 0:
        return "x"
    if normal[1] != 0:
        return "y"
    return "z"


def _rotate_vector_90(vector: tuple[int, int, int], axis_name: str, turns: int) -> tuple[int, int, int]:
    turns_mod = turns % 4
    x, y, z = vector

    for _ in range(turns_mod):
        if axis_name == "x":
            x, y, z = x, -z, y
        elif axis_name == "y":
            x, y, z = z, y, -x
        elif axis_name == "z":
            x, y, z = -y, x, z
        else:
            raise ValueError(f"Invalid rotation axis: {axis_name}")

    return x, y, z


def _add(a: tuple[int, int, int], b: tuple[int, int, int]) -> tuple[int, int, int]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(vector: tuple[int, int, int], scale: int) -> tuple[int, int, int]:
    return (vector[0] * scale, vector[1] * scale, vector[2] * scale)


def _cross(a: tuple[int, int, int], b: tuple[int, int, int]) -> tuple[int, int, int]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


FACELET_DESCRIPTORS, FACELET_DESCRIPTOR_TO_INDEX = _build_facelet_descriptors()

MOVE_U = _build_base_move_cube("U")
MOVE_R = _build_base_move_cube("R")
MOVE_F = _build_base_move_cube("F")
MOVE_D = _build_base_move_cube("D")
MOVE_L = _build_base_move_cube("L")
MOVE_B = _build_base_move_cube("B")
MOVE_M = _build_slice_move_cube("M")
MOVE_E = _build_slice_move_cube("E")
MOVE_S = _build_slice_move_cube("S")

MOVE_CUBES = {
    "U": MOVE_U,
    "R": MOVE_R,
    "F": MOVE_F,
    "D": MOVE_D,
    "L": MOVE_L,
    "B": MOVE_B,
    "M": MOVE_M,
    "E": MOVE_E,
    "S": MOVE_S,
}
