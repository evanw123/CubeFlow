import { commandLabel, escapeHtml, formatTimestamp, joinMoves, toneForValidation, validationLabel } from "../lib/format.js";
import { actionButton, betaBadge, emptyState, statusChip } from "./ui.js";

const FACE_LABELS = [
  ["U", "Up"],
  ["L", "Left"],
  ["F", "Front"],
  ["R", "Right"],
  ["B", "Back"],
  ["D", "Down"],
];

export const COLOR_HEX = {
  WHITE: "#f8fafc",
  YELLOW: "#ffd54d",
  RED: "#ef4444",
  ORANGE: "#fb923c",
  BLUE: "#3b82f6",
  GREEN: "#22c55e",
  UNKNOWN: "#334155",
};

function stickerMarkup(colorName, options = {}) {
  const {
    editable = false,
    slot = null,
    row = null,
    col = null,
    manual = false,
    locked = false,
  } = options;

  const safeColor = colorName || "UNKNOWN";
  const style = `style="background:${COLOR_HEX[safeColor] || COLOR_HEX.UNKNOWN}"`;
  const classes = ["cube-net__sticker"];
  if (manual) classes.push("is-manual");
  if (locked) classes.push("is-locked");

  if (!editable || locked || slot == null || row == null || col == null) {
    return `<div class="${classes.join(" ")}" ${style} title="${escapeHtml(safeColor)}">${manual ? '<span class="cube-net__manual-dot"></span>' : ""}</div>`;
  }

  return `
    <button
      class="${classes.join(" ")}"
      ${style}
      title="${escapeHtml(`Edit ${slot} ${row + 1},${col + 1}`)}"
      data-sticker-slot="${escapeHtml(slot)}"
      data-sticker-row="${escapeHtml(String(row))}"
      data-sticker-col="${escapeHtml(String(col))}"
      data-sticker-color="${escapeHtml(safeColor)}"
      type="button"
    >
      ${manual ? '<span class="cube-net__manual-dot"></span>' : ""}
    </button>
  `;
}

function renderFace(face, slot, label, options = {}) {
  const rows = face || [
    ["UNKNOWN", "UNKNOWN", "UNKNOWN"],
    ["UNKNOWN", "UNKNOWN", "UNKNOWN"],
    ["UNKNOWN", "UNKNOWN", "UNKNOWN"],
  ];
  const manualMask = options.manualMask?.[slot] || [[false, false, false], [false, false, false], [false, false, false]];

  return `
    <div class="cube-net__face cube-net__face--${escapeHtml(slot)} ${face ? "" : "is-empty"}">
      <div class="cube-net__face-label">${escapeHtml(label)} <span>${escapeHtml(slot)}</span></div>
      <div class="cube-net__face-grid ${options.editable ? "is-editable" : ""}">
        ${rows
          .flatMap((rowValues, rowIndex) =>
            rowValues.map((color, colIndex) =>
              stickerMarkup(color, {
                editable: options.editable,
                slot,
                row: rowIndex,
                col: colIndex,
                manual: Boolean(manualMask?.[rowIndex]?.[colIndex]),
                locked: options.lockCenters && rowIndex === 1 && colIndex === 1,
              }),
            ),
          )
          .join("")}
      </div>
    </div>
  `;
}

export function sectionHeader(eyebrow, title, description) {
  return `
    <div class="section-header">
      ${eyebrow ? `<div class="section-header__eyebrow">${escapeHtml(eyebrow)}</div>` : ""}
      <div>
        <h1>${escapeHtml(title)}</h1>
        ${description ? `<p>${escapeHtml(description)}</p>` : ""}
      </div>
    </div>
  `;
}

