from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass

from cube_backend.cfop_analyzer import CFOPAnalysis, analyze_cfop
from cube_backend.cubie_model import CubieCube
from cube_backend.f2l_cases import F2LCase, classify_all_f2l_cases
from cube_backend.move_utils import normalize_move_token, parse_alg
from cube_backend.playback_session import load_playback_session
from cube_backend.validator import (
    CORNER_COLORS,
    CORNER_FACELETS,
    CORNER_NAMES,
    EDGE_COLORS,
    EDGE_FACELETS,
    EDGE_NAMES,
)
from cube_backend.viewer_snapshot import load_view_snapshot, validate_view_snapshot


SOLVED_FACELETS = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"

WHITE = (245, 245, 245)
YELLOW = (255, 230, 40)
RED = (210, 40, 40)
ORANGE = (255, 140, 30)
BLUE = (40, 90, 220)
GREEN = (40, 170, 70)
UNKNOWN = (120, 120, 120)
PLASTIC = (25, 25, 25)
BG = (18, 18, 22)
OUTLINE = (10, 10, 10)
OVERLAY_BG = (0, 0, 0, 150)

FACELET_ORDER = ["U", "R", "F", "D", "L", "B"]
FACELET_TO_COLOR_NAME = {
    "U": "WHITE",
    "R": "RED",
    "F": "GREEN",
    "D": "YELLOW",
    "L": "ORANGE",
    "B": "BLUE",
}
COLOR_NAME_TO_RGB = {
    "WHITE": WHITE,
    "YELLOW": YELLOW,
    "RED": RED,
    "ORANGE": ORANGE,
    "BLUE": BLUE,
    "GREEN": GREEN,
    "UNKNOWN": UNKNOWN,
    None: UNKNOWN,
}

MODE_PARTIAL = "PARTIAL"
MODE_PLAYBACK = "PLAYBACK"
FACE_NAMES = ["U", "R", "F", "D", "L", "B"]
CUBE_HALF_EXTENT = 1.0
ROTATE_SENSITIVITY = 0.45
ZOOM_STEP = 0.35
MAX_PITCH_DEG = 89.0
DEFAULT_ANIMATION_SPEED = 180.0
MIN_ANIMATION_SPEED = 60.0
MAX_ANIMATION_SPEED = 720.0
PLASTIC_INSET = 0.03
STICKER_SURFACE_LIFT = 0.014
PLASTIC_SURFACE_SINK = 0.006

FACE_CENTER_FACELETS = {
    "U": 4,
    "R": 13,
    "F": 22,
    "D": 31,
    "L": 40,
    "B": 49,
}

# Face axes are explicit so orientation is easy to audit.
FACE_TO_AXIS_INFO = {
    "U": {"normal": (0.0, 1.0, 0.0), "up": (0.0, 0.0, -1.0)},
    "R": {"normal": (1.0, 0.0, 0.0), "up": (0.0, 1.0, 0.0)},
    "F": {"normal": (0.0, 0.0, 1.0), "up": (0.0, 1.0, 0.0)},
    "D": {"normal": (0.0, -1.0, 0.0), "up": (0.0, 0.0, 1.0)},
    "L": {"normal": (-1.0, 0.0, 0.0), "up": (0.0, 1.0, 0.0)},
    "B": {"normal": (0.0, 0.0, -1.0), "up": (0.0, 1.0, 0.0)},
}

# The sign is the right-hand-rule turn around the face axis that matches
# a clockwise face turn when looking directly at that face.
FACE_CLOCKWISE_AXIS_TURNS = {
    "U": -1,
    "R": -1,
    "F": -1,
    "D": 1,
    "L": 1,
    "B": 1,
    "M": -1,
    "E": 1,
    "S": -1,
    "r": -1,
    "l": 1,
    "u": -1,
    "d": 1,
    "f": -1,
    "b": 1,
    "x": -1,
    "y": -1,
    "z": -1,
}

MOVE_AXIS_NAMES = {
    "U": "y",
    "D": "y",
    "E": "y",
    "u": "y",
    "d": "y",
    "y": "y",
    "R": "x",
    "L": "x",
    "M": "x",
    "r": "x",
    "l": "x",
    "x": "x",
    "F": "z",
    "B": "z",
    "S": "z",
    "f": "z",
    "b": "z",
    "z": "z",
}

# Animated layer membership is derived from cubie positions, not world-space floats.
LAYER_CORNER_POSITIONS = {
    "U": [0, 1, 2, 3],
    "R": [0, 3, 4, 7],
    "F": [0, 1, 4, 5],
    "D": [4, 5, 6, 7],
    "L": [1, 2, 5, 6],
    "B": [2, 3, 6, 7],
    "M": [],
    "E": [],
    "S": [],
    "r": [0, 3, 4, 7],
    "l": [1, 2, 5, 6],
    "u": [0, 1, 2, 3],
    "d": [4, 5, 6, 7],
    "f": [0, 1, 4, 5],
    "b": [2, 3, 6, 7],
    "x": list(range(8)),
    "y": list(range(8)),
    "z": list(range(8)),
}
LAYER_EDGE_POSITIONS = {
    "U": [0, 1, 2, 3],
    "R": [0, 4, 8, 11],
    "F": [1, 5, 8, 9],
    "D": [4, 5, 6, 7],
    "L": [2, 6, 9, 10],
    "B": [3, 7, 10, 11],
    "M": [1, 3, 5, 7],
    "E": [8, 9, 10, 11],
    "S": [0, 2, 4, 6],
    "r": [0, 1, 3, 4, 5, 7, 8, 11],
    "l": [1, 2, 3, 5, 6, 7, 9, 10],
    "u": [0, 1, 2, 3, 8, 9, 10, 11],
    "d": [4, 5, 6, 7, 8, 9, 10, 11],
    "f": [0, 1, 2, 4, 5, 6, 8, 9],
    "b": [0, 2, 3, 4, 6, 7, 10, 11],
    "x": list(range(12)),
    "y": list(range(12)),
    "z": list(range(12)),
}
LAYER_CENTER_FACES = {
    "U": {"U"},
    "R": {"R"},
    "F": {"F"},
    "D": {"D"},
    "L": {"L"},
    "B": {"B"},
    "M": set(),
    "E": set(),
    "S": set(),
    "r": {"R"},
    "l": {"L"},
    "u": {"U"},
    "d": {"D"},
    "f": {"F"},
    "b": {"B"},
    "x": {"U", "R", "F", "D", "L", "B"},
    "y": {"U", "R", "F", "D", "L", "B"},
    "z": {"U", "R", "F", "D", "L", "B"},
}


