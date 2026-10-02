from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .cfop_analyzer import CROSS_TARGETS, F2L_SLOT_ORDER, F2L_SLOT_TARGETS, analyze_f2l_pairs, from_cfop_working_moves, is_f2l_slot_solved
from .f2l_algorithms import F2LAlgorithm, get_f2l_algorithms_for_case, slot_to_y_rotation_prompt
from .move_simplifier import simplify_moves
from .move_utils import invert_move, join_alg
from .validator import CORNER_FACELETS, EDGE_FACELETS


SLOT_LOCAL_SEARCH_MOVES = {
    "FR": ["D", "D'", "D2", "R", "R'", "R2", "F", "F'", "F2"],
    "FL": ["D", "D'", "D2", "F", "F'", "F2", "L", "L'", "L2"],
    "BL": ["D", "D'", "D2", "L", "L'", "L2", "B", "B'", "B2"],
    "BR": ["D", "D'", "D2", "B", "B'", "B2", "R", "R'", "R2"],
}

TOP_CORNER_FOR_SLOT = {
    "FR": 4,
    "FL": 5,
    "BL": 6,
    "BR": 7,
}

TOP_EDGES_FOR_SLOT = {
    "FR": {4, 5},
    "FL": {5, 6},
    "BL": {6, 7},
    "BR": {4, 7},
}

# When the target pair is adjacent on the top layer, the edge position tells us
# which shared side face the pair currently sits on. That shared face is what
# determines whether the pair is actually insertable or merely adjacent.
TOP_EDGE_TO_SHARED_FACE = {
    "FR": {4: "R", 5: "F"},
    "FL": {5: "F", 6: "L"},
    "BL": {6: "L", 7: "B"},
    "BR": {4: "R", 7: "B"},
}

# We keep two insertable paired variants because "adjacent on top" is still too
# broad. A pair can be above the target slot but only one of the two trigger
# directions is correct. These labels are intentionally geometric rather than
# "good/bad paired".
TOP_EDGE_TO_INSERTION_VARIANT = {
    "FR": {4: "BACK", 5: "FRONT"},
    "FL": {5: "BACK", 6: "FRONT"},
    "BL": {6: "BACK", 7: "FRONT"},
    "BR": {4: "FRONT", 7: "BACK"},
}


@dataclass
class F2LDetailedCase:
    slot: str
    target_corner: str
    target_edge: str
    corner_position: str
    edge_position: str
    pair_relation: str
    pair_location: str
    pair_orientation: str
    inserted: bool
    solved: bool
    normalized_case_id: str
    description: str


def solve_f2l(cube, debug: bool = False) -> list:
    solved_slots: list[str] = []
    results = []

    for slot in F2L_SLOT_ORDER:
        stage = solve_single_f2l_slot(cube, slot, solved_slots, debug=debug)
        results.append(stage)
        if not stage.success:
            break
        solved_slots.append(slot)

    return results


