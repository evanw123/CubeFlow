from __future__ import annotations

from cube_backend.viewer_snapshot import (
    cube_state_to_view_snapshot,
    facelet_string_to_view_snapshot,
    load_view_snapshot,
    save_view_snapshot,
    validate_view_snapshot,
)


SOLVED_FACELETS = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"


def test_facelet_string_to_snapshot_solved():
    snapshot = facelet_string_to_view_snapshot(SOLVED_FACELETS)

    assert snapshot["U"] == [["YELLOW", "YELLOW", "YELLOW"]] * 3
    assert snapshot["R"] == [["ORANGE", "ORANGE", "ORANGE"]] * 3
    assert snapshot["F"] == [["GREEN", "GREEN", "GREEN"]] * 3
    assert snapshot["D"] == [["WHITE", "WHITE", "WHITE"]] * 3
    assert snapshot["L"] == [["RED", "RED", "RED"]] * 3
    assert snapshot["B"] == [["BLUE", "BLUE", "BLUE"]] * 3


def test_complete_facelet_snapshot_has_no_unknown_values():
    snapshot = facelet_string_to_view_snapshot(SOLVED_FACELETS)

    values = [value for face in snapshot.values() for row in face for value in row]
    assert "UNKNOWN" not in values
    assert None not in values


def test_validate_view_snapshot_accepts_partial_unknown():
    snapshot = {
        "U": [["WHITE", "UNKNOWN", None], ["WHITE", "WHITE", "WHITE"], ["WHITE", "WHITE", "WHITE"]],
        "R": [[None, None, None], [None, None, None], [None, None, None]],
        "F": [["GREEN", "GREEN", "GREEN"], ["GREEN", "GREEN", "GREEN"], ["GREEN", "GREEN", "GREEN"]],
        "D": [["YELLOW", "YELLOW", "YELLOW"], ["YELLOW", "YELLOW", "YELLOW"], ["YELLOW", "YELLOW", "YELLOW"]],
        "L": [["ORANGE", "ORANGE", "ORANGE"], ["ORANGE", "ORANGE", "ORANGE"], ["ORANGE", "ORANGE", "ORANGE"]],
        "B": [["BLUE", "BLUE", "BLUE"], ["BLUE", "BLUE", "BLUE"], ["BLUE", "BLUE", "BLUE"]],
    }

    is_valid, errors = validate_view_snapshot(snapshot)
    assert is_valid is True
    assert errors == []


def test_validate_view_snapshot_rejects_bad_shape():
    snapshot = {
        "U": [["WHITE", "WHITE"]],
        "R": [[None, None, None], [None, None, None], [None, None, None]],
        "F": [[None, None, None], [None, None, None], [None, None, None]],
        "D": [[None, None, None], [None, None, None], [None, None, None]],
        "L": [[None, None, None], [None, None, None], [None, None, None]],
        "B": [[None, None, None], [None, None, None], [None, None, None]],
    }

    is_valid, errors = validate_view_snapshot(snapshot)
    assert is_valid is False
    assert any("Face U must be a 3x3 list." in error for error in errors)


def test_save_and_load_snapshot_round_trip(tmp_path):
    snapshot = {
        "U": [["WHITE", "WHITE", "WHITE"], ["WHITE", "WHITE", "WHITE"], ["WHITE", "WHITE", "WHITE"]],
        "R": [["RED", "RED", "RED"], ["RED", "RED", "RED"], ["RED", "RED", "RED"]],
        "F": [["GREEN", "GREEN", "GREEN"], ["GREEN", "GREEN", "GREEN"], ["GREEN", "GREEN", "GREEN"]],
        "D": [["YELLOW", "YELLOW", "YELLOW"], ["YELLOW", "YELLOW", "YELLOW"], ["YELLOW", "YELLOW", "YELLOW"]],
        "L": [["ORANGE", "ORANGE", "ORANGE"], ["ORANGE", "ORANGE", "ORANGE"], ["ORANGE", "ORANGE", "ORANGE"]],
        "B": [["BLUE", "BLUE", "BLUE"], ["BLUE", "BLUE", "BLUE"], ["BLUE", "BLUE", "BLUE"]],
    }

    snapshot_path = tmp_path / "snapshot.json"
    save_view_snapshot(snapshot, str(snapshot_path))
    loaded_snapshot = load_view_snapshot(str(snapshot_path))

    assert loaded_snapshot == snapshot


def test_cube_state_to_view_snapshot_with_partial_faces():
    class FakeCubeState:
        def __init__(self):
            self.faces = {
                "U": [["WHITE", "WHITE", "WHITE"], ["WHITE", "WHITE", "WHITE"], ["WHITE", "WHITE", "WHITE"]],
                "R": None,
                "F": [["GREEN", "GREEN", "UNKNOWN"], ["GREEN", "GREEN", "GREEN"], ["GREEN", "GREEN", "GREEN"]],
                "D": None,
                "L": [["ORANGE", "ORANGE", "ORANGE"], ["ORANGE", "ORANGE", "ORANGE"], ["ORANGE", "ORANGE", "ORANGE"]],
                "B": None,
            }

    snapshot = cube_state_to_view_snapshot(FakeCubeState())

    assert snapshot["R"] == [["ORANGE", "ORANGE", "ORANGE"]] * 3
    assert snapshot["L"] == [[None, None, None], [None, None, None], [None, None, None]]
    assert snapshot["U"] == [[None, None, None], [None, None, None], [None, None, None]]
    assert snapshot["D"] == [["WHITE", "WHITE", "WHITE"], ["WHITE", "WHITE", "WHITE"], ["WHITE", "WHITE", "WHITE"]]
    assert snapshot["F"][2][0] == "UNKNOWN"


def test_canonical_viewer_centers_are_white_bottom_yellow_top():
    snapshot = facelet_string_to_view_snapshot(SOLVED_FACELETS)

    assert snapshot["U"][1][1] == "YELLOW"
    assert snapshot["D"][1][1] == "WHITE"
    assert snapshot["F"][1][1] == "GREEN"
    assert snapshot["R"][1][1] == "ORANGE"
    assert snapshot["L"][1][1] == "RED"
    assert snapshot["B"][1][1] == "BLUE"