Point3D = tuple[float, float, float]
Point2D = tuple[int, int]


@dataclass
class ViewerConfig:
    width: int = 960
    height: int = 720
    bg_color: tuple[int, int, int] = BG
    cube_scale: float = 900.0
    sticker_inset: float = 0.12
    zoom: float = 5.8
    min_zoom: float = 3.5
    max_zoom: float = 9.5
    yaw_deg: float = -35.0
    pitch_deg: float = 25.0
    title: str = "Rubik Cube 3D Viewer"


@dataclass
class ActiveAnimation:
    move: str
    progress: float


@dataclass
class PlaybackStage:
    name: str
    start_index: int
    end_index: int
    rotation_prompt: str = ""
    display_moves: str = ""
    description: str = ""


@dataclass
class FaceletGeometry:
    facelet_index: int
    face_name: str
    row: int
    col: int
    quad_points_local: list[Point3D]


@dataclass
class StickerState:
    sticker_id: str
    color_name: str
    color_rgb: tuple[int, int, int]
    cubie_type: str
    cubie_index: int
    local_face: str
    quad_points_local: list[Point3D]
    is_partial_unknown: bool
    facelet_index: int
    position_name: str
    position_index: int
    world_face: str


@dataclass
class RenderQuad:
    sticker_id: str
    color_rgb: tuple[int, int, int]
    points_world: list[Point3D]
    points_screen: list[Point2D]
    depth: float
    draw_kind: str
    color_name: str
    is_partial_unknown: bool
    normal_world: Point3D