def solve_single_f2l_slot(cube, slot: str, solved_slots: list[str] | None = None, debug: bool = False):
    from .cfop_solver import CFOPStageResult

    solved_slots = [] if solved_slots is None else solved_slots[:]
    preserved_slots = _slots_to_preserve(cube, slot, solved_slots)
    stage_name = f"F2L-{slot}"
    before_facelets = cube.to_facelet_string()

    if not preserves_white_cross(cube):
        return CFOPStageResult(
            name=stage_name,
            slot=slot,
            case_id=None,
            description="Cannot solve F2L before the White Cross is solved.",
            instruction_lines=["White Cross must be solved before F2L."],
            moves=[],
            move_string="",
            cube_facelets_before=before_facelets,
            cube_facelets_after=before_facelets,
            success=False,
            error="White Cross is not solved.",
        )

    if not preserves_solved_f2l_slots(cube, preserved_slots):
        return CFOPStageResult(
            name=stage_name,
            slot=slot,
            case_id=None,
            description="A previously solved F2L slot was disturbed before this stage began.",
            instruction_lines=["A previously solved F2L slot was disturbed."],
            moves=[],
            move_string="",
            cube_facelets_before=before_facelets,
            cube_facelets_after=before_facelets,
            success=False,
            error="Previously solved F2L slot is no longer solved.",
        )

    if is_f2l_slot_solved(cube, slot):
        return CFOPStageResult(
            name=stage_name,
            slot=slot,
            case_id="SOLVED",
            description=f"{slot} slot is already solved.",
            cube_rotation=slot_to_y_rotation_prompt(slot),
            instruction_lines=[f"{slot} slot already solved."],
            moves=[],
            move_string="",
            cube_facelets_before=before_facelets,
            cube_facelets_after=before_facelets,
            success=True,
            error=None,
        )

    accumulated_moves: list[str] = []
    applied_steps: list[F2LAlgorithm] = []
    initial_case_id: str | None = None

    for _ in range(8):
        detailed_case = analyze_single_f2l_pair(cube, slot)
        if initial_case_id is None:
            initial_case_id = detailed_case.normalized_case_id
        _debug_case(slot, detailed_case, debug)

        if detailed_case.solved:
            return _successful_stage_result(
                stage_name,
                before_facelets,
                cube,
                accumulated_moves,
                applied_steps,
                detailed_case,
                initial_case_id,
            )

        if detailed_case.normalized_case_id in {"BURIED_COMPLEX", "CORNER_TOP_EDGE_MIDDLE", "EDGE_TOP_CORNER_SLOT", "INSERTED_BUT_TWISTED"}:
            applied = extract_pair_to_top(cube, slot, preserved_slots, debug=debug)
            if applied is None:
                fallback = solve_slot_with_local_search(cube, slot, preserved_slots, debug=debug)
                if fallback is not None:
                    accumulated_moves.extend(fallback.moves)
                    applied_steps.append(fallback)
                    continue
                return _failed_slot_result(
                    stage_name,
                    before_facelets,
                    cube,
                    accumulated_moves,
                    applied_steps,
                    detailed_case.normalized_case_id,
                    f"Unsupported F2L extraction case for {slot}: {detailed_case.normalized_case_id}.",
                )
            accumulated_moves.extend(applied.moves)
            applied_steps.append(applied)
            continue

        if detailed_case.normalized_case_id == "SEPARATE_TOP":
            applied = pair_top_case(cube, slot, preserved_slots, debug=debug)
            if applied is None:
                fallback = solve_slot_with_local_search(cube, slot, preserved_slots, debug=debug)
                if fallback is not None:
                    accumulated_moves.extend(fallback.moves)
                    applied_steps.append(fallback)
                    continue
                return _failed_slot_result(
                    stage_name,
                    before_facelets,
                    cube,
                    accumulated_moves,
                    applied_steps,
                    detailed_case.normalized_case_id,
                    f"Could not pair the top-layer {slot} pieces.",
                )
            accumulated_moves.extend(applied.moves)
            applied_steps.append(applied)
            continue

        if detailed_case.normalized_case_id in {"PAIRED_ABOVE_WRONG_SLOT", "PAIRED_TOP_MISORIENTED"}:
            applied = normalize_pair_for_insertion(cube, slot, preserved_slots, debug=debug)
            if applied is None:
                fallback = solve_slot_with_local_search(cube, slot, preserved_slots, debug=debug)
                if fallback is not None:
                    accumulated_moves.extend(fallback.moves)
                    applied_steps.append(fallback)
                    continue
                return _failed_slot_result(
                    stage_name,
                    before_facelets,
                    cube,
                    accumulated_moves,
                    applied_steps,
                    detailed_case.normalized_case_id,
                    f"Could not normalize paired {slot} case {detailed_case.normalized_case_id}.",
                )
            accumulated_moves.extend(applied.moves)
            applied_steps.append(applied)
            continue

        if detailed_case.normalized_case_id in {"PAIRED_TOP_READY", "PAIRED_INSERTABLE_FRONT", "PAIRED_INSERTABLE_BACK"}:
            applied = insert_f2l_pair(cube, slot, preserved_slots, debug=debug)
            if applied is None:
                fallback = solve_slot_with_local_search(cube, slot, preserved_slots, debug=debug)
                if fallback is not None:
                    accumulated_moves.extend(fallback.moves)
                    applied_steps.append(fallback)
                    continue
                return _failed_slot_result(
                    stage_name,
                    before_facelets,
                    cube,
                    accumulated_moves,
                    applied_steps,
                    detailed_case.normalized_case_id,
                    f"Could not insert paired {slot} case {detailed_case.normalized_case_id}.",
                )
            accumulated_moves.extend(applied.moves)
            applied_steps.append(applied)
            continue

        return _failed_slot_result(
            stage_name,
            before_facelets,
            cube,
            accumulated_moves,
            applied_steps,
            detailed_case.normalized_case_id,
            f"Unsupported F2L normalized case for {slot}: {detailed_case.normalized_case_id}.",
        )

    final_case = analyze_single_f2l_pair(cube, slot)
    return _failed_slot_result(
        stage_name,
        before_facelets,
        cube,
        accumulated_moves,
        applied_steps,
        final_case.normalized_case_id,
        f"Exceeded staged F2L attempt budget for {slot} ({final_case.normalized_case_id}).",
    )


