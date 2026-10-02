from __future__ import annotations

"""
Active CFOP Beta entrypoints.

The live CFOP path is now backed by vendored PyCube-Solver through
`cube_backend.pycube_adapter`. Older in-repo F2L/OLL/PLL modules are retained
for reference and tests, but they are no longer the engine used by the app.
"""

from .cfop_analyzer import analyze_cfop, get_human_orientation_setup_text
from .cfop_models import CFOPSolveResult, CFOPStageResult
from .move_utils import join_alg
from .playback_session import build_playback_session
from .pycube_adapter import solve_cfop_with_pycube, solve_cfop_with_pycube_state


def solve_cfop_from_facelets(facelets: str, debug: bool = False) -> CFOPSolveResult:
    del debug
    return solve_cfop_with_pycube(facelets)


def solve_cfop_from_cube_state(cube_state, debug: bool = False) -> CFOPSolveResult:
    del debug
    return solve_cfop_with_pycube_state(cube_state)


def solve_cfop(cube, debug: bool = False) -> CFOPSolveResult:
    del debug
    return solve_cfop_with_pycube(cube.to_facelet_string())


def format_cfop_solution(result: CFOPSolveResult) -> str:
    lines = ["=== CFOP SOLUTION ===", "Setup:", f"  {result.setup_text}", ""]

    if result.error:
        lines.append(f"Error: {result.error}")
    if result.failing_stage:
        lines.append(f"Failing stage: {result.failing_stage}")
    if result.failing_slot:
        lines.append(f"Failing slot: {result.failing_slot}")
    if result.failing_case_id:
        lines.append(f"Failing case: {result.failing_case_id}")
    if result.error or result.failing_stage or result.failing_slot or result.failing_case_id:
        lines.append("")

    if not result.stages:
        lines.append("CFOP Beta: No moves required.")
        lines.append("")
    else:
        for stage in result.stages:
            lines.append(f"{stage.name}:")
            if stage.slot:
                lines.append(f"  slot: {stage.slot}")
            if stage.case_id:
                lines.append(f"  case: {stage.case_id}")
            if stage.cube_rotation:
                lines.append(f"  rotate: {join_alg(stage.cube_rotation)}")
            else:
                lines.append("  rotate: none")
            if stage.display_moves:
                lines.append(f"  alg: {join_alg(stage.display_moves)}")
            elif stage.moves:
                lines.append(f"  alg: {join_alg(stage.moves)}")
            for line in stage.instruction_lines:
                lines.append(f"  {line}")
            if not stage.success and stage.error:
                lines.append(f"  error: {stage.error}")
            lines.append("")

    lines.append("Total:")
    lines.append(f"  {len(result.full_moves)}")
    lines.append("Combined:")
    lines.append(f"  {result.display_move_string or result.full_move_string}")

    return "\n".join(lines)


def solve_white_cross(cube) -> CFOPStageResult:
    if is_white_cross_solved(cube):
        facelets = cube.to_facelet_string()
        return CFOPStageResult(
            name="White Cross",
            slot=None,
            case_id="SOLVED",
            description="White cross is already solved.",
            instruction_lines=["White Cross already solved."],
            moves=[],
            move_string="",
            cube_facelets_before=facelets,
            cube_facelets_after=facelets,
            success=True,
            error=None,
        )

    result = solve_cfop(cube)
    cross_stage = next((stage for stage in result.stages if stage.name == "White Cross"), None)
    if cross_stage is not None:
        return cross_stage

    facelets = cube.to_facelet_string()
    return CFOPStageResult(
        name="White Cross",
        slot=None,
        case_id=None,
        description="PyCube-Solver did not expose a separate White Cross stage for this solve.",
        instruction_lines=[result.error or "PyCube-Solver could not isolate the White Cross stage."],
        moves=[],
        move_string="",
        cube_facelets_before=facelets,
        cube_facelets_after=facelets,
        success=False,
        error=result.error or "PyCube-Solver could not isolate the White Cross stage.",
    )


def is_white_cross_solved(cube) -> bool:
    return analyze_cfop(cube).cross.solved


def build_cfop_playback_stages(stages: list[CFOPStageResult]) -> list[dict]:
    playback_stages: list[dict] = []
    move_cursor = 0

    for stage in stages:
        start_index = move_cursor
        move_cursor += len(stage.moves)
        playback_stages.append(
            {
                "id": (stage.case_id or stage.name).lower().replace(" ", "_"),
                "name": stage.name,
                "label": stage.name,
                "start_index": start_index,
                "end_index": move_cursor,
                "move_count": len(stage.moves),
                "moves": stage.display_moves[:],
                "verified": stage.success,
                "rotation_prompt": join_alg(stage.cube_rotation) if stage.cube_rotation else "",
                "display_moves": join_alg(stage.display_moves) if stage.display_moves else stage.move_string,
                "description": stage.description,
            }
        )

    return playback_stages


def build_cfop_playback_session(facelets: str, result: CFOPSolveResult, title: str = "CFOP Beta Playback") -> dict:
    if not result.success:
        stage_text = "" if result.failing_stage is None else f" at {result.failing_stage}"
        slot_text = "" if result.failing_slot is None else f" {result.failing_slot}"
        case_text = "" if result.failing_case_id is None else f" ({result.failing_case_id})"
        raise ValueError(f"CFOP solve failed{stage_text}{slot_text}{case_text}: {result.error}")

    session = build_playback_session(
        facelets=facelets,
        moves=result.full_moves,
        title=title,
        stages=build_cfop_playback_stages(result.stages),
    )
    session["setup_text"] = result.setup_text
    session["orientation"] = result.orientation
    session["segmentation_source"] = result.segmentation_source
    session["segmentation_verified"] = result.segmentation_verified
    session["segmentation_warning"] = result.segmentation_warning
    return session
