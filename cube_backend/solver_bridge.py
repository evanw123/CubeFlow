from __future__ import annotations

from dataclasses import dataclass

from .move_utils import parse_alg
from .validator import validate_cube_state, validate_facelet_string


@dataclass
class SolveResult:
    success: bool
    moves: str | None
    move_list: list[str]
    error: str | None
    facelets: str


def solve_facelet_string(facelets: str) -> SolveResult:
    validation = validate_facelet_string(facelets)
    if not validation.is_valid:
        return SolveResult(
            success=False,
            moves=None,
            move_list=[],
            error="Deep validation failed: " + "; ".join(validation.errors),
            facelets=facelets,
        )

    try:
        import kociemba
    except ImportError:
        return SolveResult(
            success=False,
            moves=None,
            move_list=[],
            error="kociemba is not installed. Run: pip install kociemba",
            facelets=facelets,
        )

    try:
        moves = kociemba.solve(facelets).strip()
    except Exception as exc:
        return SolveResult(
            success=False,
            moves=None,
            move_list=[],
            error=f"Solver error: {exc}",
            facelets=facelets,
        )

    move_list = parse_alg(moves) if moves else []
    return SolveResult(
        success=True,
        moves=moves,
        move_list=move_list,
        error=None,
        facelets=facelets,
    )


def solve_cube_state(cube_state) -> SolveResult:
    validation = validate_cube_state(cube_state)
    if not validation.is_valid:
        return SolveResult(
            success=False,
            moves=None,
            move_list=[],
            error="Deep validation failed: " + "; ".join(validation.errors),
            facelets=validation.facelets,
        )

    return solve_facelet_string(validation.facelets)


def format_solution_for_display(result: SolveResult) -> str:
    if not result.success:
        return result.error or "Solver failed."
    if result.moves:
        return result.moves
    return "Cube is already solved."