class CubeViewer3D:
    def __init__(
        self,
        snapshot: dict | None = None,
        config: ViewerConfig | None = None,
        facelets: str | None = None,
        moves: list[str] | None = None,
        playback_stages: list[dict] | None = None,
        playback_setup_text: str = "",
        title: str | None = None,
    ):
        if snapshot is None and facelets is None:
            raise ValueError("CubeViewer3D needs either a snapshot or a facelet string.")
        if snapshot is not None and facelets is not None:
            raise ValueError("Provide either snapshot or facelets, not both.")

        self.config = config or ViewerConfig()
        self.title = title or self.config.title
        self.yaw_deg = self.config.yaw_deg
        self.pitch_deg = self.config.pitch_deg
        self.zoom = self.config.zoom
        self._default_yaw_deg = self.config.yaw_deg
        self._default_pitch_deg = self.config.pitch_deg
        self._default_zoom = self.config.zoom
        self._dragging = False
        self._last_mouse_pos: tuple[int, int] | None = None
        self._pygame = None
        self._screen = None
        self._clock = None
        self._font = None
        self._small_font = None
        self._debug_overlay_enabled = False
        self._last_render_stats = {
            "mode": MODE_PARTIAL,
            "sticker_quad_count": 0,
            "gray_sticker_count": 0,
        }
        self._last_gray_warning_signature: tuple | None = None
        self._cfop_overlay_enabled = False
        self._cached_cfop_analysis: CFOPAnalysis | None = None
        self._cached_f2l_cases: list[F2LCase] = []
        self._cfop_error: str | None = None

        self.render_mode: str
        self.static_snapshot: dict | None = None
        self.initial_cube: CubieCube | None = None
        self.current_cube: CubieCube | None = None

        self.moves = [normalize_move_token(move) for move in (moves or [])]
        self.move_index = 0
        self.playing = False
        self.animation_progress = 0.0
        self.current_anim_move: str | None = None
        self.animation_speed_deg_per_sec = DEFAULT_ANIMATION_SPEED
        self._animate_once = False
        self.playback_stages = [
            PlaybackStage(
                name=stage["name"],
                start_index=stage["start_index"],
                end_index=stage["end_index"],
                rotation_prompt=stage.get("rotation_prompt", ""),
                display_moves=stage.get("display_moves", ""),
                description=stage.get("description", ""),
            )
            for stage in (playback_stages or [])
        ]
        self.playback_setup_text = playback_setup_text

        if facelets is not None:
            self.render_mode = MODE_PLAYBACK
            self.initial_cube = CubieCube.from_facelet_string(facelets)
            self.current_cube = self.initial_cube.copy()
            self._refresh_cfop_analysis()
        else:
            if self.moves:
                raise ValueError("Partial snapshot mode does not support animated moves.")
            is_valid, errors = validate_view_snapshot(snapshot)
            if not is_valid:
                raise ValueError("; ".join(errors))
            self.render_mode = MODE_PARTIAL
            self.static_snapshot = snapshot

    def run(self) -> None:
        pygame = _import_pygame()
        if pygame is None:
            return

        self._pygame = pygame
        pygame.init()
        pygame.display.set_caption(self.title)
        self._screen = pygame.display.set_mode((self.config.width, self.config.height))
        self._clock = pygame.time.Clock()
        self._font = pygame.font.SysFont("arial", 18)
        self._small_font = pygame.font.SysFont("arial", 15)

        running = True
        while running:
            dt_seconds = self._clock.tick(60) / 1000.0

            for event in pygame.event.get():
                running = self.handle_event(event) and running

            self._update_animation(dt_seconds)
            self.draw_scene()
            pygame.display.flip()

        pygame.quit()

    def reset_view(self) -> None:
        self.yaw_deg = self._default_yaw_deg
        self.pitch_deg = self._default_pitch_deg
        self.zoom = self._default_zoom

    def build_world_render_quads(self) -> list[RenderQuad]:
        if self.render_mode == MODE_PLAYBACK:
            if self.current_cube is None:
                raise ValueError("Playback mode requires a current cube state.")
            return build_render_quads_from_cubie_cube(
                self.current_cube,
                config=self.config,
                active_animation=self._get_active_animation(),
            )

        if self.static_snapshot is None:
            raise ValueError("Partial mode requires a snapshot.")
        return build_render_quads_from_snapshot(self.static_snapshot, config=self.config)

    def build_visible_render_quads(self) -> list[RenderQuad]:
        world_quads = self.build_world_render_quads()
        summary = summarize_render_quads(world_quads)
        summary["mode"] = self.render_mode
        self._last_render_stats = summary
        self._warn_if_playback_has_gray(summary)

        return project_render_quads(
            world_quads,
            yaw_deg=self.yaw_deg,
            pitch_deg=self.pitch_deg,
            config=self.config,
            zoom=self.zoom,
        )

    def draw_scene(self) -> None:
        pygame = self._pygame
        screen = self._screen
        if pygame is None or screen is None:
            return

        screen.fill(self.config.bg_color)

        render_quads = self.build_visible_render_quads()
        for quad in sorted(render_quads, key=_render_sort_key, reverse=True):
            pygame.draw.polygon(screen, quad.color_rgb, quad.points_screen)
            outline_width = 2 if quad.draw_kind == "plastic" else 1
            pygame.draw.polygon(screen, OUTLINE, quad.points_screen, outline_width)

        self.draw_overlay()

    def draw_overlay(self) -> None:
        pygame = self._pygame
        screen = self._screen
        if pygame is None or screen is None or self._font is None or self._small_font is None:
            return

        current_move = self.current_anim_move or self._next_move_token()
        display_move_index = self.move_index + (1 if self.current_anim_move else 0)
        playback_label = "Playing" if self.playing else "Paused"
        current_stage_name = self._current_playback_stage_name()
        current_stage_progress = self._current_playback_stage_progress()
        current_stage = self._current_playback_stage()

        overlay_lines = [self.title]
        if self.render_mode == MODE_PLAYBACK:
            overlay_lines.append(self.playback_setup_text or "Hold the cube with WHITE on bottom and GREEN facing you.")
        overlay_lines.extend(
            [
                f"Move {display_move_index} / {len(self.moves)}",
                f"Stage: {current_stage_name}",
                current_stage_progress,
                f"Current move: {current_move or '--'}",
                f"{playback_label}   Speed {self.animation_speed_deg_per_sec:.0f} deg/s",
                "Left drag: rotate   Wheel: zoom",
                "SPACE play/pause   LEFT/RIGHT step",
                "HOME reset solve   END jump to end",
                "UP/DOWN speed   R reset camera   C CFOP   G debug   ESC close",
            ]
        )

        if current_stage is not None and current_stage.rotation_prompt:
            overlay_lines.append(f"Rotate: {current_stage.rotation_prompt}")
        if current_stage is not None and current_stage.display_moves:
            overlay_lines.append(f"Alg: {current_stage.display_moves}")
        if current_stage is not None and current_stage.description:
            overlay_lines.append(current_stage.description)

        if self._cfop_overlay_enabled:
            overlay_lines.extend(self._cfop_overlay_lines())

        if self._debug_overlay_enabled:
            overlay_lines.extend(
                [
                    f"Mode: {self._last_render_stats['mode']}",
                    f"Sticker quads: {self._last_render_stats['sticker_quad_count']}",
                    f"Gray stickers: {self._last_render_stats['gray_sticker_count']}",
                ]
            )

        padding = 10
        line_height = 21
        overlay_width = 440 if self._cfop_overlay_enabled else 360
        overlay_height = padding * 2 + line_height * len(overlay_lines)

        overlay = pygame.Surface((overlay_width, overlay_height), pygame.SRCALPHA)
        overlay.fill(OVERLAY_BG)
        screen.blit(overlay, (16, 16))

        for index, text in enumerate(overlay_lines):
            font = self._font if index < 5 else self._small_font
            text_surface = font.render(text, True, WHITE)
            screen.blit(text_surface, (16 + padding, 16 + padding + index * line_height))

    def handle_event(self, event) -> bool:
        pygame = self._pygame
        if pygame is None:
            return False

        if event.type == pygame.QUIT:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False
            if event.key == pygame.K_r:
                self.reset_view()
            elif event.key == pygame.K_c:
                self._cfop_overlay_enabled = not self._cfop_overlay_enabled
            elif event.key == pygame.K_g:
                self._debug_overlay_enabled = not self._debug_overlay_enabled
            elif event.key == pygame.K_SPACE:
                self._toggle_play_pause()
            elif event.key == pygame.K_RIGHT:
                self._step_forward()
            elif event.key == pygame.K_LEFT:
                self._step_backward()
            elif event.key == pygame.K_HOME:
                self._jump_to_start()
            elif event.key == pygame.K_END:
                self._jump_to_end()
            elif event.key == pygame.K_UP:
                self.animation_speed_deg_per_sec = _clamp(
                    self.animation_speed_deg_per_sec + 30.0,
                    MIN_ANIMATION_SPEED,
                    MAX_ANIMATION_SPEED,
                )
            elif event.key == pygame.K_DOWN:
                self.animation_speed_deg_per_sec = _clamp(
                    self.animation_speed_deg_per_sec - 30.0,
                    MIN_ANIMATION_SPEED,
                    MAX_ANIMATION_SPEED,
                )

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self._dragging = True
                self._last_mouse_pos = event.pos
            elif event.button == 4:
                self._adjust_zoom(-ZOOM_STEP)
            elif event.button == 5:
                self._adjust_zoom(ZOOM_STEP)

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False
            self._last_mouse_pos = None

        if event.type == pygame.MOUSEMOTION and self._dragging and self._last_mouse_pos is not None:
            dx = event.pos[0] - self._last_mouse_pos[0]
            dy = event.pos[1] - self._last_mouse_pos[1]
            self.yaw_deg += dx * ROTATE_SENSITIVITY
            self.pitch_deg = _clamp(
                self.pitch_deg + dy * ROTATE_SENSITIVITY,
                -MAX_PITCH_DEG,
                MAX_PITCH_DEG,
            )
            self._last_mouse_pos = event.pos

        if event.type == getattr(pygame, "MOUSEWHEEL", -1):
            self._adjust_zoom(-event.y * ZOOM_STEP)

        return True

    def _adjust_zoom(self, delta: float) -> None:
        self.zoom = _clamp(self.zoom + delta, self.config.min_zoom, self.config.max_zoom)

    def _toggle_play_pause(self) -> None:
        if not self.moves or self.current_cube is None:
            return

        self.playing = not self.playing
        if self.playing and self.current_anim_move is None and self.move_index < len(self.moves):
            self._start_current_move_animation()

    def _step_forward(self) -> None:
        if not self.moves or self.current_cube is None:
            return

        self.playing = False
        if self.current_anim_move is not None:
            self._commit_current_animation()
            return

        if self.move_index >= len(self.moves):
            return

        self._start_current_move_animation()
        self._animate_once = True

    def _step_backward(self) -> None:
        if not self.moves or self.current_cube is None:
            return

        self.playing = False
        self._animate_once = False

        if self.current_anim_move is not None:
            self.current_anim_move = None
            self.animation_progress = 0.0
            return

        if self.move_index == 0:
            return

        self._set_move_index(self.move_index - 1)

    def _jump_to_start(self) -> None:
        if self.current_cube is None:
            return
        self.playing = False
        self._animate_once = False
        self._set_move_index(0)

    def _jump_to_end(self) -> None:
        if self.current_cube is None:
            return
        self.playing = False
        self._animate_once = False
        self._set_move_index(len(self.moves))

    def _set_move_index(self, new_index: int) -> None:
        if self.initial_cube is None or self.current_cube is None:
            return

        self.current_cube = self.initial_cube.copy()
        self.current_cube.apply_alg(self.moves[:new_index])
        self.move_index = new_index
        self.current_anim_move = None
        self.animation_progress = 0.0
        self._refresh_cfop_analysis()

    def _start_current_move_animation(self) -> None:
        if self.move_index >= len(self.moves):
            self.current_anim_move = None
            return

        self.current_anim_move = self.moves[self.move_index]
        self.animation_progress = 0.0

    def _update_animation(self, dt_seconds: float) -> None:
        if self.current_cube is None or not self.moves:
            return

        if self.current_anim_move is None:
            if self.playing and self.move_index < len(self.moves):
                self._start_current_move_animation()
            return

        if not self.playing and not self._animate_once:
            return

        total_angle = abs(_move_total_angle(self.current_anim_move))
        if total_angle == 0.0:
            self._commit_current_animation()
            return

        self.animation_progress += (self.animation_speed_deg_per_sec * dt_seconds) / total_angle
        if self.animation_progress >= 1.0:
            self._commit_current_animation()

    def _commit_current_animation(self) -> None:
        if self.current_cube is None or self.current_anim_move is None:
            return

        self.current_cube.apply_move(self.current_anim_move)
        self.move_index += 1
        self.current_anim_move = None
        self.animation_progress = 0.0
        self._refresh_cfop_analysis()

        if self._animate_once:
            self._animate_once = False

        if self.move_index >= len(self.moves):
            self.playing = False
        elif self.playing:
            self._start_current_move_animation()

    def _next_move_token(self) -> str | None:
        if self.current_anim_move is not None:
            return self.current_anim_move
        if self.move_index < len(self.moves):
            return self.moves[self.move_index]
        return None

    def _get_active_animation(self) -> ActiveAnimation | None:
        if self.current_anim_move is None:
            return None
        return ActiveAnimation(move=self.current_anim_move, progress=self.animation_progress)

    def _warn_if_playback_has_gray(self, summary: dict[str, int | str]) -> None:
        if summary["mode"] != MODE_PLAYBACK:
            return
        if summary["gray_sticker_count"] == 0:
            self._last_gray_warning_signature = None
            return

        signature = (
            self.move_index,
            self.current_anim_move,
            summary["gray_sticker_count"],
            summary["sticker_quad_count"],
        )
        if signature != self._last_gray_warning_signature:
            print(
                "WARNING: playback mode rendered gray stickers "
                f"({summary['gray_sticker_count']} of {summary['sticker_quad_count']})."
            )
            self._last_gray_warning_signature = signature

    def _refresh_cfop_analysis(self) -> None:
        if self.current_cube is None:
            self._cached_cfop_analysis = None
            self._cached_f2l_cases = []
            self._cfop_error = None
            return

        try:
            self._cached_cfop_analysis = analyze_cfop(self.current_cube)
            self._cached_f2l_cases = classify_all_f2l_cases(self._cached_cfop_analysis.f2l_pairs)
            self._cfop_error = None
        except Exception as exc:
            self._cached_cfop_analysis = None
            self._cached_f2l_cases = []
            self._cfop_error = str(exc)

    def _cfop_overlay_lines(self) -> list[str]:
        if self.render_mode != MODE_PLAYBACK:
            return ["CFOP: unavailable in partial snapshot mode"]

        if self._cfop_error:
            return [f"CFOP error: {self._cfop_error}"]

        if self._cached_cfop_analysis is None:
            return ["CFOP: no analysis available"]

        analysis = self._cached_cfop_analysis
        lines = [
            f"White Cross: {analysis.cross.solved_count}/4   F2L: {analysis.f2l_slots_solved}/4",
            f"OLL (Yellow): {'yes' if analysis.oll_solved else 'no'}   PLL (Yellow): {'yes' if analysis.pll_solved else 'no'}",
            f"Stage: {_cfop_stage_hint(analysis)}",
        ]
        for f2l_case in self._cached_f2l_cases:
            lines.append(f"{f2l_case.slot}: {f2l_case.code}")
        return lines

    def _current_playback_stage_name(self) -> str:
        current_stage = self._current_playback_stage()
        if current_stage is None:
            if self.render_mode == MODE_PLAYBACK and self._cached_cfop_analysis is not None:
                return _cfop_stage_hint(self._cached_cfop_analysis)
            return "Static View"
        return current_stage.name

    def _current_playback_stage(self) -> PlaybackStage | None:
        if not self.playback_stages:
            return None

        if self.current_anim_move is not None:
            active_index = self.move_index
        else:
            active_index = self.move_index

        for stage in self.playback_stages:
            if stage.start_index <= active_index < stage.end_index:
                return stage

        if active_index >= len(self.moves):
            for stage in reversed(self.playback_stages):
                if stage.end_index <= active_index:
                    return stage

        for stage in self.playback_stages:
            if stage.start_index >= active_index:
                return stage

        return self.playback_stages[-1]

    def _current_playback_stage_progress(self) -> str:
        if not self.playback_stages:
            return "CFOP Progress: n/a"

        active_index = self.move_index
        for stage_number, stage in enumerate(self.playback_stages, start=1):
            if stage.start_index <= active_index < stage.end_index:
                return f"CFOP Progress: {stage_number} / {len(self.playback_stages)}"

        if active_index >= len(self.moves):
            return f"CFOP Progress: {len(self.playback_stages)} / {len(self.playback_stages)}"

        return f"CFOP Progress: 1 / {len(self.playback_stages)}"


