from __future__ import annotations

from dataclasses import dataclass

from .cubie_model import CubieCube, SOLVED_FACELETS
from .move_utils import normalize_move_token
from .validator import CORNER_NAMES, EDGE_NAMES


# ---------------------------------------------------------------------------
# CFOP working-orientation notes
# ---------------------------------------------------------------------------
#
# The scanner's fixed global color convention is:
# - U = WHITE
# - D = YELLOW
# - F = GREEN
# - B = BLUE
# - R = RED
# - L = ORANGE
#
# Human CFOP for this project should conceptually run with:
# - white on the bottom
# - yellow on the top
#
# We represent that working view in two explicit ways:
#
# 1. Facelet-role helpers:
#    `to_cfop_working_facelets()` swaps U/D colors so tests and debug output can
#    inspect the white-bottom / yellow-top view directly.
#
# 2. Stage predicates in global coordinates:
#    The CubieCube piece labels are tied to the scanner's original color names,
#    so the actual cross/F2L/OLL/PLL predicates are written directly against the
#    global cubie coordinates that are equivalent to the CFOP working view.
#
# This keeps the solving logic explicit and avoids pretending there is a single
# physical whole-cube rotation that preserves:
# - white -> D
# - yellow -> U
# - green -> F
# - blue -> B
# - red -> R
# - orange -> L
#
# Move notation between working CFOP algorithms and project-global notation is
# therefore a simple U<->D swap:
# - working U  == global D
# - working D  == global U
# - working R/F/L/B stay the same

WORKING_FACE_SWAP = {
    "U": "D",
    "D": "U",
}

WORKING_MOVE_FACE_SWAP = {
    "U": "D",
    "D": "U",
    "R": "R",
    "L": "L",
    "F": "F",
    "B": "B",
}

# In the white-bottom working view, the yellow top layer corresponds to the
# scanner's global D layer.
WORKING_TOP_CORNER_POSITIONS = {4, 5, 6, 7}
WORKING_TOP_EDGE_POSITIONS = {4, 5, 6, 7}

# Solved white-bottom F2L slots correspond to the global white-face corners
# plus the middle-layer edges.
WHITE_F2L_CORNER_POSITIONS = {0, 1, 2, 3}
WHITE_F2L_EDGE_POSITIONS = {8, 9, 10, 11}

# White cross targets expressed in global coordinates.
#
# working DF -> global UF
# working DR -> global UR
# working DB -> global UB
# working DL -> global UL
CROSS_TARGETS = [
    ("DF", 1, 1),
    ("DR", 0, 0),
    ("DB", 3, 3),
    ("DL", 2, 2),
]

F2L_SLOT_ORDER = ["FR", "FL", "BL", "BR"]
F2L_SLOT_TARGETS = {
    "FR": {
        "corner_index": 0,   # global URF cubie
        "corner_position": 0,
        "edge_index": 8,
        "edge_position": 8,
    },
    "FL": {
        "corner_index": 1,   # global UFL cubie
        "corner_position": 1,
        "edge_index": 9,
        "edge_position": 9,
    },
    "BL": {
        "corner_index": 2,   # global ULB cubie
        "corner_position": 2,
        "edge_index": 10,
        "edge_position": 10,
    },
    "BR": {
        "corner_index": 3,   # global UBR cubie
        "corner_position": 3,
        "edge_index": 11,
        "edge_position": 11,
    },
}

# Practical first-pass adjacency detector for pair-on-top states.
# In working CFOP terms the top layer is yellow, which is the scanner's global
# D layer. The map below is therefore written in global D-layer positions.
TOP_CORNER_TO_ADJACENT_TOP_EDGES = {
    4: {4, 5},   # DFR touches DR and DF
    5: {5, 6},   # DLF touches DF and DL
    6: {6, 7},   # DBL touches DL and DB
    7: {4, 7},   # DRB touches DR and DB
}


@dataclass
class CrossState:
    solved: bool
    solved_count: int
    solved_edges: list[str]
    unsolved_edges: list[str]


@dataclass
class F2LPairState:
    slot: str
    target_corner: str
    target_edge: str
    corner_position: str
    edge_position: str
    corner_oriented: bool
    edge_oriented: bool
    paired: bool
    inserted: bool
    solved: bool
    pair_on_top: bool
    corner_in_top: bool
    edge_in_top: bool
    case_hint: str


