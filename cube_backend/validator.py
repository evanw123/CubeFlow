from __future__ import annotations

from dataclasses import dataclass


VALID_FACELETS = {"U", "R", "F", "D", "L", "B"}
UD_FACELETS = {"U", "D"}

CORNER_NAMES = ["URF", "UFL", "ULB", "UBR", "DFR", "DLF", "DBL", "DRB"]
EDGE_NAMES = ["UR", "UF", "UL", "UB", "DR", "DF", "DL", "DB", "FR", "FL", "BL", "BR"]

# Facelet positions in the scanner's URFDLB export order.
CORNER_FACELETS = [
    [8, 9, 20],    # URF
    [6, 18, 38],   # UFL
    [0, 36, 47],   # ULB
    [2, 45, 11],   # UBR
    [29, 26, 15],  # DFR
    [27, 44, 24],  # DLF
    [33, 53, 42],  # DBL
    [35, 17, 51],  # DRB
]

EDGE_FACELETS = [
    [5, 10],   # UR
    [7, 19],   # UF
    [3, 37],   # UL
    [1, 46],   # UB
    [32, 16],  # DR
    [28, 25],  # DF
    [30, 43],  # DL
    [34, 52],  # DB
    [23, 12],  # FR
    [21, 41],  # FL
    [50, 39],  # BL
    [48, 14],  # BR
]

CORNER_COLORS = [
    ["U", "R", "F"],
    ["U", "F", "L"],
    ["U", "L", "B"],
    ["U", "B", "R"],
    ["D", "F", "R"],
    ["D", "L", "F"],
    ["D", "B", "L"],
    ["D", "R", "B"],
]

EDGE_COLORS = [
    ["U", "R"],
    ["U", "F"],
    ["U", "L"],
    ["U", "B"],
    ["D", "R"],
    ["D", "F"],
    ["D", "L"],
    ["D", "B"],
    ["F", "R"],
    ["F", "L"],
    ["B", "L"],
    ["B", "R"],
]


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    facelets: str
    corner_perm: list[int] | None
    corner_ori: list[int] | None
    edge_perm: list[int] | None
    edge_ori: list[int] | None
    corner_twist_ok: bool
    edge_flip_ok: bool
    parity_ok: bool
    solver_ready: bool


@dataclass
class ParsedCubies:
    corner_perm: list[int]
    corner_ori: list[int]
    edge_perm: list[int]
    edge_ori: list[int]


def permutation_parity(perm: list[int]) -> int:
    """Return 0 for even parity, 1 for odd parity."""
    inversions = 0
    for i in range(len(perm)):
        for j in range(i + 1, len(perm)):
            if perm[i] > perm[j]:
                inversions += 1
    return inversions % 2


def parse_facelets_to_cubies(facelets: str) -> ParsedCubies:
    basic_errors = _validate_basic_facelets(facelets)
    if basic_errors:
        raise ValueError("; ".join(basic_errors))

    parsed, parse_errors = _parse_facelets_to_cubies(facelets)
    if parsed is None or parse_errors:
        raise ValueError("; ".join(parse_errors))
    return parsed


def validate_facelet_string(facelets: str) -> ValidationResult:
    errors = _validate_basic_facelets(facelets)
    if errors:
        return _build_result(facelets=facelets, errors=errors)

    parsed, parse_errors = _parse_facelets_to_cubies(facelets)
    errors.extend(parse_errors)

    corner_twist_ok = False
    edge_flip_ok = False
    parity_ok = False

    if parsed is not None:
        corner_twist = sum(parsed.corner_ori) % 3
        edge_flip = sum(parsed.edge_ori) % 2
        corner_twist_ok = corner_twist == 0
        edge_flip_ok = edge_flip == 0

        if not corner_twist_ok:
            errors.append(f"Corner twist sum invalid: {corner_twist} mod 3")
        if not edge_flip_ok:
            errors.append(f"Edge flip sum invalid: {edge_flip} mod 2")

        corner_parity = permutation_parity(parsed.corner_perm)
        edge_parity = permutation_parity(parsed.edge_perm)
        parity_ok = corner_parity == edge_parity
        if not parity_ok:
            errors.append("Permutation parity mismatch between corners and edges")

    return _build_result(
        facelets=facelets,
        errors=errors,
        corner_perm=None if parsed is None else parsed.corner_perm,
        corner_ori=None if parsed is None else parsed.corner_ori,
        edge_perm=None if parsed is None else parsed.edge_perm,
        edge_ori=None if parsed is None else parsed.edge_ori,
        corner_twist_ok=corner_twist_ok,
        edge_flip_ok=edge_flip_ok,
        parity_ok=parity_ok,
    )


def validate_cube_state(cube_state) -> ValidationResult:
    try:
        facelets = cube_state.to_facelet_string()
    except Exception as exc:
        return _build_result(
            facelets="",
            errors=[f"Could not export facelet string: {exc}"],
        )
    return validate_facelet_string(facelets)


