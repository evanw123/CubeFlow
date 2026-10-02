from __future__ import annotations


VALID_MOVE_FACES = {
    "U", "D", "L", "R", "F", "B",
    "M", "E", "S",
    "x", "y", "z",
    "r", "l", "u", "d", "f", "b",
}
VALID_MOVE_SUFFIXES = {"", "'", "2"}


def simplify_moves(moves: list[str]) -> list[str]:
    """
    Simplify adjacent turns on the same face, slice, wide-move, or rotation axis.
    """
    simplified_stack: list[str] = []

    for move in moves:
        normalized = _normalize_extended_move_token(move)
        if not simplified_stack:
            simplified_stack.append(normalized)
            continue

        combined = combine_adjacent_moves(simplified_stack[-1], normalized)
        if combined is None:
            simplified_stack.append(normalized)
            continue

        simplified_stack.pop()
        simplified_stack.extend(combined)

    return simplified_stack


def simplify_move_string(alg: str) -> str:
    if not alg.strip():
        return ""
    return " ".join(simplify_moves(alg.split()))


def combine_adjacent_moves(m1: str, m2: str) -> list[str] | None:
    normalized_1 = _normalize_extended_move_token(m1)
    normalized_2 = _normalize_extended_move_token(m2)

    if normalized_1[0] != normalized_2[0]:
        return None

    quarter_turns = (_move_to_quarter_turns(normalized_1) + _move_to_quarter_turns(normalized_2)) % 4
    if quarter_turns == 0:
        return []
    return [_quarter_turns_to_move(normalized_1[0], quarter_turns)]


def _normalize_extended_move_token(token: str) -> str:
    stripped = token.strip()
    if not stripped:
        raise ValueError("Move token cannot be empty.")

    face = stripped[0]
    suffix = stripped[1:]

    if face not in VALID_MOVE_FACES:
        if face.lower() in {"x", "y", "z", "r", "l", "u", "d", "f", "b"} and face.islower():
            face = face.lower()
        elif face.upper() in {"U", "D", "L", "R", "F", "B", "M", "E", "S"}:
            face = face.upper()
        else:
            raise ValueError(f"Invalid move token: {token}")

    if suffix not in VALID_MOVE_SUFFIXES:
        raise ValueError(f"Invalid move token: {token}")

    if face in {"U", "D", "L", "R", "F", "B", "M", "E", "S"}:
        return face.upper() + suffix
    return face.lower() + suffix


def _move_to_quarter_turns(move: str) -> int:
    if move.endswith("2"):
        return 2
    if move.endswith("'"):
        return 3
    return 1


def _quarter_turns_to_move(face: str, quarter_turns: int) -> str:
    normalized_turns = quarter_turns % 4
    if normalized_turns == 0:
        return ""
    if normalized_turns == 1:
        return face
    if normalized_turns == 2:
        return face + "2"
    return face + "'"
