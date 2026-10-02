from __future__ import annotations

from dataclasses import dataclass

from .cfop_analyzer import F2L_SLOT_ORDER, from_cfop_working_moves, is_f2l_slot_solved, is_oll_solved
from .cubie_model import CubieCube
from .move_simplifier import simplify_moves
from .move_utils import invert_alg, join_alg, normalize_move_token, parse_alg


@dataclass
class OLLAlgorithm:
    case_id: str
    name: str
    pattern_key: str
    moves: list[str]


_OLL_ALGORITHMS: dict[str, OLLAlgorithm] = {}


def is_oll_stage_ready(cube: CubieCube) -> bool:
    return all(is_f2l_slot_solved(cube, slot) for slot in F2L_SLOT_ORDER)


def oll_pattern_key(cube: CubieCube) -> str:
    facelets = cube.to_facelet_string()
    d_face = "".join("1" if facelet == "D" else "0" for facelet in facelets[27:36])
    side_strip_indices = [24, 25, 26, 15, 16, 17, 51, 52, 53, 42, 43, 44]
    side_strip = "".join("1" if facelets[index] == "D" else "0" for index in side_strip_indices)
    return f"{d_face}|{side_strip}"


def recognize_oll(cube: CubieCube) -> tuple[str, int]:
    if is_oll_solved(cube):
        return "SOLVED", 0

    for turns, working_auf in enumerate(_working_u_aufs()):
        probe = cube.copy()
        if working_auf:
            probe.apply_alg(from_cfop_working_moves(working_auf))

        if is_oll_solved(probe):
            return "SOLVED", turns

        pattern_key = oll_pattern_key(probe)
        for case_id, algorithm in _OLL_ALGORITHMS.items():
            if algorithm.pattern_key == pattern_key:
                return case_id, turns

    return "UNSUPPORTED", 0


def get_oll_algorithm(case_id: str) -> OLLAlgorithm | None:
    return _OLL_ALGORITHMS.get(case_id)