# ---------------------------------------------------------------------------
# Pure render-preparation helpers
# ---------------------------------------------------------------------------

def build_sticker_states_from_snapshot(
    snapshot: dict,
    config: ViewerConfig | None = None,
) -> list[StickerState]:
    is_valid, errors = validate_view_snapshot(snapshot)
    if not is_valid:
        raise ValueError("; ".join(errors))

    viewer_config = config or ViewerConfig()
    geometry_lookup = build_facelet_geometry_lookup(viewer_config.sticker_inset)
    states: list[StickerState] = []

    for face_name in FACE_NAMES:
        for row in range(3):
            for col in range(3):
                facelet_index = facelet_index_from_face_row_col(face_name, row, col)
                geometry = geometry_lookup[facelet_index]
                raw_value = snapshot[face_name][row][col]
                normalized = _normalize_snapshot_color(raw_value)
                is_unknown = normalized == "UNKNOWN"

                states.append(
                    StickerState(
                        sticker_id=f"snapshot-{face_name}{row}{col}",
                        color_name=normalized,
                        color_rgb=COLOR_NAME_TO_RGB[normalized],
                        cubie_type=_cubie_type_from_face_position(row, col),
                        cubie_index=-1,
                        local_face=face_name,
                        quad_points_local=geometry.quad_points_local,
                        is_partial_unknown=is_unknown,
                        facelet_index=facelet_index,
                        position_name=f"{face_name}{row}{col}",
                        position_index=facelet_index,
                        world_face=face_name,
                    )
                )

    return states