def _build_result(
    facelets: str,
    errors: list[str],
    corner_perm: list[int] | None = None,
    corner_ori: list[int] | None = None,
    edge_perm: list[int] | None = None,
    edge_ori: list[int] | None = None,
    corner_twist_ok: bool = False,
    edge_flip_ok: bool = False,
    parity_ok: bool = False,
) -> ValidationResult:
    is_valid = len(errors) == 0
    return ValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=[],
        facelets=facelets,
        corner_perm=corner_perm,
        corner_ori=corner_ori,
        edge_perm=edge_perm,
        edge_ori=edge_ori,
        corner_twist_ok=corner_twist_ok,
        edge_flip_ok=edge_flip_ok,
        parity_ok=parity_ok,
        solver_ready=is_valid,
    )


def _validate_basic_facelets(facelets: str) -> list[str]:
    errors: list[str] = []

    if len(facelets) != 54:
        return [f"Facelet string must have length 54, got {len(facelets)}"]

    invalid_chars = set(facelets) - VALID_FACELETS
    if invalid_chars:
        errors.append(f"Invalid facelet characters: {invalid_chars}")

    count_errors = []
    for facelet in ["U", "R", "F", "D", "L", "B"]:
        count = facelets.count(facelet)
        if count != 9:
            count_errors.append(f"{facelet}={count}")
    if count_errors:
        errors.append(f"Facelet counts invalid: {', '.join(count_errors)}")

    return errors


def _parse_facelets_to_cubies(facelets: str) -> tuple[ParsedCubies | None, list[str]]:
    errors: list[str] = []
    corner_perm = [-1] * 8
    corner_ori = [-1] * 8
    edge_perm = [-1] * 12
    edge_ori = [-1] * 12
    parse_failed = False

    # Corner parsing follows the standard FaceCube convention:
    # find where the U/D sticker sits, then match the remaining two colors.
    for position_index, facelet_indices in enumerate(CORNER_FACELETS):
        colors = [facelets[index] for index in facelet_indices]
        orientation = next((ori for ori, color in enumerate(colors) if color in UD_FACELETS), None)
        if orientation is None:
            errors.append(
                f"Unrecognized corner colors at position {CORNER_NAMES[position_index]}: {colors}"
            )
            parse_failed = True
            continue

        c1 = colors[(orientation + 1) % 3]
        c2 = colors[(orientation + 2) % 3]
        cubie_index = next(
            (
                j
                for j, cubie_colors in enumerate(CORNER_COLORS)
                if cubie_colors[1] == c1 and cubie_colors[2] == c2
            ),
            None,
        )

        if cubie_index is None:
            errors.append(
                f"Unrecognized corner colors at position {CORNER_NAMES[position_index]}: {colors}"
            )
            parse_failed = True
            continue

        corner_perm[position_index] = cubie_index
        corner_ori[position_index] = orientation

    # Edge parsing is direct: exact order means orientation 0, reversed means 1.
    for position_index, facelet_indices in enumerate(EDGE_FACELETS):
        colors = [facelets[index] for index in facelet_indices]
        cubie_index = None
        orientation = None

        for j, cubie_colors in enumerate(EDGE_COLORS):
            if colors == cubie_colors:
                cubie_index = j
                orientation = 0
                break
            if colors == cubie_colors[::-1]:
                cubie_index = j
                orientation = 1
                break

        if cubie_index is None or orientation is None:
            errors.append(
                f"Unrecognized edge colors at position {EDGE_NAMES[position_index]}: {colors}"
            )
            parse_failed = True
            continue

        edge_perm[position_index] = cubie_index
        edge_ori[position_index] = orientation

    if parse_failed:
        return None, errors

    _append_duplicate_and_missing_errors(
        perm=corner_perm,
        cubie_names=CORNER_NAMES,
        piece_label="corner",
        errors=errors,
    )
    _append_duplicate_and_missing_errors(
        perm=edge_perm,
        cubie_names=EDGE_NAMES,
        piece_label="edge",
        errors=errors,
    )

    return ParsedCubies(
        corner_perm=corner_perm,
        corner_ori=corner_ori,
        edge_perm=edge_perm,
        edge_ori=edge_ori,
    ), errors


def _append_duplicate_and_missing_errors(
    perm: list[int],
    cubie_names: list[str],
    piece_label: str,
    errors: list[str],
) -> None:
    seen: set[int] = set()
    duplicates_reported: set[int] = set()

    for cubie_index in perm:
        if cubie_index in seen and cubie_index not in duplicates_reported:
            errors.append(f"Duplicate {piece_label} cubie detected: {cubie_names[cubie_index]}")
            duplicates_reported.add(cubie_index)
        else:
            seen.add(cubie_index)

    for cubie_index, cubie_name in enumerate(cubie_names):
        if cubie_index not in seen:
            errors.append(f"Missing {piece_label} cubie: {cubie_name}")
