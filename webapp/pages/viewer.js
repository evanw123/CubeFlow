import { COLOR_HEX } from "../components/cards.js";
import { actionButton, emptyState, statusChip } from "../components/ui.js";
import { escapeHtml, formatTimestamp } from "../lib/format.js";
import { getViewerTurnSpec } from "../lib/viewer-turns.js";

const CUBIE_HALF = 34;
const CUBIE_STEP = 76;
const CUBIE_FACES = {
  F: `translateZ(${CUBIE_HALF}px)`,
  B: `rotateY(180deg) translateZ(${CUBIE_HALF}px)`,
  R: `rotateY(90deg) translateZ(${CUBIE_HALF}px)`,
  L: `rotateY(-90deg) translateZ(${CUBIE_HALF}px)`,
  U: `rotateX(90deg) translateZ(${CUBIE_HALF}px)`,
  D: `rotateX(-90deg) translateZ(${CUBIE_HALF}px)`,
};
const VIEW_FACES = ["F", "B", "R", "L", "U", "D"];

function getActiveStage(session, frameIndex) {
  if (!session?.stages?.length) return null;
  if (frameIndex >= (session.moves?.length || 0)) {
    return session.stages[session.stages.length - 1] || null;
  }
  return session.stages.find((stage) => frameIndex >= stage.start_index && frameIndex < stage.end_index)
    || session.stages.find((stage) => stage.end_index > frameIndex)
    || session.stages[session.stages.length - 1]
    || null;
}

function faceletFromCubie(snapshot, x, y, z, face) {
  if (!snapshot?.[face]) return "UNKNOWN";
  let row = 1;
  let col = 1;

  switch (face) {
    case "F":
      row = 1 - y;
      col = x + 1;
      break;
    case "B":
      row = 1 - y;
      col = 1 - x;
      break;
    case "R":
      row = 1 - y;
      col = 1 - z;
      break;
    case "L":
      row = 1 - y;
      col = z + 1;
      break;
    case "U":
      row = z + 1;
      col = x + 1;
      break;
    case "D":
      row = 1 - z;
      col = x + 1;
      break;
    default:
      break;
  }

  return snapshot[face]?.[row]?.[col] || "UNKNOWN";
}

function cubieMarkup(snapshot, x, y, z) {
  const visibleFaces = [];
  if (z === 1) visibleFaces.push("F");
  if (z === -1) visibleFaces.push("B");
  if (x === 1) visibleFaces.push("R");
  if (x === -1) visibleFaces.push("L");
  if (y === 1) visibleFaces.push("U");
  if (y === -1) visibleFaces.push("D");
  if (!visibleFaces.length) return "";

  const baseTransform = `translate3d(${x * CUBIE_STEP}px, ${-y * CUBIE_STEP}px, ${z * CUBIE_STEP}px)`;

  return `
    <div
      class="web-cubie"
      data-cubie
      data-x="${x}"
      data-y="${y}"
      data-z="${z}"
      data-base-transform="${baseTransform}"
      style="transform:${baseTransform}"
    >
      ${visibleFaces.map((face) => `
        <div class="web-cubie__face web-cubie__face--${face}" style="transform:${CUBIE_FACES[face]}">
          <span class="web-cubie__sticker" style="background:${COLOR_HEX[faceletFromCubie(snapshot, x, y, z, face)] || COLOR_HEX.UNKNOWN}"></span>
        </div>
      `).join("")}
    </div>
  `;
}