def analyze_single_f2l_pair(cube, slot: str) -> F2LDetailedCase:
    pair_state = _pair_state_for_slot(cube, slot)
    corner_index = _corner_index_from_name(pair_state.corner_position)
    edge_index = _edge_index_from_name(pair_state.edge_position)

    if pair_state.solved:
        return F2LDetailedCase(
            slot=slot,
            target_corner=pair_state.target_corner,
            target_edge=pair_state.target_edge,
            corner_position=pair_state.corner_position,
            edge_position=pair_state.edge_position,
            pair_relation="solved",
            pair_location="slot",
            pair_orientation="solved",
            inserted=True,
            solved=True,
            normalized_case_id="SOLVED",
            description="Target pair is already solved.",
        )

    pair_above_target_slot = (
        corner_index == TOP_CORNER_FOR_SLOT[slot]
        and edge_index in TOP_EDGES_FOR_SLOT[slot]
    )

    if pair_state.paired and pair_state.pair_on_top:
        if pair_above_target_slot:
            shared_face = TOP_EDGE_TO_SHARED_FACE[slot][edge_index]
            if _top_pair_is_insertable_on_shared_face(cube, pair_state.corner_position, pair_state.edge_position, shared_face):
                insertion_variant = TOP_EDGE_TO_INSERTION_VARIANT[slot][edge_index]
                normalized_case_id = f"PAIRED_INSERTABLE_{insertion_variant}"
                pair_location = "top_target_slot"
                pair_orientation = f"insertable_{insertion_variant.lower()}"
                description = f"Target pair is paired on top and ready for the {insertion_variant.lower()} insertion trigger."
            else:
                normalized_case_id = "PAIRED_TOP_MISORIENTED"
                pair_location = "top_target_slot"
                pair_orientation = "paired_but_misoriented"
                description = "Target pair is adjacent on top but twisted relative to the target slot."
        else:
            normalized_case_id = "PAIRED_ABOVE_WRONG_SLOT"
            pair_location = "top_wrong_slot"
            pair_orientation = "misoriented_or_wrong_slot"
            description = "Target pair is paired on top but not above the target slot."

        return F2LDetailedCase(
            slot=slot,
            target_corner=pair_state.target_corner,
            target_edge=pair_state.target_edge,
            corner_position=pair_state.corner_position,
            edge_position=pair_state.edge_position,
            pair_relation="paired",
            pair_location=pair_location,
            pair_orientation=pair_orientation,
            inserted=False,
            solved=False,
            normalized_case_id=normalized_case_id,
            description=description,
        )

    if pair_state.inserted and not pair_state.solved:
        return F2LDetailedCase(
            slot=slot,
            target_corner=pair_state.target_corner,
            target_edge=pair_state.target_edge,
            corner_position=pair_state.corner_position,
            edge_position=pair_state.edge_position,
            pair_relation="paired_or_split",
            pair_location="inserted_wrong",
            pair_orientation="twisted",
            inserted=True,
            solved=False,
            normalized_case_id="INSERTED_BUT_TWISTED",
            description="Pieces are inserted but the slot is not solved.",
        )

    if pair_state.corner_in_top and pair_state.edge_in_top:
        return F2LDetailedCase(
            slot=slot,
            target_corner=pair_state.target_corner,
            target_edge=pair_state.target_edge,
            corner_position=pair_state.corner_position,
            edge_position=pair_state.edge_position,
            pair_relation="separate",
            pair_location="split_top",
            pair_orientation="unpaired",
            inserted=False,
            solved=False,
            normalized_case_id="SEPARATE_TOP",
            description="Corner and edge are separate on the top layer.",
        )

    if pair_state.corner_in_top and not pair_state.edge_in_top:
        return F2LDetailedCase(
            slot=slot,
            target_corner=pair_state.target_corner,
            target_edge=pair_state.target_edge,
            corner_position=pair_state.corner_position,
            edge_position=pair_state.edge_position,
            pair_relation="separate",
            pair_location="corner_top_edge_middle",
            pair_orientation="unpaired",
            inserted=False,
            solved=False,
            normalized_case_id="CORNER_TOP_EDGE_MIDDLE",
            description="Corner is on top and edge is buried.",
        )

    if not pair_state.corner_in_top and pair_state.edge_in_top:
        return F2LDetailedCase(
            slot=slot,
            target_corner=pair_state.target_corner,
            target_edge=pair_state.target_edge,
            corner_position=pair_state.corner_position,
            edge_position=pair_state.edge_position,
            pair_relation="separate",
            pair_location="edge_top_corner_slot",
            pair_orientation="unpaired",
            inserted=False,
            solved=False,
            normalized_case_id="EDGE_TOP_CORNER_SLOT",
            description="Edge is on top and corner is buried.",
        )

    return F2LDetailedCase(
        slot=slot,
        target_corner=pair_state.target_corner,
        target_edge=pair_state.target_edge,
        corner_position=pair_state.corner_position,
        edge_position=pair_state.edge_position,
        pair_relation="complex",
        pair_location="buried",
        pair_orientation="unknown",
        inserted=False,
        solved=False,
        normalized_case_id="BURIED_COMPLEX",
        description="Pair is buried or in a complex relation.",
    )