def build_sticker_states_from_cubie_cube(
    cube: CubieCube,
    config: ViewerConfig | None = None,
) -> list[StickerState]:
    viewer_config = config or ViewerConfig()
    geometry_lookup = build_facelet_geometry_lookup(viewer_config.sticker_inset)
    states: list[StickerState] = []

    # The logical cube state stays in CubieCube. We derive render stickers from
    # cubie identity each frame so color never depends on temporary world pose.
    for position_index, facelet_indices in enumerate(CORNER_FACELETS):
        cubie_index = cube.corner_perm[position_index]
        orientation = cube.corner_ori[position_index]
        local_faces = CORNER_COLORS[cubie_index]
        mapped_facelets = [
            facelet_indices[orientation % 3],
            facelet_indices[(orientation + 1) % 3],
            facelet_indices[(orientation + 2) % 3],
        ]

        for local_face, facelet_index in zip(local_faces, mapped_facelets):
            geometry = geometry_lookup[facelet_index]
            color_name = FACELET_TO_COLOR_NAME[local_face]
            states.append(
                StickerState(
                    sticker_id=f"corner-{cubie_index}-{local_face}",
                    color_name=color_name,
                    color_rgb=COLOR_NAME_TO_RGB[color_name],
                    cubie_type="corner",
                    cubie_index=cubie_index,
                    local_face=local_face,
                    quad_points_local=geometry.quad_points_local,
                    is_partial_unknown=False,
                    facelet_index=facelet_index,
                    position_name=CORNER_NAMES[position_index],
                    position_index=position_index,
                    world_face=geometry.face_name,
                )
            )

    for position_index, facelet_indices in enumerate(EDGE_FACELETS):
        cubie_index = cube.edge_perm[position_index]
        orientation = cube.edge_ori[position_index]
        local_faces = EDGE_COLORS[cubie_index]
        if orientation == 0:
            mapped_facelets = [facelet_indices[0], facelet_indices[1]]
        else:
            mapped_facelets = [facelet_indices[1], facelet_indices[0]]

        for local_face, facelet_index in zip(local_faces, mapped_facelets):
            geometry = geometry_lookup[facelet_index]
            color_name = FACELET_TO_COLOR_NAME[local_face]
            states.append(
                StickerState(
                    sticker_id=f"edge-{cubie_index}-{local_face}",
                    color_name=color_name,
                    color_rgb=COLOR_NAME_TO_RGB[color_name],
                    cubie_type="edge",
                    cubie_index=cubie_index,
                    local_face=local_face,
                    quad_points_local=geometry.quad_points_local,
                    is_partial_unknown=False,
                    facelet_index=facelet_index,
                    position_name=EDGE_NAMES[position_index],
                    position_index=position_index,
                    world_face=geometry.face_name,
                )
            )

    for center_index, face_name in enumerate(FACE_NAMES):
        facelet_index = FACE_CENTER_FACELETS[face_name]
        geometry = geometry_lookup[facelet_index]
        color_name = FACELET_TO_COLOR_NAME[face_name]
        states.append(
            StickerState(
                sticker_id=f"center-{face_name}",
                color_name=color_name,
                color_rgb=COLOR_NAME_TO_RGB[color_name],
                cubie_type="center",
                cubie_index=center_index,
                local_face=face_name,
                quad_points_local=geometry.quad_points_local,
                is_partial_unknown=False,
                facelet_index=facelet_index,
                position_name=face_name,
                position_index=center_index,
                world_face=face_name,
            )
        )

    validate_complete_sticker_states(states)
    return states


