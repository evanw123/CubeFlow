from __future__ import annotations

from dataclasses import dataclass

from .cfop_analyzer import F2L_SLOT_ORDER, analyze_cross, is_cube_solved, is_f2l_slot_solved, is_oll_solved
from .cubie_model import CubieCube
from .move_utils import normalize_move_token


CFOP_STAGE_SPECS = [
    ("cross", "White Cross"),
    ("f2l", "F2L"),
    ("oll", "OLL"),
    ("pll", "PLL"),
]


@dataclass
class CFOPStageSegment:
    id: str
    label: str
    moves: list[str]
    start_index: int
    end_index: int
    verified: bool


@dataclass
class CFOPSegmentation:
    stages: list[CFOPStageSegment]
    source: str
    verified: bool
    warning: str | None


def segment_cfop_solution(
    original_facelets: str,
    all_moves: list[str],
    solver_stage_moves: dict[str, list[str]] | None = None,
) -> CFOPSegmentation:
    normalized_moves = [normalize_move_token(move) for move in all_moves]

    if solver_stage_moves is not None:
        stages = _segments_from_solver_metadata(solver_stage_moves)
        flattened = [move for stage in stages for move in stage.moves]
        if flattened != normalized_moves:
            return CFOPSegmentation(
                stages=[],
                source="solver_metadata",
                verified=False,
                warning="CFOP solver stage metadata did not match the complete move sequence.",
            )
        return _verify_segments(original_facelets, stages, "solver_metadata")

    stages = _segments_from_state_analysis(original_facelets, normalized_moves)
    if stages is None:
        return CFOPSegmentation(
            stages=[],
            source="state_analysis",
            verified=False,
            warning="CFOP solution was generated, but exact stage boundaries could not be verified.",
        )
    return _verify_segments(original_facelets, stages, "state_analysis")


def white_cross_complete(cube: CubieCube) -> bool:
    return analyze_cross(cube).solved


def f2l_complete(cube: CubieCube) -> bool:
    return white_cross_complete(cube) and all(is_f2l_slot_solved(cube, slot) for slot in F2L_SLOT_ORDER)


def oll_complete(cube: CubieCube) -> bool:
    return f2l_complete(cube) and is_oll_solved(cube)


def pll_complete(cube: CubieCube) -> bool:
    return is_cube_solved(cube)


def _segments_from_solver_metadata(stage_moves: dict[str, list[str]]) -> list[CFOPStageSegment]:
    cursor = 0
    stages: list[CFOPStageSegment] = []
    for stage_id, label in CFOP_STAGE_SPECS:
        moves = [normalize_move_token(move) for move in stage_moves.get(stage_id, [])]
        start_index = cursor
        cursor += len(moves)
        stages.append(
            CFOPStageSegment(
                id=stage_id,
                label=label,
                moves=moves,
                start_index=start_index,
                end_index=cursor,
                verified=False,
            )
        )
    return stages


def _segments_from_state_analysis(
    original_facelets: str,
    all_moves: list[str],
) -> list[CFOPStageSegment] | None:
    cube = CubieCube.from_facelet_string(original_facelets)
    states = [cube.copy()]
    for move in all_moves:
        cube.apply_move(move)
        states.append(cube.copy())

    predicates = [white_cross_complete, f2l_complete, oll_complete, pll_complete]
    boundaries: list[int] = []
    cursor = 0
    for predicate in predicates:
        boundary = next((index for index in range(cursor, len(states)) if predicate(states[index])), None)
        if boundary is None:
            return None
        boundaries.append(boundary)
        cursor = boundary

    if boundaries[-1] != len(all_moves):
        return None

    stages: list[CFOPStageSegment] = []
    start_index = 0
    for (stage_id, label), end_index in zip(CFOP_STAGE_SPECS, boundaries):
        stages.append(
            CFOPStageSegment(
                id=stage_id,
                label=label,
                moves=all_moves[start_index:end_index],
                start_index=start_index,
                end_index=end_index,
                verified=False,
            )
        )
        start_index = end_index
    return stages


def _verify_segments(
    original_facelets: str,
    stages: list[CFOPStageSegment],
    source: str,
) -> CFOPSegmentation:
    cube = CubieCube.from_facelet_string(original_facelets)
    predicates = [white_cross_complete, f2l_complete, oll_complete, pll_complete]
    failures: list[str] = []

    for stage, predicate in zip(stages, predicates):
        cube.apply_alg(stage.moves)
        stage.verified = predicate(cube)
        if not stage.verified:
            failures.append(stage.label)

    warning = None
    if failures:
        warning = "CFOP stage verification failed after: " + ", ".join(failures)

    return CFOPSegmentation(
        stages=stages,
        source=source,
        verified=not failures,
        warning=warning,
    )
