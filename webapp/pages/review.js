import { COLOR_HEX, betaFeatureCard, cubeNetCard, sectionHeader, validationCard } from "../components/cards.js";
import { actionButton, emptyState, statusChip } from "../components/ui.js";
import { commandLabel, escapeHtml } from "../lib/format.js";

const COLOR_OPTIONS = ["WHITE", "YELLOW", "RED", "ORANGE", "BLUE", "GREEN", "UNKNOWN"];

function renderLegend() {
  return `
    <div class="color-legend">
      ${COLOR_OPTIONS.map(
        (color) => `
          <div class="color-legend__item">
            <span class="color-legend__swatch" style="background:${COLOR_HEX[color]}"></span>
            <span>${escapeHtml(color)}</span>
          </div>
        `,
      ).join("")}
    </div>
  `;
}

function renderEditFooter(review) {
  return `
    <div class="cube-net-card__meta-row">
      ${statusChip(`${review.manualEditCount || 0} manual ${review.manualEditCount === 1 ? "edit" : "edits"}`, review.manualEditCount ? "accent" : "neutral")}
      ${statusChip(review.centersLocked ? "Centers locked" : "Centers editable", review.centersLocked ? "neutral" : "warning")}
    </div>
    <p class="support-text">Click any non-center sticker to correct the scanned color. Manual edits stay separate from the raw scan and re-run validation immediately.</p>
    ${renderLegend()}
  `;
}

function renderSelectedStickerEditor(review, app) {
  const selection = app?.reviewEditor?.selected;
  if (!selection) {
    return `
      <div class="card">
        <div class="card__header card__header--tight">
          <div>
            <div class="card__eyebrow">Manual correction</div>
            <h3>Edit sticker colors</h3>
          </div>
        </div>
        <p class="muted">Choose a sticker on the cube net to open a quick color picker. Center stickers stay locked so orientation conventions remain stable.</p>
        ${renderLegend()}
      </div>
    `;
  }

  const slotLabel = commandLabel(selection.slot);
  return `
    <div class="card review-editor-card">
      <div class="card__header card__header--tight">
        <div>
          <div class="card__eyebrow">Manual correction</div>
          <h3>${escapeHtml(slotLabel)} sticker</h3>
        </div>
        ${statusChip(`${selection.slot} · row ${selection.row + 1} · col ${selection.col + 1}`, "accent")}
      </div>
      <p class="muted">Pick the color this sticker should be. The cube preview and validation status update immediately.</p>
      <div class="color-picker-grid">
        ${COLOR_OPTIONS.map(
          (color) => `
            <button
              type="button"
              class="color-choice ${selection.color === color ? "is-active" : ""}"
              data-color-choice="${escapeHtml(color)}"
            >
              <span class="color-choice__swatch" style="background:${COLOR_HEX[color]}"></span>
              <span>${escapeHtml(color)}</span>
            </button>
          `,
        ).join("")}
      </div>
      <div class="cta-row cta-row--wrap">
        <button class="button button--secondary" type="button" data-edit-action="undo" ${review.manualEditCount ? "" : "disabled"}>Undo last edit</button>
        <button class="button button--ghost" type="button" data-edit-action="reset" ${review.manualEditCount ? "" : "disabled"}>Reset manual edits</button>
        <button class="button button--ghost" type="button" data-edit-action="close-picker">Done</button>
      </div>
    </div>
  `;
}

function renderReviewActions(review) {
  return `
    <div class="card">
      <div class="card__header card__header--tight">
        <div>
          <div class="card__eyebrow">Actions</div>
          <h3>Next step</h3>
        </div>
      </div>
      <div class="cta-row cta-row--wrap">
        ${actionButton("Back to Scan", "route:scan", "secondary")}
        ${actionButton("Solve with Standard Solver", "solve-standard", "primary", review.deepValidation?.ok ? "" : "disabled")}
        ${actionButton("Open 3D Viewer", "route:viewer", "ghost")}
      </div>
      <div class="support-text">Standard Solve stays the stable path. Manual corrections carry through into Review, Solve, and Viewer.</div>
    </div>
  `;
}

export function renderReviewPage(state, app) {
  const review = state.review || {};

  if (!review.capturedFaceCount) {
    return `
      <div class="stack-lg">
        ${sectionHeader("Review", "Confirm the current cube state", "This screen becomes your checkpoint before solving.")}
        <div class="two-column-grid">
          <div class="card">
            ${emptyState(
              "No cube scanned yet",
              "Scan a cube to review colors, validate the state, and make manual corrections. This screen will keep working even before the first capture.",
              `
                <div class="cta-row cta-row--wrap">
                  ${actionButton("Go to Scan", "route:scan", "primary")}
                  ${actionButton("Open 3D Viewer", "route:viewer", "ghost")}
                </div>
              `,
            )}
          </div>
          ${cubeNetCard({}, null, "Placeholder cube net", {
            activeLabel: "Waiting for first scan",
            footerHtml: `<p class="support-text">Once faces are captured, the editable net appears here for final review and manual corrections.</p>`,
          })}
        </div>
      </div>
    `;
  }

  return `
    <div class="stack-lg">
      ${sectionHeader("Review", "Confirm and correct the cube", "Inspect the captured net, make any small sticker fixes, and validate the final cube before solving.")}
      <div class="two-column-grid">
        ${cubeNetCard(review.faces, null, "Editable cube net", {
          editable: true,
          manualMask: review.manualMask,
          lockCenters: review.centersLocked,
          activeLabel: review.manualEditCount ? "Manual edits applied" : "Scanned cube state",
          footerHtml: renderEditFooter(review),
        })}
        <div class="stack-md">
          ${validationCard(review)}
          ${renderSelectedStickerEditor(review, app)}
          ${renderReviewActions(review)}
          ${betaFeatureCard({
            title: "Try CFOP Beta",
            description: "Experimental. PyCube-backed and improving, but still not the default path.",
            actionLabel: "Open Solve Screen",
            action: "route:solve",
          })}
        </div>
      </div>
    </div>
  `;
}