def build_render_quads_from_snapshot(
    snapshot: dict,
    config: ViewerConfig | None = None,
) -> list[RenderQuad]:
    sticker_states = build_sticker_states_from_snapshot(snapshot, config=config)
    return build_render_quads_from_sticker_states(
        sticker_states,
        config=config,
        active_animation=None,
        mode=MODE_PARTIAL,
    )


def build_render_quads_from_cubie_cube(
    cube: CubieCube,
    config: ViewerConfig | None = None,
    active_animation: ActiveAnimation | None = None,
) -> list[RenderQuad]:
    sticker_states = build_sticker_states_from_cubie_cube(cube, config=config)
    render_quads = build_render_quads_from_sticker_states(
        sticker_states,
        config=config,
        active_animation=active_animation,
        mode=MODE_PLAYBACK,
    )

    summary = summarize_render_quads(render_quads)
    if summary["sticker_quad_count"] != 54:
        raise ValueError(
            f"Playback render pipeline must produce 54 stickers, got {summary['sticker_quad_count']}"
        )
    if summary["gray_sticker_count"] != 0:
        raise ValueError(
            f"Playback render pipeline produced gray stickers: {summary['gray_sticker_count']}"
        )
    return render_quads


def build_render_quads_from_sticker_states(
    sticker_states: list[StickerState],
    config: ViewerConfig | None = None,
    active_animation: ActiveAnimation | None = None,
    mode: str = MODE_PARTIAL,
) -> list[RenderQuad]:
    viewer_config = config or ViewerConfig()
    plastic_geometry_lookup = build_facelet_geometry_lookup(PLASTIC_INSET)
    render_quads: list[RenderQuad] = []

    if mode == MODE_PLAYBACK:
        validate_complete_sticker_states(sticker_states)

    for state in sticker_states:
        face_normal = FACE_TO_AXIS_INFO[state.world_face]["normal"]
        # Stickers must sit slightly above the plastic bed. If both surfaces are
        # coplanar, the painter sort can flip their order and cause flashing.
        sticker_points = _offset_points_along_normal(
            state.quad_points_local,
            face_normal,
            STICKER_SURFACE_LIFT,
        )
        plastic_points = _offset_points_along_normal(
            plastic_geometry_lookup[state.facelet_index].quad_points_local,
            face_normal,
            -PLASTIC_SURFACE_SINK,
        )

        if active_animation is not None and sticker_state_is_in_layer(state, active_animation.move[0]):
            angle_deg = _move_total_angle(active_animation.move) * active_animation.progress
            axis_name = MOVE_AXIS_NAMES[active_animation.move[0]]
            sticker_points = [_rotate_point_about_axis(point, axis_name, angle_deg) for point in sticker_points]
            plastic_points = [_rotate_point_about_axis(point, axis_name, angle_deg) for point in plastic_points]
            face_normal = _rotate_point_about_axis(face_normal, axis_name, angle_deg)

        render_quads.append(
            RenderQuad(
                sticker_id=f"{state.sticker_id}-plastic",
                color_rgb=PLASTIC,
                points_world=plastic_points,
                points_screen=[],
                depth=0.0,
                draw_kind="plastic",
                color_name="PLASTIC",
                is_partial_unknown=False,
                normal_world=face_normal,
            )
        )
        render_quads.append(
            RenderQuad(
                sticker_id=state.sticker_id,
                color_rgb=state.color_rgb,
                points_world=sticker_points,
                points_screen=[],
                depth=0.0,
                draw_kind="sticker",
                color_name=state.color_name,
                is_partial_unknown=state.is_partial_unknown,
                normal_world=face_normal,
            )
        )

    return render_quads


