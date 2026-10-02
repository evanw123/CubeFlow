from __future__ import annotations

from importlib import import_module

from .cfop_analyzer import get_human_orientation_setup_text, is_cube_solved
from .cfop_models import CFOPSolveResult, CFOPStageResult
from .cfop_segmenter import CFOPSegmentation, segment_cfop_solution
from .cubie_model import CubieCube
from .move_simplifier import simplify_moves
from .move_utils import join_alg, normalize_move_token
from .validator import validate_cube_state, validate_facelet_string
from .viewer_orientation import CANONICAL_VIEWER_ORIENTATION, map_internal_moves_to_viewer

PROJECT_TO_PYCUBE_COLOR = {
    "U": "W",
    "R": "R",
    "F": "G",
    "D": "Y",
    "L": "O",
    "B": "B",
}

PROJECT_FACE_BLOCKS = {
    "U": (0, 9),
    "R": (9, 18),
    "F": (18, 27),
    "D": (27, 36),
    "L": (36, 45),
    "B": (45, 54),
}

PYCUBE_FACE_SEQUENCE = ["F", "L", "B", "R", "U", "D"]
PYCUBE_FACE_ROTATE_180 = {"F", "L", "B", "R", "U", "D"}

PYCUBE_BASE_MAP = {
    "U": "D",
    "D": "U",
    "R": "L",
    "L": "R",
    "F": "F",
    "B": "B",
    "M": "M",
    "E": "E",
    "S": "S",
    "x": "x",
    "y": "y",
    "z": "z",
    "r": "l",
    "l": "r",
    "u": "d",
    "d": "u",
    "f": "f",
    "b": "b",
}

PYCUBE_DIRECTION_FLIP = {"M", "E", "x", "y"}

STAGE_LABEL_TO_ID = {
    "Alignment": "cross",
    "Cross": "cross",
    "F2L": "f2l",
    "OLL": "oll",
    "PLL": "pll",
}

STAGE_DESCRIPTIONS = {
    "cross": "PyCube-Solver aligned the cube and solved the white cross.",
    "f2l": "PyCube-Solver solved the first two layers.",
    "oll": "PyCube-Solver oriented the yellow last layer.",
    "pll": "PyCube-Solver permuted the last layer and completed AUF.",
}


def pycube_available() -> bool:
    try:
        _load_pycube_modules()
    except Exception:
        return False
    return True


def facelets_to_pycube_faces(facelets: str) -> list[list[list[str]]]:
    validation = validate_facelet_string(facelets)
    if not validation.is_valid:
        raise ValueError("; ".join(validation.errors))

    faces: list[list[list[str]]] = []
    for project_face in PYCUBE_FACE_SEQUENCE:
        start, end = PROJECT_FACE_BLOCKS[project_face]
        block = facelets[start:end]
        rows = [
            [PROJECT_TO_PYCUBE_COLOR[sticker] for sticker in block[row_start:row_start + 3]]
            for row_start in range(0, 9, 3)
        ]
        if project_face in PYCUBE_FACE_ROTATE_180:
            rows = [list(reversed(row)) for row in reversed(rows)]
        faces.append(rows)
    return faces


