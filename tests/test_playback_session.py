from __future__ import annotations

from cube_backend.playback_session import (
    build_playback_session,
    load_playback_session,
    save_playback_session,
    validate_playback_session,
)


SOLVED_FACELETS = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"


def test_playback_session_round_trip(tmp_path):
    session = build_playback_session(
        facelets=SOLVED_FACELETS,
        moves=["R", "U", "R'", "U'"],
        title="Playback Test",
        stages=[
            {"name": "White Cross", "start_index": 0, "end_index": 2},
            {"name": "F2L-FR", "start_index": 2, "end_index": 4},
        ],
    )

    session_path = tmp_path / "playback.json"
    save_playback_session(session, str(session_path))
    loaded = load_playback_session(str(session_path))

    assert loaded == session


def test_playback_session_validation_rejects_missing_keys():
    is_valid, errors = validate_playback_session({"moves": ["R"]})
    assert is_valid is False
    assert any("facelets" in error.lower() for error in errors)


def test_playback_session_validation_rejects_bad_move_types():
    is_valid, errors = validate_playback_session(
        {
            "facelets": SOLVED_FACELETS,
            "moves": ["R", 3],
            "title": "Bad Session",
        }
    )

    assert is_valid is False
    assert any("must be a string" in error for error in errors)


def test_playback_session_validation_rejects_bad_stage_ranges():
    is_valid, errors = validate_playback_session(
        {
            "facelets": SOLVED_FACELETS,
            "moves": ["R"],
            "title": "Bad Stage",
            "stages": [{"name": "White Cross", "start_index": 1, "end_index": 2}],
        }
    )

    assert is_valid is False
    assert any("extends past the move list" in error for error in errors)
