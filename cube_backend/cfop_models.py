from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CFOPStageResult:
    name: str
    slot: str | None
    case_id: str | None
    description: str
    cube_rotation: list[str] = field(default_factory=list)
    algorithm_moves: list[str] = field(default_factory=list)
    display_moves: list[str] = field(default_factory=list)
    instruction_lines: list[str] = field(default_factory=list)
    moves: list[str] = field(default_factory=list)
    move_string: str = ""
    cube_facelets_before: str = ""
    cube_facelets_after: str = ""
    success: bool = False
    error: str | None = None


@dataclass
class CFOPSolveResult:
    success: bool
    error: str | None
    failing_stage: str | None
    failing_slot: str | None
    failing_case_id: str | None
    setup_text: str
    stages: list[CFOPStageResult]
    cross_moves: list[str]
    f2l_slot_results: list[CFOPStageResult]
    oll_result: CFOPStageResult | None
    pll_result: CFOPStageResult | None
    auf_moves: list[str]
    full_moves: list[str]
    full_move_string: str
    final_facelets: str
    orientation: dict[str, str] = field(default_factory=dict)
    display_moves: list[str] = field(default_factory=list)
    display_move_string: str = ""
    segmentation_source: str | None = None
    segmentation_verified: bool = False
    segmentation_warning: str | None = None