def extract_pair_to_top(cube, slot: str, solved_slots: list[str], debug: bool = False) -> F2LAlgorithm | None:
    detailed_case = analyze_single_f2l_pair(cube, slot)
    algorithms = get_f2l_algorithms_for_case(detailed_case.normalized_case_id, slot)

    for algorithm in algorithms:
        global_moves = simplify_moves(from_cfop_working_moves(algorithm.moves))
        if _candidate_reaches_goal(cube, slot, solved_slots, global_moves, _extraction_goal):
            applied = F2LAlgorithm(
                case_id=algorithm.case_id,
                slot=slot,
                description=algorithm.description,
                moves=global_moves,
                display_moves=simplify_moves(algorithm.display_moves[:]),
                phase=algorithm.phase,
                source=algorithm.source,
            )
            cube.apply_alg(applied.moves)
            _debug_algorithm(slot, applied, debug)
            return applied

    search_moves = _find_slot_local_sequence(
        cube,
        slot,
        lambda probe: _extraction_goal(probe, slot, solved_slots),
        max_depth=5,
    )
    if search_moves is not None:
        algorithm = F2LAlgorithm(
            case_id=f"LOCAL_EXTRACT_{slot}",
            slot=slot,
            description=f"Used bounded slot-local extraction setup for {slot}.",
            moves=simplify_moves(search_moves),
            display_moves=simplify_moves(search_moves),
            phase="extract",
            source="local_search",
        )
        cube.apply_alg(algorithm.moves)
        _debug_algorithm(slot, algorithm, debug)
        return algorithm

    return None


def normalize_pair_for_insertion(cube, slot: str, solved_slots: list[str], debug: bool = False) -> F2LAlgorithm | None:
    search_moves = _find_slot_local_sequence(
        cube,
        slot,
        lambda probe: _normalization_goal(probe, slot, solved_slots),
        max_depth=4,
    )
    if search_moves is not None:
        algorithm = F2LAlgorithm(
            case_id=f"LOCAL_NORMALIZE_{slot}",
            slot=slot,
            description=f"Normalized paired {slot} state above the target slot.",
            moves=simplify_moves(search_moves),
            display_moves=simplify_moves(search_moves),
            phase="normalize",
            source="local_search",
        )
        cube.apply_alg(algorithm.moves)
        _debug_algorithm(slot, algorithm, debug)
        return algorithm

    return None