@dataclass
class CFOPAnalysis:
    cross: CrossState
    f2l_pairs: list[F2LPairState]
    f2l_slots_solved: int
    oll_solved: bool
    pll_solved: bool
    fully_solved: bool
    warnings: list[str]


def to_cfop_working_facelets(facelets: str) -> str:
    """Swap white/yellow face roles for debug and tests."""
    return "".join(WORKING_FACE_SWAP.get(facelet, facelet) for facelet in facelets)


def from_cfop_working_facelets(facelets: str) -> str:
    return to_cfop_working_facelets(facelets)


def to_cfop_working_cube(cube: CubieCube) -> CubieCube:
    """
    Return the facelet-role-swapped view of the cube.

    This is useful for testing/documentation. The actual stage predicates still
    run in explicit global coordinates, because CubieCube piece labels are tied
    to the scanner's original color conventions.
    """
    return CubieCube.from_facelet_string(to_cfop_working_facelets(cube.to_facelet_string()))


def to_cfop_human_orientation(cube: CubieCube) -> CubieCube:
    return to_cfop_working_cube(cube)


def from_cfop_human_moves(moves: list[str]) -> list[str]:
    return from_cfop_working_moves(moves)


def get_human_orientation_setup_text() -> str:
    return "Hold the cube with WHITE on bottom and GREEN facing you."


def map_move_between_global_and_working(move: str) -> str:
    normalized = normalize_move_token(move)
    return WORKING_MOVE_FACE_SWAP[normalized[0]] + normalized[1:]


def from_cfop_working_moves(moves: list[str]) -> list[str]:
    return [map_move_between_global_and_working(move) for move in moves]


def to_white_cross_working_facelets(facelets: str) -> str:
    return to_cfop_working_facelets(facelets)


def from_white_cross_working_facelets(facelets: str) -> str:
    return from_cfop_working_facelets(facelets)


def to_white_cross_working_cube(cube: CubieCube) -> CubieCube:
    return to_cfop_working_cube(cube)


def from_white_cross_working_moves(moves: list[str]) -> list[str]:
    return from_cfop_working_moves(moves)


def corner_name(index: int) -> str:
    return CORNER_NAMES[index]


def edge_name(index: int) -> str:
    return EDGE_NAMES[index]


def find_corner_position(cube: CubieCube, target_corner_index: int) -> int:
    return cube.corner_perm.index(target_corner_index)


def find_edge_position(cube: CubieCube, target_edge_index: int) -> int:
    return cube.edge_perm.index(target_edge_index)


def is_cross_edge_solved(cube: CubieCube, target_edge_index: int) -> bool:
    target_position = next(
        position_index
        for _, edge_index, position_index in CROSS_TARGETS
        if edge_index == target_edge_index
    )
    return cube.edge_perm[target_position] == target_edge_index and cube.edge_ori[target_position] == 0


def is_f2l_slot_solved(cube: CubieCube, slot: str) -> bool:
    slot_info = F2L_SLOT_TARGETS[slot]
    return (
        cube.corner_perm[slot_info["corner_position"]] == slot_info["corner_index"]
        and cube.corner_ori[slot_info["corner_position"]] == 0
        and cube.edge_perm[slot_info["edge_position"]] == slot_info["edge_index"]
        and cube.edge_ori[slot_info["edge_position"]] == 0
    )


def analyze_cross(cube: CubieCube) -> CrossState:
    solved_edges: list[str] = []
    unsolved_edges: list[str] = []

    for edge_label, target_edge_index, _ in CROSS_TARGETS:
        if is_cross_edge_solved(cube, target_edge_index):
            solved_edges.append(edge_label)
        else:
            unsolved_edges.append(edge_label)

    return CrossState(
        solved=len(unsolved_edges) == 0,
        solved_count=len(solved_edges),
        solved_edges=solved_edges,
        unsolved_edges=unsolved_edges,
    )