function renderCube(session, viewerState) {
  const frame = session?.frames?.[viewerState.frameIndex] || session?.frames?.[0];
  if (!frame) {
    return emptyState("Viewer not ready", "Load the current cube or a playback session to inspect it here.");
  }

  const cubies = [];
  for (let x = -1; x <= 1; x += 1) {
    for (let y = -1; y <= 1; y += 1) {
      for (let z = -1; z <= 1; z += 1) {
        if (x === 0 && y === 0 && z === 0) continue;
        cubies.push(cubieMarkup(frame, x, y, z));
      }
    }
  }

  return `
    <div class="web-cube-stage" data-viewer-stage>
      <div class="web-cube-stage__hint">Drag to rotate • Scroll to zoom • ←/→ step • Space play</div>
      <div class="web-cube-stage__viewport">
        <div class="web-cube__orbit" data-viewer-orbit style="transform: rotateX(${viewerState.pitch}deg) rotateY(${viewerState.yaw}deg) scale(${viewerState.zoom});">
          <div class="web-cube" data-cube-root>
            ${cubies.join("")}
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderPlaybackControls(session, viewerState) {
  const moves = session?.moves || [];
  const atStart = viewerState.frameIndex <= 0;
  const atEnd = viewerState.frameIndex >= moves.length;
  const busy = Boolean(viewerState.animating);
  const activeMove = viewerState.frameIndex < moves.length ? moves[viewerState.frameIndex] : moves.length ? "Solved" : "Inspection";
  const stage = getActiveStage(session, viewerState.frameIndex);
  const stageLocalIndex = stage ? Math.max(0, Math.min(stage.move_count || 0, viewerState.frameIndex - stage.start_index)) : 0;

  return `
    <div class="card viewer-controls-card" data-viewer-controls>
      <div class="viewer-controls-card__top">
        <div>
          <div class="card__eyebrow">Playback</div>
          <h3 data-viewer-current-move>${escapeHtml(activeMove)}</h3>
          <p data-viewer-stage-name>${escapeHtml(stage?.label || stage?.name || (session?.mode === "current" ? "Current Cube" : "Playback"))}${stage ? ` · ${stageLocalIndex + (viewerState.frameIndex < stage.end_index ? 1 : 0)} / ${stage.move_count || 0}` : ""}</p>
        </div>
        <div class="viewer-progress-badge" data-viewer-progress>${escapeHtml(String(viewerState.frameIndex))} / ${escapeHtml(String(moves.length))}</div>
      </div>
      <div class="viewer-controls-bar">
        <button type="button" class="button button--ghost" data-viewer-action="prev" ${atStart || viewerState.playing || busy ? "disabled" : ""}>Previous</button>
        <button type="button" class="button button--primary" data-viewer-action="toggle-play" ${moves.length ? "" : "disabled"}>${viewerState.playing ? "Pause" : busy ? "Working…" : "Play"}</button>
        <button type="button" class="button button--ghost" data-viewer-action="next" ${atEnd || viewerState.playing || busy ? "disabled" : ""}>Next</button>
        <button type="button" class="button button--secondary" data-viewer-action="reset-playback" ${busy ? "disabled" : ""}>Reset</button>
        <button type="button" class="button button--ghost" data-viewer-action="reset-view">Reset View</button>
        <label class="viewer-speed-control">
          <span>Speed</span>
          <select data-viewer-speed>
            ${(session?.speedOptions || [0.5, 1.0, 1.5, 2.0]).map((speed) => `<option value="${speed}" ${Number(viewerState.speed) === Number(speed) ? "selected" : ""}>${speed}×</option>`).join("")}
          </select>
        </label>
      </div>
      <div class="viewer-stage-note" data-viewer-stage-note>${stage?.rotation_prompt ? `Rotate ${escapeHtml(stage.rotation_prompt)} · ${escapeHtml(stage.display_moves || stage.description || "")}` : stage?.description ? escapeHtml(stage.description) : "Watching the cube move directly in the browser."}</div>
    </div>
  `;
}

function renderModeCard(label, description, mode, active, disabled = false, badge = "") {
  return `
    <div class="mode-switch-item ${active ? "is-active" : ""} ${disabled ? "is-disabled" : ""}">
      <div>
        <strong>${escapeHtml(label)}</strong>
        <p>${escapeHtml(description)}</p>
      </div>
      <div class="mode-switch-item__actions">
        ${badge}
        <button type="button" class="button button--${active ? "secondary" : "ghost"}" data-viewer-mode="${escapeHtml(mode)}" ${disabled ? "disabled" : ""}>${active ? "Loaded" : "Load"}</button>
      </div>
    </div>
  `;
}

function renderMoveList(session, viewerState) {
  const moves = session?.moves || [];
  if (!moves.length) {
    return `<div class="muted">No playback moves for this view.</div>`;
  }

  return `
    <div class="viewer-move-list" data-viewer-move-list>
      ${moves.map((move, index) => `
        <span class="viewer-move-chip ${viewerState.frameIndex === index ? "is-active" : ""} ${viewerState.frameIndex > index ? "is-complete" : ""}">${escapeHtml(move)}</span>
      `).join("")}
    </div>
  `;
}

function renderStagePanel(session, viewerState) {
  if (session?.mode !== "cfop" || !session?.stages?.length) return "";

  const activeStage = getActiveStage(session, viewerState.frameIndex);
  return `
    <div class="card viewer-stage-panel">
      <div class="viewer-orientation-callout">
        <div class="card__eyebrow">Hold orientation</div>
        <strong>${escapeHtml(session.setupText || "Hold the cube with WHITE on the bottom and GREEN facing you.")}</strong>
      </div>
      ${session.segmentationWarning ? `<div class="notice notice--warning">${escapeHtml(session.segmentationWarning)}</div>` : ""}
      <div class="card__header card__header--tight">
        <div>
          <div class="card__eyebrow">CFOP stages</div>
          <h3>Four-stage solution</h3>
        </div>
        ${statusChip(session.segmentationVerified ? "Verified" : "Unverified", session.segmentationVerified ? "success" : "warning")}
      </div>
      <div class="viewer-cfop-stages">
        ${session.stages.map((stage) => {
          const completed = viewerState.frameIndex >= stage.end_index;
          const active = activeStage === stage && !completed;
          const stageMoves = Array.isArray(stage.moves) ? stage.moves : [];
          return `
            <div class="viewer-cfop-stage ${active ? "is-active" : ""} ${completed ? "is-complete" : ""}">
              <div class="viewer-cfop-stage__header">
                <div>
                  <div class="viewer-cfop-stage__state">${completed ? "✓ Complete" : active ? "Now playing" : "Up next"}</div>
                  <strong>${escapeHtml(stage.label || stage.name)}</strong>
                  <span>${escapeHtml(String(stage.move_count || stageMoves.length))} moves</span>
                </div>
                <div class="viewer-cfop-stage__actions">
                  <button type="button" class="button button--ghost" data-viewer-stage-start="${stage.start_index}">Jump</button>
                  <button type="button" class="button button--secondary" data-viewer-stage-play="${stage.start_index}:${stage.end_index}" ${stage.end_index <= stage.start_index ? "disabled" : ""}>Play stage</button>
                </div>
              </div>
              <div class="viewer-stage-moves">
                ${stageMoves.length ? stageMoves.map((move, localIndex) => {
                  const globalIndex = stage.start_index + localIndex;
                  return `<span class="viewer-move-chip ${viewerState.frameIndex === globalIndex ? "is-active" : ""} ${viewerState.frameIndex > globalIndex ? "is-complete" : ""}">${escapeHtml(move)}</span>`;
                }).join("") : `<span class="muted">No moves needed.</span>`}
              </div>
            </div>
          `;
        }).join("")}
      </div>
    </div>
  `;
}

function renderMovePanel(session, viewerState) {
  const isCfop = session?.mode === "cfop";
  return `
    <div class="card viewer-move-panel">
      <div class="card__header card__header--tight">
        <div>
          <div class="card__eyebrow">${isCfop ? "Combined timeline" : "Move list"}</div>
          <h3>${isCfop ? "Full CFOP solution" : session?.mode === "standard" ? "Standard Solution" : "Current cube"}</h3>
        </div>
        ${session?.moves?.length ? statusChip(`${session.moves.length} moves`, "neutral") : ""}
      </div>
      ${renderMoveList(session, viewerState)}
    </div>
  `;
}

function rotatePrefix(axis, angle) {
  const fn = axis === "x" ? "rotateX" : axis === "y" ? "rotateY" : "rotateZ";
  return `${fn}(${angle}deg)`;
}

function easeInOutCubic(progress) {
  return progress < 0.5
    ? 4 * progress * progress * progress
    : 1 - ((-2 * progress + 2) ** 3) / 2;
}

function cubieMatchesLayer(node, axis, layer) {
  if (layer === "all") return true;
  const value = Number(node.dataset[axis]);
  if (Array.isArray(layer)) return layer.includes(value);
  return value === layer;
}

export function animateViewerTurn(move, { reverse = false, speed = 1 } = {}) {
  const spec = getViewerTurnSpec(move, reverse);
  const cubeRoot = document.querySelector("[data-cube-root]");
  if (!spec || !cubeRoot) {
    return Promise.resolve(false);
  }

  const cubies = Array.from(cubeRoot.querySelectorAll("[data-cubie]"))
    .filter((node) => cubieMatchesLayer(node, spec.axis, spec.layer));
  if (!cubies.length) {
    return Promise.resolve(false);
  }

  const durationMs = Math.max(150, Math.round(300 / Number(speed || 1)));
  return new Promise((resolve) => {
    const startedAt = performance.now();
    const tick = (now) => {
      const elapsed = now - startedAt;
      const progress = Math.min(1, elapsed / durationMs);
      const eased = easeInOutCubic(progress);
      const currentAngle = spec.angle * eased;

      cubies.forEach((cubie) => {
        cubie.style.transform = `${rotatePrefix(spec.axis, currentAngle)} ${cubie.dataset.baseTransform}`;
      });

      if (progress < 1) {
        window.requestAnimationFrame(tick);
        return;
      }

      resolve(true);
    };

    window.requestAnimationFrame(tick);
  });
}

export function renderViewerPage(state, app) {
  const viewer = state.viewer || {};
  const standard = state.solves?.standard;
  const cfop = state.solves?.cfop;
  const viewerState = app?.viewerState || {};
  const session = viewerState.session;
  const stage = getActiveStage(session, viewerState.frameIndex || 0);

  return `
    <div class="viewer-page-shell">
      <div class="viewer-layout viewer-layout--web">
        <div class="viewer-primary-column">
          <div class="card viewer-stage-card viewer-stage-card--web">
            <div class="card__header viewer-stage-card__header">
              <div>
                <div class="card__eyebrow">Interactive viewer</div>
                <h2>${escapeHtml(session?.title || "3D cube viewer")}</h2>
                <p>${escapeHtml(session?.setupText || "Rotate the camera freely to inspect the cube.")}</p>
              </div>
              ${statusChip(session?.beta ? "CFOP Beta" : session ? "Ready" : "Not loaded", session?.beta ? "warning" : session ? "success" : "neutral")}
            </div>
            <div class="viewer-stage-card__canvas viewer-stage-card__canvas--web">
              ${viewerState.loading ? `<div class="viewer-inline-message">Loading viewer session…</div>` : viewerState.error ? `<div class="viewer-inline-message viewer-inline-message--warning">${escapeHtml(viewerState.error)}</div>` : renderCube(session, viewerState)}
            </div>
            ${renderPlaybackControls(session, viewerState)}
          </div>
        </div>
        <aside class="viewer-sidebar">
          ${renderStagePanel(session, viewerState)}
          ${renderMovePanel(session, viewerState)}
          <div class="card mode-switch-card">
            <div class="card__header card__header--tight">
              <div>
                <div class="card__eyebrow">Sources</div>
                <h3>Choose what to inspect</h3>
              </div>
            </div>
            <div class="mode-switch-list">
              ${renderModeCard("Current cube", "Inspect the latest scanned or manually corrected cube state.", "current", session?.mode === "current")}
              ${renderModeCard("Standard playback", standard?.status === "success" ? `Stable solve ready with ${standard.moveCount} moves.` : "Run Standard Solve first.", "standard", session?.mode === "standard", standard?.status !== "success")}
              ${renderModeCard("CFOP Beta playback", cfop?.status === "success" ? `Experimental solve ready with ${cfop.moveCount} moves.` : cfop?.error || "Available only when CFOP Beta succeeds.", "cfop", session?.mode === "cfop", cfop?.status !== "success", cfop?.status === "success" ? statusChip("Beta", "warning") : "")}
            </div>
          </div>
          <div class="card">
            <div class="card__header card__header--tight">
              <div>
                <div class="card__eyebrow">Session details</div>
                <h3>${escapeHtml(stage?.name || session?.title || "Viewer idle")}</h3>
              </div>
            </div>
            <div class="metric-list">
              <div><span>Mode</span><strong>${escapeHtml(session?.mode || "none")}</strong></div>
              <div><span>Current move</span><strong>${escapeHtml(viewerState.frameIndex < (session?.moves?.length || 0) ? session?.moves?.[viewerState.frameIndex] || "—" : session?.moves?.length ? "Solved" : "Inspection")}</strong></div>
              <div><span>Stages</span><strong>${escapeHtml(String(session?.stages?.length || 0))}</strong></div>
              <div><span>Orientation</span><strong>Yellow top · White bottom</strong></div>
              <div><span>Last native session</span><strong>${escapeHtml(viewer.lastOpenedAt ? formatTimestamp(viewer.lastOpenedAt) : "Never")}</strong></div>
            </div>
            ${stage?.description ? `<div class="viewer-stage-note">${escapeHtml(stage.description)}</div>` : ""}
          </div>
          <div class="card">
            <div class="card__header card__header--tight">
              <div>
                <div class="card__eyebrow">Fallback</div>
                <h3>Open the native viewer</h3>
              </div>
            </div>
            <p class="muted">The browser viewer is now the main inspection surface, but the original native 3D viewer remains available as a fallback for snapshots and playback.</p>
            <div class="cta-row cta-row--wrap">
              ${actionButton("Open Native Current Cube", "open-viewer", "secondary")}
              ${actionButton("Play Native Standard", "playback-standard", "ghost", standard?.status === "success" ? "" : "disabled")}
              ${actionButton("Play Native CFOP Beta", "playback-cfop", "ghost", cfop?.status === "success" ? "" : "disabled")}
            </div>
          </div>
        </aside>
      </div>
    </div>
  `;
}

export function hydrateViewerPage(app) {
  const stage = document.querySelector("[data-viewer-stage]");
  const orbit = document.querySelector("[data-viewer-orbit]");
  if (!stage || !orbit) return;

  const state = app.viewerState;
  if (!state) return;

  const applyOrbit = () => {
    const orbitNode = document.querySelector("[data-viewer-orbit]");
    if (orbitNode) {
      orbitNode.style.transform = `rotateX(${state.pitch}deg) rotateY(${state.yaw}deg) scale(${state.zoom})`;
    }
  };

  let dragState = null;

  stage.onpointerdown = (event) => {
    dragState = { x: event.clientX, y: event.clientY };
    stage.classList.add("is-dragging");
    stage.setPointerCapture?.(event.pointerId);
  };

  stage.onpointermove = (event) => {
    if (!dragState) return;
    const deltaX = event.clientX - dragState.x;
    const deltaY = event.clientY - dragState.y;
    dragState = { x: event.clientX, y: event.clientY };
    state.yaw += deltaX * 0.42;
    state.pitch = Math.max(-88, Math.min(88, state.pitch - deltaY * 0.34));
    applyOrbit();
  };

  const endDrag = (event) => {
    if (!dragState) return;
    dragState = null;
    stage.classList.remove("is-dragging");
    if (typeof event?.pointerId === "number") {
      try {
        stage.releasePointerCapture?.(event.pointerId);
      } catch (_error) {
        // no-op
      }
    }
  };

  stage.onpointerup = endDrag;
  stage.onpointercancel = endDrag;
  stage.onpointerleave = () => {
    if (dragState) {
      stage.classList.remove("is-dragging");
    }
  };

  stage.onwheel = (event) => {
    event.preventDefault();
    const delta = event.deltaY > 0 ? -0.08 : 0.08;
    state.zoom = Math.max(0.72, Math.min(1.8, Number((state.zoom + delta).toFixed(2))));
    applyOrbit();
  };

  applyOrbit();
}