def project_render_quads(
    render_quads: list[RenderQuad],
    yaw_deg: float,
    pitch_deg: float,
    config: ViewerConfig,
    zoom: float | None = None,
) -> list[RenderQuad]:
    active_zoom = config.zoom if zoom is None else zoom
    projected: list[RenderQuad] = []

    for quad in render_quads:
        rotated_normal = rotate_points_for_camera([quad.normal_world], yaw_deg, pitch_deg)[0]
        if rotated_normal[2] <= 0.0:
            continue

        rotated_points = rotate_points_for_camera(quad.points_world, yaw_deg, pitch_deg)
        points_screen = project_points_to_screen(
            rotated_points,
            width=config.width,
            height=config.height,
            cube_scale=config.cube_scale,
            zoom=active_zoom,
        )
        depth = sum(active_zoom - point[2] for point in rotated_points) / len(rotated_points)

        projected.append(
            RenderQuad(
                sticker_id=quad.sticker_id,
                color_rgb=quad.color_rgb,
                points_world=quad.points_world,
                points_screen=points_screen,
                depth=depth,
                draw_kind=quad.draw_kind,
                color_name=quad.color_name,
                is_partial_unknown=quad.is_partial_unknown,
                normal_world=quad.normal_world,
            )
        )

    return projected


def summarize_render_quads(render_quads: list[RenderQuad]) -> dict[str, int]:
    sticker_quads = [quad for quad in render_quads if quad.draw_kind == "sticker"]
    gray_count = sum(
        1
        for quad in sticker_quads
        if quad.color_name == "UNKNOWN" or quad.is_partial_unknown
    )
    return {
        "sticker_quad_count": len(sticker_quads),
        "gray_sticker_count": gray_count,
    }


def _cfop_stage_hint(analysis: CFOPAnalysis) -> str:
    if not analysis.cross.solved:
        return "White Cross incomplete"
    if analysis.f2l_slots_solved < 4:
        return "Working on F2L"
    if not analysis.oll_solved:
        return "Yellow OLL unsolved"
    if not analysis.pll_solved:
        return "Yellow PLL unsolved"
    return "Cube solved"


def validate_complete_sticker_states(sticker_states: list[StickerState]) -> None:
    errors: list[str] = []

    if len(sticker_states) != 54:
        errors.append(f"Expected 54 sticker states, got {len(sticker_states)}")

    sticker_ids = [state.sticker_id for state in sticker_states]
    if len(set(sticker_ids)) != len(sticker_ids):
        errors.append("Sticker ids are not unique in complete playback mode")

    facelet_indices = sorted(state.facelet_index for state in sticker_states)
    if facelet_indices != list(range(54)):
        errors.append("Complete playback mode did not cover all 54 facelet positions exactly once")

    gray_states = [state.sticker_id for state in sticker_states if state.color_name == "UNKNOWN"]
    if gray_states:
        errors.append(f"Complete playback mode produced UNKNOWN colors: {gray_states[:6]}")

    partial_unknowns = [state.sticker_id for state in sticker_states if state.is_partial_unknown]
    if partial_unknowns:
        errors.append("Complete playback mode marked stickers as partial/unknown")

    if errors:
        raise ValueError("; ".join(errors))


def sticker_state_is_in_layer(state: StickerState, face_name: str) -> bool:
    if state.cubie_type == "corner":
        return state.position_index in LAYER_CORNER_POSITIONS[face_name]
    if state.cubie_type == "edge":
        return state.position_index in LAYER_EDGE_POSITIONS[face_name]
    if state.cubie_type == "center":
        return state.local_face in LAYER_CENTER_FACES[face_name]
    return False


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def build_facelet_geometry_lookup(inset_ratio: float) -> dict[int, FaceletGeometry]:
    lookup: dict[int, FaceletGeometry] = {}
    for face_name in FACE_NAMES:
        for row in range(3):
            for col in range(3):
                facelet_index = facelet_index_from_face_row_col(face_name, row, col)
                lookup[facelet_index] = FaceletGeometry(
                    facelet_index=facelet_index,
                    face_name=face_name,
                    row=row,
                    col=col,
                    quad_points_local=build_face_cell_quad(face_name, row, col, inset_ratio),
                )
    return lookup


