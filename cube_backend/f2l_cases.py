from __future__ import annotations

from dataclasses import dataclass

from .cfop_analyzer import F2LPairState


@dataclass
class F2LCase:
    slot: str
    code: str
    description: str
    recommended_next_step: str


def classify_f2l_case(pair_state: F2LPairState) -> F2LCase:
    if pair_state.solved:
        return F2LCase(
            slot=pair_state.slot,
            code="SOLVED",
            description="Pair is already solved.",
            recommended_next_step="Leave this slot alone and inspect the next unsolved slot.",
        )

    if pair_state.paired and pair_state.pair_on_top:
        return F2LCase(
            slot=pair_state.slot,
            code="PAIRED_TOP",
            description="Pair is paired in the U layer.",
            recommended_next_step="Insert the pair into its target slot.",
        )

    if pair_state.corner_in_top and pair_state.edge_in_top and not pair_state.paired:
        return F2LCase(
            slot=pair_state.slot,
            code="SEPARATE_TOP",
            description="Corner and edge are separate in the U layer.",
            recommended_next_step="Pair them up on top before insertion.",
        )

    if pair_state.corner_in_top and not pair_state.edge_in_top:
        return F2LCase(
            slot=pair_state.slot,
            code="CORNER_TOP_EDGE_MIDDLE",
            description="Corner is on top while the edge is buried in the middle layer.",
            recommended_next_step="Extract or align the edge, then form the pair.",
        )

    if not pair_state.corner_in_top and pair_state.edge_in_top:
        return F2LCase(
            slot=pair_state.slot,
            code="EDGE_TOP_CORNER_SLOT",
            description="Edge is on top while the corner is buried in a slot.",
            recommended_next_step="Free the corner or use the top edge to set up a pair.",
        )

    if pair_state.inserted and not pair_state.solved:
        return F2LCase(
            slot=pair_state.slot,
            code="BOTH_INSERTED_WRONG",
            description="Pair pieces are inserted but the slot is not solved.",
            recommended_next_step="Take the pair out or correct the insertion setup.",
        )

    return F2LCase(
        slot=pair_state.slot,
        code="BURIED_OR_COMPLEX",
        description="Pair is buried or in a more complex state.",
        recommended_next_step="Extract pieces into a cleaner setup before pairing.",
    )


def classify_all_f2l_cases(pair_states: list[F2LPairState]) -> list[F2LCase]:
    return [classify_f2l_case(pair_state) for pair_state in pair_states]
