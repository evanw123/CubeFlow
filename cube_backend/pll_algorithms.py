from __future__ import annotations

from dataclasses import dataclass

from .cfop_analyzer import F2L_SLOT_ORDER, from_cfop_working_moves, is_cube_solved, is_f2l_slot_solved, is_oll_solved
from .cubie_model import CubieCube
from .move_simplifier import simplify_moves
from .move_utils import invert_alg, join_alg, normalize_move_token, parse_alg


@dataclass
class PLLAlgorithm:
    case_id: str
    name: str
    pattern_key: str
    moves: list[str]


_PLL_ALGORITHMS: dict[str, PLLAlgorithm] = {}


def is_pll_stage_ready(cube: CubieCube) -> bool:
    return is_oll_solved(cube) and all(is_f2l_slot_solved(cube, slot) for slot in F2L_SLOT_ORDER)


def is_pll_solved(cube: CubieCube) -> bool:
    return is_cube_solved(cube)


def pll_pattern_key(cube: CubieCube) -> str:
    facelets = cube.to_facelet_string()
    side_strip_indices = [24, 25, 26, 15, 16, 17, 51, 52, 53, 42, 43, 44]
    return "".join(facelets[index] for index in side_strip_indices)


def recognize_pll(cube: CubieCube) -> tuple[str, int]:
    if is_cube_solved(cube):
        return "SOLVED", 0

    if not is_oll_solved(cube):
        return "UNSUPPORTED", 0

    for turns, working_auf in enumerate(_working_u_aufs()):
        probe = cube.copy()
        if working_auf:
            probe.apply_alg(from_cfop_working_moves(working_auf))

        if is_cube_solved(probe):
            return "SOLVED", turns

        pattern_key = pll_pattern_key(probe)
        for case_id, algorithm in _PLL_ALGORITHMS.items():
            if algorithm.pattern_key == pattern_key:
                return case_id, turns

    return "UNSUPPORTED", 0


def get_pll_algorithm(case_id: str) -> PLLAlgorithm | None:
    return _PLL_ALGORITHMS.get(case_id)


def solve_pll(cube: CubieCube):
    from .cfop_solver import CFOPStageResult

    before_facelets = cube.to_facelet_string()
    if not is_pll_stage_ready(cube):
        return CFOPStageResult(
            name="Yellow PLL",
            slot=None,
            case_id=None,
            description="PLL can only run after White Cross, all F2L slots, and Yellow OLL are solved.",
            instruction_lines=["Finish Yellow OLL before starting Yellow PLL."],
            moves=[],
            move_string="",
            cube_facelets_before=before_facelets,
            cube_facelets_after=before_facelets,
            success=False,
            error="Yellow PLL stage was requested before Yellow OLL was complete.",
        )

    case_id, pre_auf_turns = recognize_pll(cube)
    if case_id == "SOLVED":
        return CFOPStageResult(
            name="Yellow PLL",
            slot=None,
            case_id="SOLVED",
            description="Yellow PLL is already solved or only needs final AUF.",
            instruction_lines=["Yellow PLL already solved or only needs AUF."],
            moves=[],
            move_string="",
            cube_facelets_before=before_facelets,
            cube_facelets_after=before_facelets,
            success=True,
            error=None,
        )

    algorithm = get_pll_algorithm(case_id)
    if algorithm is None:
        return CFOPStageResult(
            name="Yellow PLL",
            slot=None,
            case_id="UNSUPPORTED",
            description=f"PLL case is not implemented yet. Pattern key: {pll_pattern_key(cube)}",
            instruction_lines=[f"Unsupported Yellow PLL case: {case_id}"],
            moves=[],
            move_string="",
            cube_facelets_before=before_facelets,
            cube_facelets_after=before_facelets,
            success=False,
            error="Unsupported Yellow PLL case.",
        )

    display_moves = simplify_moves(algorithm.moves[:])
    algorithm_moves = _compile_human_last_layer_moves_to_global(algorithm.moves)
    moves = simplify_moves(_working_auf_moves(pre_auf_turns) + algorithm_moves)
    cube.apply_alg(moves)

    if not is_oll_solved(cube) or not all(is_f2l_slot_solved(cube, slot) for slot in F2L_SLOT_ORDER):
        return CFOPStageResult(
            name="Yellow PLL",
            slot=None,
            case_id=case_id,
            description=f"{algorithm.name} failed verification.",
            algorithm_moves=moves[:],
            display_moves=display_moves[:],
            instruction_lines=[f"alg: {join_alg(display_moves)}"],
            moves=moves,
            move_string=join_alg(display_moves),
            cube_facelets_before=before_facelets,
            cube_facelets_after=cube.to_facelet_string(),
            success=False,
            error="Yellow PLL verification failed after applying the algorithm.",
        )

    return CFOPStageResult(
        name="Yellow PLL",
        slot=None,
        case_id=case_id,
        description=algorithm.name,
        algorithm_moves=moves[:],
        display_moves=display_moves[:],
        instruction_lines=[f"alg: {join_alg(display_moves)}"],
        moves=moves,
        move_string=join_alg(display_moves),
        cube_facelets_before=before_facelets,
        cube_facelets_after=cube.to_facelet_string(),
        success=True,
        error=None,
    )