def solve_cfop_with_pycube(facelets: str) -> CFOPSolveResult:
    setup_text = get_human_orientation_setup_text()
    validation = validate_facelet_string(facelets)
    if not validation.is_valid:
        return _failed_result(
            error="Deep validation failed: " + "; ".join(validation.errors),
            setup_text=setup_text,
            final_facelets=facelets,
        )

    try:
        PyCubeCube, PyCubeSolver, parse_formula = _load_pycube_modules()
    except Exception as exc:
        return _failed_result(
            error=f"PyCube-Solver is unavailable: {exc}",
            setup_text=setup_text,
            final_facelets=facelets,
        )

    base_cube = CubieCube.from_facelet_string(facelets)

    try:
        pycube_cube = PyCubeCube(faces=facelets_to_pycube_faces(facelets))
        pycube_solver = PyCubeSolver(pycube_cube)
        pycube_solver.solveCube(optimize=True)
        decorated_output = pycube_solver.getMoves(decorated=True)
        raw_output = pycube_solver.getMoves()
    except Exception as exc:
        return _failed_result(
            error=f"PyCube-Solver execution failed: {exc}",
            setup_text=setup_text,
            final_facelets=facelets,
        )

    stages, full_moves, segmentation = _build_stage_results(
        facelets,
        decorated_output,
        raw_output,
        parse_formula,
    )

    solved_cube = base_cube.copy()
    if full_moves:
        solved_cube.apply_alg(full_moves)

    if not pycube_solver.isSolved() or not is_cube_solved(solved_cube):
        error = "PyCube-Solver could not fully solve this cube yet. Try Standard Solve instead."
        return _failed_result(
            error=error,
            setup_text=setup_text,
            final_facelets=solved_cube.to_facelet_string(),
            stages=stages,
        )

    stage_lookup = {stage.name: stage for stage in stages}
    cross_stage = stage_lookup.get("White Cross")
    f2l_stage = stage_lookup.get("F2L")
    oll_stage = stage_lookup.get("OLL")
    pll_stage = stage_lookup.get("PLL")
    display_moves = map_internal_moves_to_viewer(full_moves)

    return CFOPSolveResult(
        success=True,
        error=None,
        failing_stage=None,
        failing_slot=None,
        failing_case_id=None,
        setup_text=setup_text,
        stages=stages,
        cross_moves=[] if cross_stage is None else cross_stage.moves[:],
        f2l_slot_results=[] if f2l_stage is None else [f2l_stage],
        oll_result=oll_stage,
        pll_result=pll_stage,
        auf_moves=[],
        full_moves=full_moves,
        full_move_string=join_alg(full_moves),
        final_facelets=solved_cube.to_facelet_string(),
        orientation=CANONICAL_VIEWER_ORIENTATION.copy(),
        display_moves=display_moves,
        display_move_string=join_alg(display_moves),
        segmentation_source=segmentation.source,
        segmentation_verified=segmentation.verified,
        segmentation_warning=segmentation.warning,
    )


def solve_cfop_with_pycube_state(cube_state) -> CFOPSolveResult:
    setup_text = get_human_orientation_setup_text()
    validation = validate_cube_state(cube_state)
    if not validation.is_valid:
        return _failed_result(
            error="Deep validation failed: " + "; ".join(validation.errors),
            setup_text=setup_text,
            final_facelets=validation.facelets,
        )

    return solve_cfop_with_pycube(validation.facelets)


def _load_pycube_modules():
    cube_module = import_module("third_party.pycube_solver.cube")
    solver_module = import_module("third_party.pycube_solver.solver")
    helper_module = import_module("third_party.pycube_solver.helper")
    return cube_module.Cube, solver_module.Solver, helper_module.parseFormula


def _build_stage_results(
    original_facelets: str,
    decorated_output: str,
    raw_output: str,
    parse_formula,
) -> tuple[list[CFOPStageResult], list[str], CFOPSegmentation]:
    stage_formulas = _extract_stage_formulas(decorated_output)
    solver_stage_moves: dict[str, list[str]] | None = None

    if stage_formulas:
        solver_stage_moves = {"cross": [], "f2l": [], "oll": [], "pll": []}
        for stage_label, formula in stage_formulas:
            stage_id = STAGE_LABEL_TO_ID.get(stage_label)
            if stage_id is None:
                continue
            pycube_moves = parse_formula(formula)
            solver_stage_moves[stage_id].extend(_map_pycube_moves_to_project(pycube_moves))

        solver_stage_moves = {
            stage_id: simplify_moves(moves)
            for stage_id, moves in solver_stage_moves.items()
        }
        all_moves = [
            move
            for stage_id in ("cross", "f2l", "oll", "pll")
            for move in solver_stage_moves[stage_id]
        ]
    else:
        fallback_formula = "".join(line.strip() for line in raw_output.splitlines())
        pycube_moves = parse_formula(fallback_formula) if fallback_formula else []
        all_moves = simplify_moves(_map_pycube_moves_to_project(pycube_moves))

    segmentation = segment_cfop_solution(
        original_facelets,
        all_moves,
        solver_stage_moves=solver_stage_moves,
    )

    stages: list[CFOPStageResult] = []
    cube = CubieCube.from_facelet_string(original_facelets)

    for segment in segmentation.stages:
        mapped_moves = segment.moves
        before_facelets = cube.to_facelet_string()
        if mapped_moves:
            cube.apply_alg(mapped_moves)
        after_facelets = cube.to_facelet_string()
        move_string = join_alg(mapped_moves)
        display_moves = map_internal_moves_to_viewer(mapped_moves)
        display_move_string = join_alg(display_moves)
        instruction_lines = [f"moves: {display_move_string}"] if display_moves else ["No moves required."]
        stages.append(
            CFOPStageResult(
                name=segment.label,
                slot=None,
                case_id=segment.id.upper(),
                description=STAGE_DESCRIPTIONS[segment.id],
                cube_rotation=[],
                algorithm_moves=mapped_moves[:],
                display_moves=display_moves,
                instruction_lines=instruction_lines,
                moves=mapped_moves[:],
                move_string=move_string,
                cube_facelets_before=before_facelets,
                cube_facelets_after=after_facelets,
                success=segment.verified,
                error=None if segment.verified else f"{segment.label} boundary could not be verified.",
            )
        )

    return stages, all_moves, segmentation


