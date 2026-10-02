import { escapeHtml } from "../lib/format.js";

export function betaBadge(label = "Beta") {
  return `<span class="beta-badge">${escapeHtml(label)}</span>`;
}

export function statusChip(label, tone = "neutral") {
  return `<span class="status-chip status-chip--${escapeHtml(tone)}">${escapeHtml(label)}</span>`;
}

export function actionButton(label, action, variant = "secondary", extra = "") {
  return `<button class="button button--${escapeHtml(variant)}" data-action="${escapeHtml(action)}" ${extra}>${escapeHtml(label)}</button>`;
}

export function iconTile(label, detail, tone = "accent") {
  return `
    <div class="icon-tile icon-tile--${escapeHtml(tone)}">
      <div class="icon-tile__orb"></div>
      <div>
        <div class="icon-tile__label">${escapeHtml(label)}</div>
        <div class="icon-tile__detail">${escapeHtml(detail)}</div>
      </div>
    </div>
  `;
}

export function emptyState(title, description, actions = "") {
  return `
    <div class="empty-state">
      <div class="empty-state__glyph">◎</div>
      <h3>${escapeHtml(title)}</h3>
      <p>${escapeHtml(description)}</p>
      ${actions ? `<div class="empty-state__actions">${actions}</div>` : ""}
    </div>
  `;
}
