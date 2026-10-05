from __future__ import annotations

import math
from collections import Counter, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from numbers import Real
from typing import Any

import cv2
import numpy as np


DISPLAY_MAP = {
    "WHITE": (255, 255, 255),
    "YELLOW": (0, 255, 255),
    "RED": (0, 0, 255),
    "ORANGE": (0, 165, 255),
    "BLUE": (255, 0, 0),
    "GREEN": (0, 255, 0),
    "UNKNOWN": (128, 128, 128),
}

HISTORY_LENGTH = 7
STABLE_MIN_COUNT = 5


def normalize_bgr(value: Sequence[Any], *, field_name: str = "BGR sample") -> list[int]:
    if isinstance(value, (str, bytes)) or not hasattr(value, "__len__") or len(value) != 3:
        raise ValueError(f"{field_name} must contain exactly three values.")
    normalized: list[int] = []
    for component in value:
        if isinstance(component, (bool, np.bool_)) or not isinstance(component, Real):
            raise ValueError(f"{field_name} values must be numbers.")
        numeric = float(component)
        if not math.isfinite(numeric) or numeric < 0 or numeric > 255:
            raise ValueError(f"{field_name} values must be finite numbers from 0 to 255.")
        normalized.append(int(round(numeric)))
    return normalized


def validate_sample_grid(samples: Any) -> list[list[list[int]]]:
    if not isinstance(samples, list) or len(samples) != 3:
        raise ValueError("samples must be a 3x3 array.")
    result: list[list[list[int]]] = []
    for row_index, row in enumerate(samples):
        if not isinstance(row, list) or len(row) != 3:
            raise ValueError("samples must be a 3x3 array.")
        result.append(
            [normalize_bgr(sample, field_name=f"samples[{row_index}][{col_index}]") for col_index, sample in enumerate(row)]
        )
    return result


def median_bgr_from_patch(patch: np.ndarray) -> np.ndarray:
    if patch.size == 0:
        return np.array([0, 0, 0], dtype=np.uint8)
    pixels = patch.reshape(-1, 3)
    return np.median(pixels, axis=0).astype(np.uint8)


def bgr_to_lab(bgr: Sequence[Any]) -> np.ndarray:
    normalized = normalize_bgr(bgr)
    arr = np.uint8([[normalized]])
    return cv2.cvtColor(arr, cv2.COLOR_BGR2LAB)[0][0].astype(np.float32)


def bgr_to_hsv(bgr: Sequence[Any]) -> np.ndarray:
    normalized = normalize_bgr(bgr)
    arr = np.uint8([[normalized]])
    return cv2.cvtColor(arr, cv2.COLOR_BGR2HSV)[0][0].astype(np.int32)


def color_distance_lab(bgr1: Sequence[Any], bgr2: Sequence[Any]) -> float:
    return float(np.linalg.norm(bgr_to_lab(bgr1) - bgr_to_lab(bgr2)))


def classify_from_calibration(
    bgr: Sequence[Any],
    calibration: Mapping[str, Sequence[Any]],
) -> tuple[str, tuple[int, int, int], str]:
    normalized = normalize_bgr(bgr)
    hsv = bgr_to_hsv(normalized)
    h, s, v = (int(hsv[0]), int(hsv[1]), int(hsv[2]))

    if s < 45 and v > 120:
        return "WHITE", DISPLAY_MAP["WHITE"], f"S:{s} V:{v}"

    if not calibration:
        return "UNKNOWN", DISPLAY_MAP["UNKNOWN"], f"H:{h} S:{s} V:{v}"

    best_name: str | None = None
    best_dist = float("inf")
    for color_name, reference in calibration.items():
        if color_name not in DISPLAY_MAP:
            continue
        distance = color_distance_lab(normalized, reference)
        if distance < best_dist:
            best_name = color_name
            best_dist = distance

    if best_name is None:
        return "UNKNOWN", DISPLAY_MAP["UNKNOWN"], f"H:{h} S:{s} V:{v}"
    return best_name, DISPLAY_MAP[best_name], f"D:{best_dist:.1f}"


def get_stable_label(history: Sequence[str], min_count: int = STABLE_MIN_COUNT) -> tuple[str, bool]:
    if not history:
        return "UNKNOWN", False
    label, count = Counter(history).most_common(1)[0]
    return label, count >= min_count


def all_face_stable(stable_grid: Sequence[Sequence[tuple[str, bool]]]) -> bool:
    return all(stable_grid[row][col][1] for row in range(3) for col in range(3))


def extract_stable_face_grid(stable_grid: Sequence[Sequence[tuple[str, bool]]]) -> list[list[str]]:
    return [[stable_grid[row][col][0] for col in range(3)] for row in range(3)]


def reset_sticker_history(maxlen: int = HISTORY_LENGTH) -> list[list[deque[str]]]:
    return [[deque(maxlen=maxlen) for _ in range(3)] for _ in range(3)]


@dataclass
class RecognitionTracker:
    history_length: int = HISTORY_LENGTH
    stable_min_count: int = STABLE_MIN_COUNT
    histories: list[list[deque[str]]] = field(init=False)

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.histories = reset_sticker_history(self.history_length)

    def classify(
        self,
        samples: list[list[list[int]]],
        calibration: Mapping[str, Sequence[Any]],
    ) -> tuple[list[list[str]], list[list[tuple[str, bool]]]]:
        live_grid: list[list[str]] = [["UNKNOWN"] * 3 for _ in range(3)]
        stable_grid: list[list[tuple[str, bool]]] = [[("UNKNOWN", False)] * 3 for _ in range(3)]
        for row in range(3):
            for col in range(3):
                label, _display, _debug = classify_from_calibration(samples[row][col], calibration)
                live_grid[row][col] = label
                self.histories[row][col].append(label)
                stable_grid[row][col] = get_stable_label(
                    self.histories[row][col],
                    min_count=self.stable_min_count,
                )
        return live_grid, stable_grid