def build_face_cell_quad(face_name: str, row: int, col: int, inset_ratio: float) -> list[Point3D]:
    face_info = FACE_TO_AXIS_INFO[face_name]
    normal = face_info["normal"]
    up = face_info["up"]
    right = _cross(up, normal)
    face_center = _scale(normal, CUBE_HALF_EXTENT)

    cell_size = (CUBE_HALF_EXTENT * 2.0) / 3.0
    inset = cell_size * inset_ratio

    left = -CUBE_HALF_EXTENT + col * cell_size + inset
    right_edge = -CUBE_HALF_EXTENT + (col + 1) * cell_size - inset
    top = CUBE_HALF_EXTENT - row * cell_size - inset
    bottom = CUBE_HALF_EXTENT - (row + 1) * cell_size + inset

    def point(u: float, v: float) -> Point3D:
        return _add(face_center, _add(_scale(right, u), _scale(up, v)))

    return [
        point(left, top),
        point(right_edge, top),
        point(right_edge, bottom),
        point(left, bottom),
    ]


def facelet_index_from_face_row_col(face_name: str, row: int, col: int) -> int:
    return FACELET_ORDER.index(face_name) * 9 + row * 3 + col


# ---------------------------------------------------------------------------
# Camera / projection helpers
# ---------------------------------------------------------------------------

def rotate_points_for_camera(points: list[Point3D], yaw_deg: float, pitch_deg: float) -> list[Point3D]:
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)

    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)
    cos_pitch = math.cos(pitch)
    sin_pitch = math.sin(pitch)

    rotated_points: list[Point3D] = []
    for x, y, z in points:
        x_yaw = x * cos_yaw - z * sin_yaw
        z_yaw = x * sin_yaw + z * cos_yaw

        y_pitch = y * cos_pitch - z_yaw * sin_pitch
        z_pitch = y * sin_pitch + z_yaw * cos_pitch

        rotated_points.append((x_yaw, y_pitch, z_pitch))

    return rotated_points


def project_points_to_screen(
    points: list[Point3D],
    width: int,
    height: int,
    cube_scale: float,
    zoom: float,
) -> list[Point2D]:
    projected: list[Point2D] = []
    center_x = width / 2.0
    center_y = height / 2.0

    for x, y, z in points:
        depth = max(0.1, zoom - z)
        scale = cube_scale / depth
        projected.append(
            (
                int(round(center_x + x * scale)),
                int(round(center_y - y * scale)),
            )
        )

    return projected


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _move_total_angle(move: str) -> float:
    face_name = move[0]
    base_angle = 90.0 * FACE_CLOCKWISE_AXIS_TURNS[face_name]

    if move.endswith("'"):
        base_angle *= -1.0
    elif move.endswith("2"):
        base_angle *= 2.0

    return base_angle


def _cubie_type_from_face_position(row: int, col: int) -> str:
    if row == 1 and col == 1:
        return "center"
    if row in (0, 2) and col in (0, 2):
        return "corner"
    return "edge"


def _normalize_snapshot_color(value) -> str:
    if value is None:
        return "UNKNOWN"
    if isinstance(value, str):
        upper = value.upper()
        if upper in COLOR_NAME_TO_RGB:
            return upper
    return "UNKNOWN"


def _axis_name_from_normal(normal: Point3D) -> str:
    if abs(normal[0]) > 0.5:
        return "x"
    if abs(normal[1]) > 0.5:
        return "y"
    return "z"


def _rotate_point_about_axis(point: Point3D, axis_name: str, angle_deg: float) -> Point3D:
    x, y, z = point
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    if axis_name == "x":
        return (
            x,
            y * cos_a - z * sin_a,
            y * sin_a + z * cos_a,
        )
    if axis_name == "y":
        return (
            x * cos_a + z * sin_a,
            y,
            -x * sin_a + z * cos_a,
        )
    return (
        x * cos_a - y * sin_a,
        x * sin_a + y * cos_a,
        z,
    )


def _offset_points_along_normal(points: list[Point3D], normal: Point3D, amount: float) -> list[Point3D]:
    offset = _scale(normal, amount)
    return [_add(point, offset) for point in points]


def _add(a: Point3D, b: Point3D) -> Point3D:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(vector: Point3D, scale: float) -> Point3D:
    return (vector[0] * scale, vector[1] * scale, vector[2] * scale)


def _cross(a: Point3D, b: Point3D) -> Point3D:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _render_sort_key(quad: RenderQuad) -> tuple[float, int]:
    # Farthest polygons draw first. For nearly equal depth on the same face,
    # draw plastic before stickers so the sticker remains visibly on top.
    return (quad.depth, 1 if quad.draw_kind == "plastic" else 0)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _import_pygame():
    try:
        import pygame
    except ImportError:
        print("pygame is not installed. Run: pip install pygame")
        return None
    return pygame


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only and animated 3D Rubik's cube viewer")
    parser.add_argument("--facelets", help="54-character URFDLB facelet string")
    parser.add_argument("--snapshot", help="Path to a saved snapshot JSON file")
    parser.add_argument("--alg", help="Move sequence like \"R U R' U'\"")
    parser.add_argument("--session", help="Playback session JSON file")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        if args.session:
            session = load_playback_session(args.session)
            viewer = CubeViewer3D(
                facelets=session["facelets"],
                moves=session["moves"],
                playback_stages=session.get("stages"),
                playback_setup_text=session.get("setup_text", ""),
                title=session.get("title") or "Solution Playback",
            )
        elif args.snapshot:
            snapshot = load_view_snapshot(args.snapshot)
            viewer = CubeViewer3D(snapshot=snapshot, title="Cube Snapshot")
        else:
            facelets = args.facelets or SOLVED_FACELETS
            moves = parse_alg(args.alg) if args.alg else []
            title = "Animated Cube Viewer" if moves else "Rubik Cube 3D Viewer"
            viewer = CubeViewer3D(facelets=facelets, moves=moves, title=title)
    except Exception as exc:
        print(f"Could not load cube view input: {exc}")
        return 1

    viewer.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
