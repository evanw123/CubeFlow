from __future__ import annotations

from cube_backend.cfop_analyzer import F2LPairState
from cube_backend.f2l_cases import classify_f2l_case


def _pair_state(**updates) -> F2LPairState:
    base = F2LPairState(
        slot="FR",
        target_corner="DFR",
        target_edge="FR",
        corner_position="URF",
        edge_position="UF",
        corner_oriented=False,
        edge_oriented=False,
        paired=False,
        inserted=False,
        solved=False,
        pair_on_top=False,
        corner_in_top=False,
        edge_in_top=False,
        case_hint="BURIED_OR_COMPLEX",
    )
    for key, value in updates.items():
        setattr(base, key, value)
    return base


def test_classify_solved_pair():
    result = classify_f2l_case(
        _pair_state(
            solved=True,
            paired=True,
            inserted=True,
            case_hint="SOLVED",
        )
    )
    assert result.code == "SOLVED"


def test_classify_paired_top():
    result = classify_f2l_case(
        _pair_state(
            paired=True,
            pair_on_top=True,
            corner_in_top=True,
            edge_in_top=True,
            case_hint="PAIRED_TOP",
        )
    )
    assert result.code == "PAIRED_TOP"


def test_classify_separate_top():
    result = classify_f2l_case(
        _pair_state(
            corner_in_top=True,
            edge_in_top=True,
            pair_on_top=True,
            paired=False,
            case_hint="SEPARATE_TOP",
        )
    )
    assert result.code == "SEPARATE_TOP"


def test_classify_buried_complex():
    result = classify_f2l_case(_pair_state(case_hint="BURIED_OR_COMPLEX"))
    assert result.code == "BURIED_OR_COMPLEX"