def analyze_f2l_pairs(cube: CubieCube) -> list[F2LPairState]:
    pair_states: list[F2LPairState] = []

    for slot in F2L_SLOT_ORDER:
        slot_info = F2L_SLOT_TARGETS[slot]
        corner_index = slot_info["corner_index"]
        edge_index = slot_info["edge_index"]

        corner_position_index = find_corner_position(cube, corner_index)
        edge_position_index = find_edge_position(cube, edge_index)

        corner_oriented = cube.corner_ori[corner_position_index] == 0
        edge_oriented = cube.edge_ori[edge_position_index] == 0
        solved = is_f2l_slot_solved(cube, slot)
        corner_in_top = corner_position_index in WORKING_TOP_CORNER_POSITIONS
        edge_in_top = edge_position_index in WORKING_TOP_EDGE_POSITIONS
        pair_on_top = corner_in_top and edge_in_top
        inserted = (
            corner_position_index in WHITE_F2L_CORNER_POSITIONS
            and edge_position_index in WHITE_F2L_EDGE_POSITIONS
        )
        paired = _is_pair_paired(
            slot,
            corner_position_index,
            edge_position_index,
            solved,
            pair_on_top,
        )

        pair_states.append(
            F2LPairState(
                slot=slot,
                target_corner=corner_name(corner_index),
                target_edge=edge_name(edge_index),
                corner_position=corner_name(corner_position_index),
                edge_position=edge_name(edge_position_index),
                corner_oriented=corner_oriented,
                edge_oriented=edge_oriented,
                paired=paired,
                inserted=inserted,
                solved=solved,
                pair_on_top=pair_on_top,
                corner_in_top=corner_in_top,
                edge_in_top=edge_in_top,
                case_hint=_basic_f2l_case_hint(
                    solved=solved,
                    paired=paired,
                    pair_on_top=pair_on_top,
                    corner_in_top=corner_in_top,
                    edge_in_top=edge_in_top,
                    inserted=inserted,
                ),
            )
        )

    return pair_states


def is_oll_solved(cube: CubieCube) -> bool:
    facelets = cube.to_facelet_string()
    return all(facelet == "D" for facelet in facelets[27:36])


def is_pll_solved(cube: CubieCube) -> bool:
    return is_cube_solved(cube)


def is_cube_solved(cube: CubieCube) -> bool:
    return cube.to_facelet_string() == SOLVED_FACELETS


def analyze_cfop(cube: CubieCube) -> CFOPAnalysis:
    cross = analyze_cross(cube)
    f2l_pairs = analyze_f2l_pairs(cube)
    f2l_slots_solved = sum(1 for pair_state in f2l_pairs if pair_state.solved)
    oll_solved = is_oll_solved(cube)
    pll_solved = is_pll_solved(cube)
    fully_solved = is_cube_solved(cube)

    warnings: list[str] = []
    return CFOPAnalysis(
        cross=cross,
        f2l_pairs=f2l_pairs,
        f2l_slots_solved=f2l_slots_solved,
        oll_solved=oll_solved,
        pll_solved=pll_solved,
        fully_solved=fully_solved,
        warnings=warnings,
    )


def _is_pair_paired(
    slot: str,
    corner_position_index: int,
    edge_position_index: int,
    solved: bool,
    pair_on_top: bool,
) -> bool:
    if solved:
        return True

    slot_info = F2L_SLOT_TARGETS[slot]
    if (
        corner_position_index == slot_info["corner_position"]
        and edge_position_index == slot_info["edge_position"]
    ):
        return True

    if pair_on_top:
        return edge_position_index in TOP_CORNER_TO_ADJACENT_TOP_EDGES[corner_position_index]

    return False


def _basic_f2l_case_hint(
    solved: bool,
    paired: bool,
    pair_on_top: bool,
    corner_in_top: bool,
    edge_in_top: bool,
    inserted: bool,
) -> str:
    if solved:
        return "SOLVED"
    if paired and pair_on_top:
        return "PAIRED_TOP"
    if corner_in_top and edge_in_top and not paired:
        return "SEPARATE_TOP"
    if corner_in_top and not edge_in_top:
        return "CORNER_TOP_EDGE_MIDDLE"
    if not corner_in_top and edge_in_top:
        return "EDGE_TOP_CORNER_SLOT"
    if inserted:
        return "BOTH_INSERTED_WRONG"
    return "BURIED_OR_COMPLEX"