def pair_top_case(cube, slot: str, solved_slots: list[str], debug: bool = False) -> F2LAlgorithm | None:
    detailed_case = analyze_single_f2l_pair(cube, slot)
    algorithms = get_f2l_algorithms_for_case(detailed_case.normalized_case_id, slot)

    for algorithm in algorithms:
        global_moves = simplify_moves(from_cfop_working_moves(algorithm.moves))
        if _candidate_reaches_goal(cube, slot, solved_slots, global_moves, _pair_goal):
            applied = F2LAlgorithm(
                case_id=algorithm.case_id,
                slot=slot,
                description=algorithm.description,
                moves=global_moves,
                display_moves=simplify_moves(algorithm.display_moves[:]),
                phase=algorithm.phase,
                source=algorithm.source,
            )
            cube.apply_alg(applied.moves)
            _debug_algorithm(slot, applied, debug)
            return applied

    search_moves = _find_slot_local_sequence(
        cube,
        slot,
        lambda probe: _pair_goal(probe, slot, solved_slots),
        max_depth=5,
    )
    if search_moves is not None:
        algorithm = F2LAlgorithm(
            case_id=f"LOCAL_PAIR_{slot}",
            slot=slot,
            description=f"Used bounded slot-local pairing setup for {slot}.",
            moves=simplify_moves(search_moves),
            display_moves=simplify_moves(search_moves),
            phase="pair",
            source="local_search",
        )
        cube.apply_alg(algorithm.moves)
        _debug_algorithm(slot, algorithm, debug)
        return algorithm

    return None


def insert_f2l_pair(cube, slot: str, solved_slots: list[str], debug: bool = False) -> F2LAlgorithm | None:
    detailed_case = analyze_single_f2l_pair(cube, slot)
    algorithms = get_f2l_algorithms_for_case(detailed_case.normalized_case_id, slot)

    for algorithm in algorithms:
        global_moves = simplify_moves(from_cfop_working_moves(algorithm.moves))
        if _candidate_reaches_goal(cube, slot, solved_slots, global_moves, _insertion_goal):
            applied = F2LAlgorithm(
                case_id=algorithm.case_id,
                slot=slot,
                description=algorithm.description,
                moves=global_moves,
                display_moves=simplify_moves(algorithm.display_moves[:]),
                phase=algorithm.phase,
                source=algorithm.source,
            )
            cube.apply_alg(applied.moves)
            _debug_algorithm(slot, applied, debug)
            return applied

    search_moves = _find_slot_local_sequence(
        cube,
        slot,
        lambda probe: _insertion_goal(probe, slot, solved_slots),
        max_depth=6,
    )
    if search_moves is not None:
        algorithm = F2LAlgorithm(
            case_id=f"LOCAL_INSERT_{slot}",
            slot=slot,
            description=f"Used bounded slot-local insertion setup for {slot}.",
            moves=simplify_moves(search_moves),
            display_moves=simplify_moves(search_moves),
            phase="insert",
            source="local_search",
        )
        cube.apply_alg(algorithm.moves)
        _debug_algorithm(slot, algorithm, debug)
        return algorithm

    return None


def preserves_white_cross(cube) -> bool:
    from .cfop_solver import is_white_cross_solved

    return is_white_cross_solved(cube)


def preserves_solved_f2l_slots(cube, solved_slots: list[str]) -> bool:
    return all(is_f2l_slot_solved(cube, slot) for slot in solved_slots)


def verify_f2l_slot_solved(cube, slot: str, solved_slots: list[str]) -> bool:
    return (
        preserves_white_cross(cube)
        and preserves_solved_f2l_slots(cube, solved_slots)
        and is_f2l_slot_solved(cube, slot)
    )


def _slots_to_preserve(cube, current_slot: str, solved_slots: list[str]) -> list[str]:
    preserved = []
    for slot in F2L_SLOT_ORDER:
        if slot == current_slot:
            continue
        if slot in solved_slots or is_f2l_slot_solved(cube, slot):
            preserved.append(slot)
    return preserved


def solve_slot_with_local_search(cube, slot: str, solved_slots: list[str], debug: bool = False) -> F2LAlgorithm | None:
    """
    Stage-local fallback for difficult F2L slots.

    This is intentionally not a generic rest-of-cube solver. The search only
    uses moves around the target slot plus working-U turns (global D turns), and
    the tracked signature only includes:
    - the White Cross edges
    - previously solved F2L slots
    - the current target F2L pair
    """
    search_moves = _find_slot_exact_solution_sequence(cube, slot, solved_slots, max_total_depth=10)
    if search_moves is None:
        return None

    algorithm = F2LAlgorithm(
        case_id=f"LOCAL_SLOT_SEARCH_{slot}",
        slot=slot,
        description=f"Solved the {slot} slot with a bounded slot-local fallback search.",
        moves=simplify_moves(search_moves),
        display_moves=simplify_moves(search_moves),
        phase="recovery",
        source="local_search",
    )
    cube.apply_alg(algorithm.moves)
    _debug_algorithm(slot, algorithm, debug)
    return algorithm