export function progressStepper(scanner) {
  const faces = [
    ["F", "Front"],
    ["R", "Right"],
    ["B", "Back"],
    ["L", "Left"],
    ["U", "Up"],
    ["D", "Down"],
  ];

  return `
    <div class="progress-stepper">
      ${faces
        .map(([slot, label], index) => {
          const done = Boolean(scanner?.capturedFaces?.[slot]);
          const active = scanner?.currentStepIndex === index;
          return `
            <div class="progress-step ${active ? "is-active" : ""} ${done ? "is-done" : ""}">
              <div class="progress-step__dot">${done ? "✓" : index + 1}</div>
              <div>
                <div class="progress-step__label">${escapeHtml(label)}</div>
              </div>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

export function validationCard(review) {
  const tone = toneForValidation(review);
  const label = validationLabel(review);
  const issues = [...(review?.basicValidation?.errors || []), ...(review?.deepValidation?.errors || [])].slice(0, 3);

  return `
    <div class="card validation-card">
      <div class="card__header card__header--tight">
        <div>
          <div class="card__eyebrow">Validation</div>
          <h3>Cube review status</h3>
        </div>
        ${statusChip(label, tone)}
      </div>
      <div class="validation-grid">
        <div>
          <div class="validation-grid__label">Faces captured</div>
          <div class="validation-grid__value">${escapeHtml(String(review?.capturedFaceCount || 0))} / 6</div>
        </div>
        <div>
          <div class="validation-grid__label">Basic validation</div>
          <div class="validation-grid__value">${review?.basicValidation?.ok ? "Pass" : "Needs attention"}</div>
        </div>
        <div>
          <div class="validation-grid__label">Deep validation</div>
          <div class="validation-grid__value">${review?.deepValidation?.ok ? "Solver-ready" : "Not ready"}</div>
        </div>
      </div>
      ${issues.length ? `<div class="notice notice--warning">${issues.map((issue) => `<div>${escapeHtml(issue)}</div>`).join("")}</div>` : `<p class="muted">The current scan looks healthy enough to continue.</p>`}
    </div>
  `;
}

export function cubeNetCard(faces, activeSlot = null, title = "Cube Net", options = {}) {
  const safeFaces = faces || {};
  const activeLabel = activeSlot ? `Tracking ${commandLabel(activeSlot)} face` : options.activeLabel || "Latest cube state";
  const footer = options.footerHtml ? `<div class="cube-net-card__footer">${options.footerHtml}</div>` : "";
  return `
    <div class="card cube-net-card ${options.editable ? "cube-net-card--editable" : ""}">
      <div class="card__header card__header--tight">
        <div>
          <div class="card__eyebrow">Review</div>
          <h3>${escapeHtml(title)}</h3>
        </div>
        ${statusChip(activeLabel, activeSlot ? "accent" : "neutral")}
      </div>
      <div class="cube-net ${options.compact ? "cube-net--compact" : ""}">
        ${FACE_LABELS.map(([slot, label]) => renderFace(safeFaces[slot], slot, label, options)).join("")}
      </div>
      ${footer}
    </div>
  `;
}

export function betaFeatureCard({ title, description, actionLabel, action }) {
  return `
    <div class="card beta-card">
      <div class="card__header card__header--tight">
        <div>
          <div class="card__eyebrow">Labs</div>
          <h3>${escapeHtml(title)}</h3>
        </div>
        ${betaBadge("BETA")}
      </div>
      <p class="muted">${escapeHtml(description)}</p>
      <div class="card__actions">
        ${actionButton(actionLabel, action, "ghost")}
      </div>
    </div>
  `;
}

export function advancedDrawer(title, content) {
  return `
    <details class="advanced-drawer">
      <summary>
        <span>${escapeHtml(title)}</span>
        <span class="advanced-drawer__hint">Show advanced</span>
      </summary>
      <div class="advanced-drawer__content">${content}</div>
    </details>
  `;
}

export function solveResultCard(result, { beta = false } = {}) {
  if (!result) {
    return emptyState(
      beta ? "No CFOP Beta result yet" : "No solve result yet",
      beta ? "Run CFOP Beta when you want to test the experimental pipeline." : "Run the standard solver to generate a solution and playback.",
    );
  }

  const tone = result.status === "success" ? "success" : result.status === "incomplete" ? "warning" : "danger";
  const headerBadge = beta ? betaBadge("BETA") : statusChip("Stable", "success");
  const moveString = result.moveString || joinMoves(result.moves || []);
  const stageList = Array.isArray(result.stages) && result.stages.length
    ? `<div class="solve-stage-list">${result.stages
        .map(
          (stage) => `
            <div class="solve-stage-item ${stage.success ? "" : "is-error"}">
              <div class="solve-stage-item__header">
                <div>
                  <strong>${escapeHtml(stage.label || stage.name)}</strong>
                  ${stage.caseId ? `<span class="solve-stage-item__case">${escapeHtml(stage.caseId)}</span>` : ""}
                </div>
                <div class="solve-stage-item__meta">${stage.success ? "✓ Verified" : "Unverified"} · ${escapeHtml(String(stage.moveCount ?? stage.moves?.length ?? 0))} moves</div>
              </div>
              <div class="solve-stage-item__moves">${escapeHtml((stage.moves || stage.displayMoves || []).join(" ") || "No moves needed")}</div>
            </div>
          `,
        )
        .join("")}</div>`
    : "";

  return `
    <div class="card solve-result-card ${beta ? "solve-result-card--beta" : ""}">
      <div class="card__header card__header--tight">
        <div>
          <div class="card__eyebrow">${beta ? "Experimental solve" : "Primary solve"}</div>
          <h3>${escapeHtml(result.title || (beta ? "CFOP Beta" : "Standard Solve"))}</h3>
        </div>
        <div class="card__header-badges">
          ${headerBadge}
          ${statusChip(result.status === "success" ? `${result.moveCount || 0} moves` : result.status === "incomplete" ? "Incomplete" : "Needs attention", tone)}
        </div>
      </div>
      ${result.error ? `<div class="notice ${beta ? "notice--warning" : "notice--danger"}">${escapeHtml(result.error)}</div>` : ""}
      ${beta && result.setupText ? `<div class="viewer-orientation-callout"><div class="card__eyebrow">Hold orientation</div><strong>${escapeHtml(result.setupText)}</strong></div>` : ""}
      ${result.segmentationWarning ? `<div class="notice notice--warning">${escapeHtml(result.segmentationWarning)}</div>` : ""}
      ${result.failingStage ? `<div class="result-meta">Failed at ${escapeHtml(result.failingStage)}${result.failingSlot ? ` ${escapeHtml(result.failingSlot)}` : ""}${result.failingCaseId ? ` · ${escapeHtml(result.failingCaseId)}` : ""}</div>` : ""}
      <div class="move-block">${escapeHtml(moveString || "No moves")}</div>
      ${stageList}
      <div class="card__footer">
        <div class="muted">Updated ${escapeHtml(formatTimestamp(result.lastSolvedAt))}</div>
        <div class="card__actions">
          ${moveString ? `<button class="button button--secondary" data-copy-text="${escapeHtml(moveString)}">Copy Moves</button>` : ""}
          ${!beta && result.status === "success" ? actionButton("Play in 3D", "viewer:standard", "primary") : ""}
          ${beta && result.status === "success" ? actionButton("Play Beta in 3D", "viewer:cfop", "ghost") : ""}
        </div>
      </div>
    </div>
  `;
}
