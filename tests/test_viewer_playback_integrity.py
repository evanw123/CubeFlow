from __future__ import annotations

import pytest

from cube_backend.cubie_model import CubieCube
from cube_backend.move_utils import parse_alg
from cube_backend.viewer_snapshot import facelet_string_to_view_snapshot
from cube_viewer_3d import (
    ActiveAnimation,
    CubeViewer3D,
    MODE_PARTIAL,
    MODE_PLAYBACK,
    ViewerConfig,
    build_render_quads_from_cubie_cube,
    build_render_quads_from_snapshot,
    project_render_quads,
    summarize_render_quads,
)


SOLVED_FACELETS = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"
TEST_CONFIG = ViewerConfig(width=800, height=600)


def _partial_snapshot() -> dict:
    snapshot = facelet_string_to_view_snapshot(SOLVED_FACELETS)
    snapshot["F"][0][0] = "UNKNOWN"
    snapshot["R"][2][2] = None
    return snapshot


def test_complete_solved_cube_has_54_non_gray_stickers():
    quads = build_render_quads_from_cubie_cube(CubieCube.solved(), config=TEST_CONFIG)
    summary = summarize_render_quads(quads)

    assert summary["sticker_quad_count"] == 54
    assert summary["gray_sticker_count"] == 0


def test_complete_cube_after_single_move_has_54_non_gray_stickers():
    cube = CubieCube.solved()
    cube.apply_move("R")

    quads = build_render_quads_from_cubie_cube(cube, config=TEST_CONFIG)
    summary = summarize_render_quads(quads)

    assert summary["sticker_quad_count"] == 54
    assert summary["gray_sticker_count"] == 0


def test_complete_cube_after_algorithm_has_54_non_gray_stickers():
    cube = CubieCube.solved()
    cube.apply_alg("R U R' U'")

    quads = build_render_quads_from_cubie_cube(cube, config=TEST_CONFIG)
    summary = summarize_render_quads(quads)

    assert summary["sticker_quad_count"] == 54
    assert summary["gray_sticker_count"] == 0


def test_each_animation_frame_keeps_54_colored_stickers():
    cube = CubieCube.solved()

    for progress in [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]:
        quads = build_render_quads_from_cubie_cube(
            cube,
            config=TEST_CONFIG,
            active_animation=ActiveAnimation(move="R", progress=progress),
        )
        summary = summarize_render_quads(quads)

        assert summary["sticker_quad_count"] == 54
        assert summary["gray_sticker_count"] == 0


def test_step_forward_backward_does_not_introduce_unknowns():
    viewer = CubeViewer3D(facelets=SOLVED_FACELETS, moves=parse_alg("R U"), config=TEST_CONFIG)

    before = summarize_render_quads(viewer.build_world_render_quads())
    assert before["gray_sticker_count"] == 0

    viewer._step_forward()
    viewer._commit_current_animation()
    after_step = summarize_render_quads(viewer.build_world_render_quads())
    assert after_step["sticker_quad_count"] == 54
    assert after_step["gray_sticker_count"] == 0

    viewer._step_backward()
    after_back = summarize_render_quads(viewer.build_world_render_quads())
    assert after_back["sticker_quad_count"] == 54
    assert after_back["gray_sticker_count"] == 0
    assert viewer.current_cube is not None
    assert viewer.current_cube.to_facelet_string() == SOLVED_FACELETS


def test_partial_snapshot_mode_allows_gray():
    quads = build_render_quads_from_snapshot(_partial_snapshot(), config=TEST_CONFIG)
    summary = summarize_render_quads(quads)

    assert summary["sticker_quad_count"] == 54
    assert summary["gray_sticker_count"] == 2


def test_viewer_mode_complete_vs_partial():
    playback_viewer = CubeViewer3D(facelets=SOLVED_FACELETS, config=TEST_CONFIG)
    partial_viewer = CubeViewer3D(snapshot=_partial_snapshot(), config=TEST_CONFIG)

    assert playback_viewer.render_mode == MODE_PLAYBACK
    assert partial_viewer.render_mode == MODE_PARTIAL
    assert summarize_render_quads(playback_viewer.build_world_render_quads())["gray_sticker_count"] == 0
    assert summarize_render_quads(partial_viewer.build_world_render_quads())["gray_sticker_count"] == 2


def test_partial_snapshot_mode_rejects_animation_requests():
    with pytest.raises(ValueError):
        CubeViewer3D(snapshot=_partial_snapshot(), moves=["R"], config=TEST_CONFIG)


def test_projected_complete_cube_has_no_gray_visible_stickers_across_camera_angles():
    world_quads = build_render_quads_from_cubie_cube(CubieCube.solved(), config=TEST_CONFIG)

    for yaw_deg, pitch_deg in [(-35, 25), (20, 20), (70, 15), (-120, 30), (140, -20)]:
        visible = project_render_quads(
            world_quads,
            yaw_deg=yaw_deg,
            pitch_deg=pitch_deg,
            config=TEST_CONFIG,
            zoom=TEST_CONFIG.zoom,
        )
        summary = summarize_render_quads(visible)
        assert summary["gray_sticker_count"] == 0
        assert summary["sticker_quad_count"] > 0


def test_sticker_surfaces_are_offset_in_front_of_matching_plastic():
    quads = build_render_quads_from_cubie_cube(CubieCube.solved(), config=TEST_CONFIG)
    plastic_by_id = {
        quad.sticker_id: quad
        for quad in quads
        if quad.draw_kind == "plastic"
    }

    for sticker in [quad for quad in quads if quad.draw_kind == "sticker"]:
        plastic = plastic_by_id[f"{sticker.sticker_id}-plastic"]
        sticker_center = _quad_center(sticker.points_world)
        plastic_center = _quad_center(plastic.points_world)
        normal = sticker.normal_world

        signed_gap = (
            (sticker_center[0] - plastic_center[0]) * normal[0]
            + (sticker_center[1] - plastic_center[1]) * normal[1]
            + (sticker_center[2] - plastic_center[2]) * normal[2]
        )
        assert signed_gap > 0.0


def _quad_center(points: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
        sum(point[2] for point in points) / len(points),
    )