def _candidate_reaches_goal(cube, slot: str, solved_slots: list[str], moves: list[str], goal) -> bool:
    probe = cube.copy()
    probe.apply_alg(moves)
    return goal(probe, slot, solved_slots)


def _extraction_goal(cube, slot: str, solved_slots: list[str]) -> bool:
    if not preserves_white_cross(cube) or not preserves_solved_f2l_slots(cube, solved_slots):
        return False

    detailed_case = analyze_single_f2l_pair(cube, slot)
    return detailed_case.normalized_case_id in {
        "SOLVED",
        "SEPARATE_TOP",
        "PAIRED_INSERTABLE_FRONT",
        "PAIRED_INSERTABLE_BACK",
        "PAIRED_ABOVE_WRONG_SLOT",
        "PAIRED_TOP_MISORIENTED",
    }


def _pair_goal(cube, slot: str, solved_slots: list[str]) -> bool:
    if not preserves_white_cross(cube) or not preserves_solved_f2l_slots(cube, solved_slots):
        return False

    detailed_case = analyze_single_f2l_pair(cube, slot)
    return detailed_case.normalized_case_id in {
        "SOLVED",
        "PAIRED_INSERTABLE_FRONT",
        "PAIRED_INSERTABLE_BACK",
        "PAIRED_ABOVE_WRONG_SLOT",
        "PAIRED_TOP_MISORIENTED",
    }


def _normalization_goal(cube, slot: str, solved_slots: list[str]) -> bool:
    if not preserves_white_cross(cube) or not preserves_solved_f2l_slots(cube, solved_slots):
        return False

    detailed_case = analyze_single_f2l_pair(cube, slot)
    return detailed_case.normalized_case_id in {
        "SOLVED",
        "PAIRED_INSERTABLE_FRONT",
        "PAIRED_INSERTABLE_BACK",
    }


def _insertion_goal(cube, slot: str, solved_slots: list[str]) -> bool:
    return verify_f2l_slot_solved(cube, slot, solved_slots)


def _find_slot_local_sequence(cube, slot: str, goal, max_depth: int) -> list[str] | None:
    if goal(cube):
        return []

    allowed_moves = SLOT_LOCAL_SEARCH_MOVES[slot]
    queue = deque([(cube.copy(), [])])
    seen = {cube.to_facelet_string()}

    while queue:
        state, path = queue.popleft()
        if len(path) >= max_depth:
            continue

        last_face = path[-1][0] if path else None
        for move in allowed_moves:
            if last_face is not None and move[0] == last_face:
                continue

            next_cube = state.copy()
            next_cube.apply_move(move)
            signature = next_cube.to_facelet_string()
            if signature in seen:
                continue

            next_path = path + [move]
            if goal(next_cube):
                return next_path

            seen.add(signature)
            queue.append((next_cube, next_path))

    return None


def _find_slot_exact_solution_sequence(cube, slot: str, solved_slots: list[str], max_total_depth: int) -> list[str] | None:
    allowed_moves = SLOT_LOCAL_SEARCH_MOVES[slot]
    start_signature = _slot_stage_signature(cube, slot, solved_slots)
    solved_cube = _slot_goal_cube()
    goal_signature = _slot_stage_signature(solved_cube, slot, solved_slots)

    if start_signature == goal_signature:
        return []

    forward_layer = {start_signature: (cube.copy(), [])}
    backward_layer = {goal_signature: (solved_cube, [])}
    forward_visited = dict(forward_layer)
    backward_visited = dict(backward_layer)

    for _ in range(max_total_depth):
        if len(forward_layer) <= len(backward_layer):
            solution, next_layer = _expand_slot_bidirectional_layer(
                forward_layer,
                forward_visited,
                backward_visited,
                allowed_moves,
                slot,
                solved_slots,
                forward=True,
            )
            forward_layer = next_layer
            forward_visited.update(next_layer)
        else:
            solution, next_layer = _expand_slot_bidirectional_layer(
                backward_layer,
                backward_visited,
                forward_visited,
                allowed_moves,
                slot,
                solved_slots,
                forward=False,
            )
            backward_layer = next_layer
            backward_visited.update(next_layer)

        if solution is not None:
            return solution
        if not forward_layer or not backward_layer:
            break

    return None


