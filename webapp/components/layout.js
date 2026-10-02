import { escapeHtml } from "../lib/format.js";

const NAV_ITEMS = [
  ["home", "Home"],
  ["scan", "Scan"],
  ["review", "Review"],
  ["solve", "Solve"],
  ["viewer", "3D Viewer"],
  ["settings", "Settings"],
];

export function renderAppShell({ route, state, pageTitle, pageDescription, pageHtml, toast, isLoading }) {
  const subtitle = state?.app?.subtitle || "Scan, validate, and solve your Rubik's cube.";
  const modeLabel = state?.settings?.debugMode ? "Advanced Mode" : "Normal Mode";

  return `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand-card">
          <div class="brand-mark">
            <span></span><span></span><span></span>
            <span></span><span></span><span></span>
            <span></span><span></span><span></span>
          </div>
          <div>
            <div class="brand-card__title">CubeFlow</div>
            <div class="brand-card__subtitle">${escapeHtml(subtitle)}</div>
          </div>
        </div>
        <nav class="sidebar__nav">
          ${NAV_ITEMS.map(([key, label]) => `<button class="nav-item ${route === key ? "is-active" : ""}" data-route="${key}">${escapeHtml(label)}</button>`).join("")}
        </nav>
        <div class="sidebar__footer">
          <div class="sidebar__mode">${escapeHtml(modeLabel)}</div>
          <div class="sidebar__hint">Stable solve stays primary. CFOP remains clearly beta.</div>
        </div>
      </aside>
      <main class="main-panel">
        <header class="topbar">
          <div>
            <div class="topbar__eyebrow">CubeFlow App</div>
            <h1>${escapeHtml(pageTitle)}</h1>
            <p>${escapeHtml(pageDescription)}</p>
          </div>
          <div class="topbar__actions">
            <button class="button button--ghost" data-action="launch-scanner">${state?.scanner?.running ? "Scanner Running" : "Launch Scanner"}</button>
            <button class="button button--secondary" data-route="settings">Settings</button>
          </div>
        </header>
        ${toast ? `<div class="toast toast--${escapeHtml(toast.tone || "neutral")}">${escapeHtml(toast.message)}</div>` : ""}
        ${isLoading ? `<div class="loading-banner">Refreshing app state…</div>` : ""}
        <section class="page-grid">${pageHtml}</section>
      </main>
    </div>
  `;
}
