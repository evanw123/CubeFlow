from __future__ import annotations

VALID_FACES = {"U", "D", "L", "R", "F", "B"}
VALID_SLICES = {"M", "E", "S"}
VALID_ROTATIONS = {"x", "y", "z"}
VALID_WIDE_MOVES = {"r", "l", "u", "d", "f", "b"}
VALID_SUFFIXES = {"", "'", "2"}


def normalize_move_token(token: str) -> str:
    stripped = token.strip()
    if not stripped:
        raise ValueError("Move token cannot be empty.")

    raw_face = stripped[0]
    suffix = stripped[1:]

    if raw_face in VALID_ROTATIONS or raw_face.lower() in VALID_ROTATIONS and raw_face.islower():
        face = raw_face.lower()
    elif raw_face in VALID_WIDE_MOVES or raw_face.lower() in VALID_WIDE_MOVES and raw_face.islower():
        face = raw_face.lower()
    elif raw_face.upper() in VALID_FACES:
        face = raw_face.upper()
    elif raw_face.upper() in VALID_SLICES:
        face = raw_face.upper()
    else:
        raise ValueError(f"Invalid move token: {token}")

    if suffix not in VALID_SUFFIXES:
        raise ValueError(f"Invalid move token: {token}")

    return face + suffix


def parse_alg(alg: str) -> list[str]:
    if not alg.strip():
        return []
    return [normalize_move_token(token) for token in alg.split()]


def invert_move(move: str) -> str:
    normalized = normalize_move_token(move)
    if normalized.endswith("2"):
        return normalized
    if normalized.endswith("'"):
        return normalized[0]
    return normalized + "'"


def invert_alg(alg: str | list[str]) -> list[str]:
    moves = parse_alg(alg) if isinstance(alg, str) else [normalize_move_token(move) for move in alg]
    return [invert_move(move) for move in reversed(moves)]


def join_alg(moves: list[str]) -> str:
    return " ".join(normalize_move_token(move) for move in moves)