def _expand_slot_bidirectional_layer(
    current_layer: dict,
    current_visited: dict,
    opposite_visited: dict,
    allowed_moves: list[str],
    slot: str,
    solved_slots: list[str],
    *,
    forward: bool,
) -> tuple[list[str] | None, dict]:
    next_layer: dict = {}

    for _, (state_cube, path) in current_layer.items():
        last_face = path[-1][0] if path else None
        for move in allowed_moves:
            if last_face is not None and move[0] == last_face:
                continue

            next_cube = state_cube.copy()
            next_cube.apply_move(move)
            signature = _slot_stage_signature(next_cube, slot, solved_slots)
            if signature in current_visited or signature in next_layer:
                continue

            next_path = path + [move]
            if signature in opposite_visited:
                opposite_path = opposite_visited[signature][1]
                if forward:
                    return next_path + [invert_move(step) for step in reversed(opposite_path)], next_layer
                return opposite_path + [invert_move(step) for step in reversed(next_path)], next_layer

            next_layer[signature] = (next_cube, next_path)

    return None, next_layer


def _slot_stage_signature(cube, slot: str, solved_slots: list[str]) -> tuple[tuple, tuple]:
    tracked_corners: list[tuple[int, int, int]] = []
    tracked_edges: list[tuple[int, int, int]] = []

    for tracked_slot in solved_slots + [slot]:
        slot_info = F2L_SLOT_TARGETS[tracked_slot]
        corner_cubie_index = slot_info["corner_index"]
        corner_position_index = cube.corner_perm.index(corner_cubie_index)
        tracked_corners.append(
            (
                corner_cubie_index,
                corner_position_index,
                cube.corner_ori[corner_position_index],
            )
        )

        edge_cubie_index = slot_info["edge_index"]
        edge_position_index = cube.edge_perm.index(edge_cubie_index)
        tracked_edges.append(
            (
                edge_cubie_index,
                edge_position_index,
                cube.edge_ori[edge_position_index],
            )
        )

    for _, edge_cubie_index, _ in CROSS_TARGETS:
        edge_position_index = cube.edge_perm.index(edge_cubie_index)
        tracked_edges.append(
            (
                edge_cubie_index,
                edge_position_index,
                cube.edge_ori[edge_position_index],
            )
        )

    return tuple(sorted(tracked_corners)), tuple(sorted(tracked_edges))


def _slot_goal_cube():
    from .cubie_model import CubieCube

    return CubieCube.solved()


def _top_pair_is_insertable_on_shared_face(
    cube,
    corner_position_name: str,
    edge_position_name: str,
    shared_face: str,
) -> bool:
    facelets = cube.to_facelet_string()
    corner_face_colors = _position_face_colors(
        facelets,
        corner_position_name,
        CORNER_FACELETS[_corner_index_from_name(corner_position_name)],
    )
    edge_face_colors = _position_face_colors(
        facelets,
        edge_position_name,
        EDGE_FACELETS[_edge_index_from_name(edge_position_name)],
    )
    return (
        corner_face_colors.get(shared_face) == shared_face
        and edge_face_colors.get(shared_face) == shared_face
    )


def _position_face_colors(facelets: str, position_name: str, facelet_indices: list[int]) -> dict[str, str]:
    return {
        face_name: facelets[facelet_index]
        for face_name, facelet_index in zip(position_name, facelet_indices)
    }


def _pair_state_for_slot(cube, slot: str):
    return next(pair_state for pair_state in analyze_f2l_pairs(cube) if pair_state.slot == slot)


def _corner_index_from_name(name: str) -> int:
    corner_names = ["URF", "UFL", "ULB", "UBR", "DFR", "DLF", "DBL", "DRB"]
    return corner_names.index(name)


