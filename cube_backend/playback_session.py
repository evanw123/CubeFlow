from __future__ import annotations

import json
from pathlib import Path

from .move_utils import normalize_move_token
from .validator import validate_facelet_string


def build_playback_session(
    facelets: str,
    moves: list[str],
    title: str = "",
    stages: list[dict] | None = None,
) -> dict:
    validation = validate_facelet_string(facelets)
    if not validation.is_valid:
        raise ValueError("; ".join(validation.errors))

    normalized_moves = [normalize_move_token(move) for move in moves]
    session = {
        "facelets": facelets,
        "moves": normalized_moves,
        "title": title,
    }
    if stages is not None:
        session["stages"] = stages
    return session


def save_playback_session(session: dict, path: str) -> None:
    is_valid, errors = validate_playback_session(session)
    if not is_valid:
        raise ValueError("; ".join(errors))

    Path(path).write_text(json.dumps(session, indent=2), encoding="utf-8")


def load_playback_session(path: str) -> dict:
    session = json.loads(Path(path).read_text(encoding="utf-8"))
    is_valid, errors = validate_playback_session(session)
    if not is_valid:
        raise ValueError("; ".join(errors))
    return session


def validate_playback_session(session: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if not isinstance(session, dict):
        return False, ["Playback session must be a dictionary."]

    facelets = session.get("facelets")
    moves = session.get("moves")
    title = session.get("title", "")
    stages = session.get("stages")

    if not isinstance(facelets, str):
        errors.append("Playback session facelets must be a string.")
    else:
        validation = validate_facelet_string(facelets)
        if not validation.is_valid:
            errors.extend(validation.errors)

    if not isinstance(moves, list):
        errors.append("Playback session moves must be a list.")
    else:
        for index, move in enumerate(moves):
            if not isinstance(move, str):
                errors.append(f"Playback move at index {index} must be a string.")
                continue
            try:
                normalize_move_token(move)
            except ValueError as exc:
                errors.append(str(exc))

    if title is not None and not isinstance(title, str):
        errors.append("Playback session title must be a string.")

    if stages is not None:
        if not isinstance(stages, list):
            errors.append("Playback session stages must be a list.")
        else:
            for index, stage in enumerate(stages):
                if not isinstance(stage, dict):
                    errors.append(f"Playback stage at index {index} must be a dictionary.")
                    continue

                name = stage.get("name")
                start_index = stage.get("start_index")
                end_index = stage.get("end_index")

                if not isinstance(name, str) or not name:
                    errors.append(f"Playback stage at index {index} must have a non-empty name.")
                if not isinstance(start_index, int) or start_index < 0:
                    errors.append(f"Playback stage {name or index} has invalid start_index.")
                if not isinstance(end_index, int) or end_index < 0:
                    errors.append(f"Playback stage {name or index} has invalid end_index.")
                if isinstance(start_index, int) and isinstance(end_index, int) and end_index < start_index:
                    errors.append(f"Playback stage {name or index} has end_index before start_index.")
                if isinstance(end_index, int) and isinstance(moves, list) and end_index > len(moves):
                    errors.append(f"Playback stage {name or index} extends past the move list.")

    return len(errors) == 0, errors