def apply_final_auf_if_needed(cube: CubieCube) -> list[str]:
    if is_cube_solved(cube):
        return []

    for working_auf in _working_u_aufs()[1:]:
        probe = cube.copy()
        probe.apply_alg(from_cfop_working_moves(working_auf))
        if is_cube_solved(probe):
            moves = from_cfop_working_moves(working_auf)
            simplified = simplify_moves(moves)
            cube.apply_alg(simplified)
            return simplified

    return []


def _working_u_aufs() -> list[list[str]]:
    return [
        [],
        ["U"],
        ["U2"],
        ["U'"],
    ]


def _working_auf_moves(turns: int) -> list[str]:
    return from_cfop_working_moves(_working_u_aufs()[turns])


def _compose_suffix(base_move: str, suffix: str) -> str:
    normalized = normalize_move_token(base_move)
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


def _map_human_last_layer_move_to_global(move: str) -> str:
    normalized = normalize_move_token(move)
    face = normalized[0]
    suffix = normalized[1:]
    face_map = {
        "U": "D",
        "D": "U",
        "R": "R",
        "L": "L",
        "F": "B",
        "B": "F",
        "u": "d",
        "d": "u",
        "r": "r",
        "l": "l",
        "f": "b",
        "b": "f",
        "M": "M",
        "E": "E'",
        "S": "S'",
        "x": "x",
        "y": "y'",
        "z": "z'",
    }
    return _compose_suffix(face_map[face], suffix)


def _map_human_last_layer_moves_to_global(moves: list[str]) -> list[str]:
    return [_map_human_last_layer_move_to_global(move) for move in moves]


def _compile_human_last_layer_moves_to_global(moves: list[str]) -> list[str]:
    mapped_moves = _map_human_last_layer_moves_to_global(moves)
    net_rotations = [move for move in mapped_moves if move[0] in {"x", "y", "z"}]
    return simplify_moves(mapped_moves + invert_alg(net_rotations))


def _register_pll_algorithms() -> None:
    base_algorithms = [
        PLLAlgorithm("Aa", "Aa Perm", "", parse_alg("x L2 D2 L' U' L D2 L' U L'")),
        PLLAlgorithm("Ab", "Ab Perm", "", parse_alg("x' L2 D2 L U L' D2 L U' L")),
        PLLAlgorithm("F", "F Perm", "", parse_alg("R' U' F' R U R' U' R' F R2 U' R' U' R U R' U R")),
        PLLAlgorithm("Ga", "Ga Perm", "", parse_alg("R2 U R' U R' U' R U' R2 D U' R' U R D'")),
        PLLAlgorithm("Gb", "Gb Perm", "", parse_alg("R' U' R U D' R2 U R' U R U' R U' R2 D")),
        PLLAlgorithm("Gc", "Gc Perm", "", parse_alg("R2 U' R U' R U R' U R2 D' U R U' R' D")),
        PLLAlgorithm("Gd", "Gd Perm", "", parse_alg("R U R' U' D R2 U' R U' R' U R' U R2 D'")),
        PLLAlgorithm("Ja", "Ja Perm", "", parse_alg("L' U' L F L' U' L U L F' L2 U L U")),
        PLLAlgorithm("Jb", "Jb Perm", "", parse_alg("R U R' F' R U R' U' R' F R2 U' R' U'")),
        PLLAlgorithm("Ra", "Ra Perm", "", parse_alg("R U' R' U' R U R D R' U' R D' R' U2 R'")),
        PLLAlgorithm("Rb", "Rb Perm", "", parse_alg("R2 F R U R U' R' F' R U2 R' U2 R")),
        PLLAlgorithm("T", "T Perm", "", parse_alg("R U R' U' R' F R2 U' R' U' R U R' F'")),
        PLLAlgorithm("E", "E Perm", "", parse_alg("x' L' U L D' L' U' L D L' U' L D' L' U L D")),
        PLLAlgorithm("Na", "Na Perm", "", parse_alg("L U' R U2 L' U R' L U' R U2 L' U R'")),
        PLLAlgorithm("Nb", "Nb Perm", "", parse_alg("R' U R U' R' F' U' F R U R' F R' F' R U' R")),
        PLLAlgorithm("V", "V Perm", "", parse_alg("R' U R' U' y R' F' R2 U' R' U R' F R F")),
        PLLAlgorithm("Y", "Y Perm", "", parse_alg("F R U' R' U' R U R' F' R U R' U' R' F R F'")),
        PLLAlgorithm("H", "H Perm", "", parse_alg("M2 U M2 U2 M2 U M2")),
        PLLAlgorithm("Ua", "Ua Perm", "", parse_alg("M2 U M U2 M' U M2")),
        PLLAlgorithm("Ub", "Ub Perm", "", parse_alg("M2 U' M U2 M' U' M2")),
        PLLAlgorithm("Z", "Z Perm", "", parse_alg("M' U M2 U M2 U M' U2 M2")),
    ]

    for algorithm in base_algorithms:
        probe = CubieCube.solved()
        inverse_moves = invert_alg(_compile_human_last_layer_moves_to_global(algorithm.moves))
        probe.apply_alg(inverse_moves)
        algorithm.pattern_key = pll_pattern_key(probe)
        _PLL_ALGORITHMS[algorithm.case_id] = algorithm


_register_pll_algorithms()