def _edge_index_from_name(name: str) -> int:
    edge_names = ["UR", "UF", "UL", "UB", "DR", "DF", "DL", "DB", "FR", "FL", "BL", "BR"]
    return edge_names.index(name)


def _debug_case(slot: str, detailed_case: F2LDetailedCase, debug: bool) -> None:
    if not debug:
        return
    print(f"=== F2L DEBUG: {slot} ===")
    print(f"corner_position: {detailed_case.corner_position}")
    print(f"edge_position: {detailed_case.edge_position}")
    print(f"pair_relation: {detailed_case.pair_relation}")
    print(f"pair_location: {detailed_case.pair_location}")
    print(f"pair_orientation: {detailed_case.pair_orientation}")
    print(f"normalized_case_id: {detailed_case.normalized_case_id}")


def _debug_algorithm(slot: str, algorithm: F2LAlgorithm, debug: bool) -> None:
    if not debug:
        return
    print(f"selected_algorithm: {algorithm.case_id}")
    print(f"moves: {join_alg(algorithm.moves)}")


def _successful_stage_result(
    stage_name: str,
    before_facelets: str,
    cube,
    accumulated_moves: list[str],
    applied_steps: list[F2LAlgorithm],
    detailed_case: F2LDetailedCase,
    initial_case_id: str | None,
):
    from .cfop_solver import CFOPStageResult

    stage_moves = simplify_moves(accumulated_moves[:])
    cube_rotation, display_moves, instruction_lines = _build_f2l_instruction_payload(detailed_case.slot, applied_steps, stage_moves)
    return CFOPStageResult(
        name=stage_name,
        slot=detailed_case.slot,
        case_id=initial_case_id or detailed_case.normalized_case_id,
        description=f"Solved the {detailed_case.slot} F2L slot.",
        cube_rotation=cube_rotation,
        algorithm_moves=stage_moves[:],
        display_moves=display_moves[:],
        instruction_lines=instruction_lines,
        moves=stage_moves[:],
        move_string=join_alg(display_moves or stage_moves),
        cube_facelets_before=before_facelets,
        cube_facelets_after=cube.to_facelet_string(),
        success=True,
        error=None,
    )


def _failed_slot_result(
    stage_name: str,
    before_facelets: str,
    cube,
    accumulated_moves: list[str],
    applied_steps: list[F2LAlgorithm],
    case_id: str | None,
    error: str,
):
    from .cfop_solver import CFOPStageResult

    stage_moves = simplify_moves(accumulated_moves[:])
    slot = stage_name.split("-", 1)[1] if "-" in stage_name else None
    cube_rotation, display_moves, instruction_lines = _build_f2l_instruction_payload(slot, applied_steps, stage_moves)
    return CFOPStageResult(
        name=stage_name,
        slot=slot,
        case_id=case_id,
        description=error,
        cube_rotation=cube_rotation,
        algorithm_moves=stage_moves[:],
        display_moves=display_moves[:],
        instruction_lines=instruction_lines,
        moves=stage_moves[:],
        move_string=join_alg(display_moves or stage_moves),
        cube_facelets_before=before_facelets,
        cube_facelets_after=cube.to_facelet_string(),
        success=False,
        error=error,
    )


def _build_f2l_instruction_payload(
    slot: str | None,
    applied_steps: list[F2LAlgorithm],
    stage_moves: list[str],
) -> tuple[list[str], list[str], list[str]]:
    if slot is None:
        return [], stage_moves[:], []

    if not applied_steps:
        return slot_to_y_rotation_prompt(slot), [], [f"{slot} already solved."]

    if any(step.source != "library" for step in applied_steps):
        instruction_lines = [f"Use slot-local recovery: {join_alg(stage_moves)}"]
        return [], stage_moves[:], instruction_lines

    rotation_prompt = slot_to_y_rotation_prompt(slot)
    display_moves = simplify_moves([move for step in applied_steps for move in step.display_moves])
    instruction_lines: list[str] = []

    phase_labels = {
        "extract": "Extract",
        "normalize": "Normalize",
        "pair": "Pair",
        "insert": "Insert",
        "recovery": "Recover",
    }

    for step in applied_steps:
        label = phase_labels.get(step.phase, "Step")
        instruction_lines.append(f"{label}: {join_alg(simplify_moves(step.display_moves[:]))}")

    return rotation_prompt, display_moves, instruction_lines