def solve_oll(cube: CubieCube):
    from .cfop_solver import CFOPStageResult

    before_facelets = cube.to_facelet_string()
    if not is_oll_stage_ready(cube):
        return CFOPStageResult(
            name="Yellow OLL",
            slot=None,
            case_id=None,
            description="OLL can only run after White Cross and all four F2L slots are solved.",
            instruction_lines=["Finish all four F2L slots before starting Yellow OLL."],
            moves=[],
            move_string="",
            cube_facelets_before=before_facelets,
            cube_facelets_after=before_facelets,
            success=False,
            error="Yellow OLL stage was requested before F2L was complete.",
        )

    case_id, pre_auf_turns = recognize_oll(cube)
    if case_id == "SOLVED":
        return CFOPStageResult(
            name="Yellow OLL",
            slot=None,
            case_id="SOLVED",
            description="Yellow OLL is already solved.",
            instruction_lines=["Yellow OLL already solved."],
            moves=[],
            move_string="",
            cube_facelets_before=before_facelets,
            cube_facelets_after=before_facelets,
            success=True,
            error=None,
        )

    algorithm = get_oll_algorithm(case_id)
    if algorithm is None:
        return CFOPStageResult(
            name="Yellow OLL",
            slot=None,
            case_id="UNSUPPORTED",
            description=f"OLL case is not implemented yet. Pattern key: {oll_pattern_key(cube)}",
            instruction_lines=[f"Unsupported Yellow OLL case: {case_id}"],
            moves=[],
            move_string="",
            cube_facelets_before=before_facelets,
            cube_facelets_after=before_facelets,
            success=False,
            error="Unsupported Yellow OLL case.",
        )

    display_moves = simplify_moves(algorithm.moves[:])
    algorithm_moves = _compile_human_last_layer_moves_to_global(algorithm.moves)
    moves = simplify_moves(_working_auf_moves(pre_auf_turns) + algorithm_moves)
    cube.apply_alg(moves)

    if not is_oll_solved(cube) or not is_oll_stage_ready(cube):
        return CFOPStageResult(
            name="Yellow OLL",
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
            error="Yellow OLL verification failed after applying the algorithm.",
        )

    return CFOPStageResult(
        name="Yellow OLL",
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


def _register_oll_algorithms() -> None:
    base_algorithms = [
        OLLAlgorithm("OLL_1", "Dot 1", "", parse_alg("R U2 R2 F R F' U2 R' F R F'")),
        OLLAlgorithm("OLL_2", "Dot 2", "", parse_alg("r U r' U2 r U2 R' U2 R U' r'")),
        OLLAlgorithm("OLL_3", "Dot 3", "", parse_alg("r' R2 U R' U r U2 r' U M'")),
        OLLAlgorithm("OLL_4", "Dot 4", "", parse_alg("M U' r U2 r' U' R U' R' M'")),
        OLLAlgorithm("OLL_5", "Square Shape 5", "", parse_alg("l' U2 L U L' U l")),
        OLLAlgorithm("OLL_6", "Square Shape 6", "", parse_alg("r U2 R' U' R U' r'")),
        OLLAlgorithm("OLL_7", "Small Lightning Bolt 7", "", parse_alg("r U R' U R U2 r'")),
        OLLAlgorithm("OLL_8", "Small Lightning Bolt 8", "", parse_alg("l' U' L U' L' U2 l")),
        OLLAlgorithm("OLL_9", "Fish Shape 9", "", parse_alg("R U R' U' R' F R2 U R' U' F'")),
        OLLAlgorithm("OLL_10", "Fish Shape 10", "", parse_alg("R U R' U R' F R F' R U2 R'")),
        OLLAlgorithm("OLL_11", "Small Lightning Bolt 11", "", parse_alg("r U R' U R' F R F' R U2 r'")),
        OLLAlgorithm("OLL_12", "Small Lightning Bolt 12", "", parse_alg("M' R' U' R U' R' U2 R U' R r'")),
        OLLAlgorithm("OLL_13", "Knight Move Shape 13", "", parse_alg("F U R U' R2 F' R U R U' R'")),
        OLLAlgorithm("OLL_14", "Knight Move Shape 14", "", parse_alg("R' F R U R' F' R F U' F'")),
        OLLAlgorithm("OLL_15", "Knight Move Shape 15", "", parse_alg("l' U' l U' L' U L U' l' U l")),
        OLLAlgorithm("OLL_16", "Knight Move Shape 16", "", parse_alg("r U R' U R U' r' U' R U' R'")),
        OLLAlgorithm("OLL_17", "Dot 17", "", parse_alg("F R' F' R2 r' U R U' R' U' M'")),
        OLLAlgorithm("OLL_18", "Dot 18", "", parse_alg("r U R' U R U2 r2 U' R U' R' U2 r")),
        OLLAlgorithm("OLL_19", "Dot 19", "", parse_alg("r' R U R U R' U' M' R' F R F'")),
        OLLAlgorithm("OLL_20", "Dot 20", "", parse_alg("r U R' U' M2 U R U' R' U' M'")),
        OLLAlgorithm("OLL_21", "Cross 21", "", parse_alg("R U2 R' U' R U R' U' R U' R'")),
        OLLAlgorithm("OLL_22", "Cross 22", "", parse_alg("R U2 R2 U' R2 U' R2 U2 R")),
        OLLAlgorithm("OLL_23", "Cross 23", "", parse_alg("R2 D' R U2 R' D R U2 R")),
        OLLAlgorithm("OLL_24", "Cross 24", "", parse_alg("r U R' U' r' F R F'")),
        OLLAlgorithm("OLL_25", "Cross 25", "", parse_alg("F' r U R' U' r' F R")),
        OLLAlgorithm("OLL_26", "Cross 26", "", parse_alg("R U2 R' U' R U' R'")),
        OLLAlgorithm("OLL_27", "Cross 27", "", parse_alg("R U R' U R U2 R'")),
        OLLAlgorithm("OLL_28", "Corners Oriented 28", "", parse_alg("r U R' U' M U R U' R'")),
        OLLAlgorithm("OLL_29", "Awkward Shape 29", "", parse_alg("R U R' U' R U' R' F' U' F R U R'")),
        OLLAlgorithm("OLL_30", "Awkward Shape 30", "", parse_alg("F R' F R2 U' R' U' R U R' F2")),
        OLLAlgorithm("OLL_31", "P Shape 31", "", parse_alg("R' U' F U R U' R' F' R")),
        OLLAlgorithm("OLL_32", "P Shape 32", "", parse_alg("L U F' U' L' U L F L'")),
        OLLAlgorithm("OLL_33", "T Shape 33", "", parse_alg("R U R' U' R' F R F'")),
        OLLAlgorithm("OLL_34", "C Shape 34", "", parse_alg("R U R2 U' R' F R U R U' F'")),
        OLLAlgorithm("OLL_35", "Fish Shape 35", "", parse_alg("R U2 R2 F R F' R U2 R'")),
        OLLAlgorithm("OLL_36", "W Shape 36", "", parse_alg("L' U' L U' L' U L U L F' L' F")),
        OLLAlgorithm("OLL_37", "Fish Shape 37", "", parse_alg("F R' F' R U R U' R'")),
        OLLAlgorithm("OLL_38", "W Shape 38", "", parse_alg("R U R' U R U' R' U' R' F R F'")),
        OLLAlgorithm("OLL_39", "Big Lightning Bolt 39", "", parse_alg("L F' L' U' L U F U' L'")),
        OLLAlgorithm("OLL_40", "Big Lightning Bolt 40", "", parse_alg("R' F R U R' U' F' U R")),
        OLLAlgorithm("OLL_41", "Awkward Shape 41", "", parse_alg("R U R' U R U2 R' F R U R' U' F'")),
        OLLAlgorithm("OLL_42", "Awkward Shape 42", "", parse_alg("R' U' R U' R' U2 R F R U R' U' F'")),
        OLLAlgorithm("OLL_43", "P Shape 43", "", parse_alg("F' U' L' U L F")),
        OLLAlgorithm("OLL_44", "P Shape 44", "", parse_alg("F U R U' R' F'")),
        OLLAlgorithm("OLL_45", "T Shape 45", "", parse_alg("F R U R' U' F'")),
        OLLAlgorithm("OLL_46", "C Shape 46", "", parse_alg("R' U' R' F R F' U R")),
        OLLAlgorithm("OLL_47", "Small L Shape 47", "", parse_alg("R' U' R' F R F' R' F R F' U R")),
        OLLAlgorithm("OLL_48", "Small L Shape 48", "", parse_alg("F R U R' U' R U R' U' F'")),
        OLLAlgorithm("OLL_49", "Small L Shape 49", "", parse_alg("r U' r2 U r2 U r2 U' r")),
        OLLAlgorithm("OLL_50", "Small L Shape 50", "", parse_alg("r' U r2 U' r2 U' r2 U r'")),
        OLLAlgorithm("OLL_51", "I Shape 51", "", parse_alg("F U R U' R' U R U' R' F'")),
        OLLAlgorithm("OLL_52", "I Shape 52", "", parse_alg("R U R' U R U' B U' B' R'")),
        OLLAlgorithm("OLL_53", "Small L Shape 53", "", parse_alg("l' U2 L U L' U' L U L' U l")),
        OLLAlgorithm("OLL_54", "Small L Shape 54", "", parse_alg("r U2 R' U' R U' R' U R U' r'")),
        OLLAlgorithm("OLL_55", "I Shape 55", "", parse_alg("R' F R U R U' R2 F' R2 U' R' U R U R'")),
        OLLAlgorithm("OLL_56", "I Shape 56", "", parse_alg("r' U' R U' R' U R U' R' U2 r")),
        OLLAlgorithm("OLL_57", "Corners Oriented 57", "", parse_alg("R U R' U' M' U R U' r'")),
        OLLAlgorithm("SUNE", "Sune", "", parse_alg("R U R' U R U2 R'")),
        OLLAlgorithm("ANTI_SUNE", "Anti-Sune", "", parse_alg("R U2 R' U' R U' R'")),
    ]

    for algorithm in base_algorithms:
        probe = CubieCube.solved()
        inverse_moves = invert_alg(_compile_human_last_layer_moves_to_global(algorithm.moves))
        probe.apply_alg(inverse_moves)
        algorithm.pattern_key = oll_pattern_key(probe)
        _OLL_ALGORITHMS[algorithm.case_id] = algorithm


_register_oll_algorithms()