def _extract_stage_formulas(decorated_output: str) -> list[tuple[str, str]]:
    stage_formulas: list[tuple[str, str]] = []
    for raw_line in decorated_output.splitlines():
        line = raw_line.strip()
        if not line.startswith("For "):
            continue
        label, _, formula = line.partition(":")
        stage_name = label.replace("For ", "", 1).strip()
        if formula.strip():
            stage_formulas.append((stage_name, formula.strip()))
    return stage_formulas


def _map_pycube_moves_to_project(pycube_moves: list[str]) -> list[str]:
    return [_map_single_pycube_move(move) for move in pycube_moves if move]


def _map_single_pycube_move(move: str) -> str:
    normalized = _normalize_pycube_move_token(move)
    base = normalized[0]
    suffix = normalized[1:]

    mapped_base = PYCUBE_BASE_MAP.get(base)
    if mapped_base is None:
        raise ValueError(f"Unsupported PyCube-Solver move token: {move}")

    turns = _suffix_to_turns(suffix)
    if base in PYCUBE_DIRECTION_FLIP:
        turns = (-turns) % 4
        if turns == 0:
            turns = 4

    mapped = mapped_base + _turns_to_suffix(turns)
    return normalize_move_token(mapped)


def _normalize_pycube_move_token(move: str) -> str:
    stripped = move.strip()
    if not stripped:
        raise ValueError("PyCube-Solver move token cannot be empty.")
    if stripped.endswith("P"):
        stripped = stripped[:-1] + "'"
    return stripped


def _suffix_to_turns(suffix: str) -> int:
    if suffix == "":
        return 1
    if suffix == "2":
        return 2
    if suffix == "'":
        return 3
    raise ValueError(f"Unsupported move suffix: {suffix}")


def _turns_to_suffix(turns: int) -> str:
    turns_mod = turns % 4
    if turns_mod == 0:
        return ""
    if turns_mod == 1:
        return ""
    if turns_mod == 2:
        return "2"
    return "'"


def _failed_result(
    error: str,
    setup_text: str,
    final_facelets: str,
    stages: list[CFOPStageResult] | None = None,
) -> CFOPSolveResult:
    stage_list = [] if stages is None else stages
    failing_stage = stage_list[-1].name if stage_list else None
    failing_case_id = stage_list[-1].case_id if stage_list else None
    full_moves = simplify_moves([move for stage in stage_list for move in stage.moves])
    stage_lookup = {stage.name: stage for stage in stage_list}
    cross_stage = stage_lookup.get("White Cross")
    f2l_stage = stage_lookup.get("F2L")
    return CFOPSolveResult(
        success=False,
        error=error,
        failing_stage=failing_stage,
        failing_slot=None,
        failing_case_id=failing_case_id,
        setup_text=setup_text,
        stages=stage_list,
        cross_moves=[] if cross_stage is None else cross_stage.moves[:],
        f2l_slot_results=[] if f2l_stage is None else [f2l_stage],
        oll_result=stage_lookup.get("OLL"),
        pll_result=stage_lookup.get("PLL"),
        auf_moves=[],
        full_moves=full_moves,
        full_move_string=join_alg(full_moves),
        final_facelets=final_facelets,
    )
