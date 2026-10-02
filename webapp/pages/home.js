import { cubeNetCard, sectionHeader, validationCard, betaFeatureCard } from "../components/cards.js";
import { actionButton, iconTile } from "../components/ui.js";
import { escapeHtml, formatTimestamp } from "../lib/format.js";

export function renderHomePage(state) {
  const review = state.review || {};
  const home = state.home || {};
  const labs = state.labs?.cfopBeta || {};

  return `
    <div class="stack-lg">
      ${sectionHeader("Home", "Scan. Validate. Solve.", "A calmer, clearer shell around the working scanner and solver backend.")}
      <div class="hero-grid">
        <div class="card hero-card">
          <div class="hero-card__content">
            <div>
              <div class="hero-card__eyebrow">Primary workflow</div>
              <h2>${escapeHtml(home.heroTitle || "Scan your cube and solve it")}</h2>
              <p>${escapeHtml(home.heroSubtitle || "Use your camera to capture each face, review the state, and run the stable solver.")}</p>
            </div>
            <div class="hero-card__actions">
              ${actionButton("Scan Cube", "launch-scanner", "primary")}
              ${actionButton("Review Last Scan", "route:review", "secondary")}
              ${actionButton("Open 3D Viewer", "open-viewer", "ghost")}
            </div>
            <div class="hero-highlights">
              ${iconTile("Last status", home.lastValidationLabel || "No scan yet")}
              ${iconTile("Last scan", formatTimestamp(home.lastScannedAt), "calm")}
            </div>
          </div>
          <div class="hero-cube">
            <div class="hero-cube__face hero-cube__face--front"></div>
            <div class="hero-cube__face hero-cube__face--top"></div>
            <div class="hero-cube__face hero-cube__face--side"></div>
          </div>
        </div>
        <div class="stack-md">
          <div class="card action-card-list">
            <div class="card__header card__header--tight">
              <div>
                <div class="card__eyebrow">Quick actions</div>
                <h3>Main destinations</h3>
              </div>
            </div>
            <div class="action-card-list__grid">
              <button class="action-card" data-route="scan"><span>Scan</span><small>Capture the six faces</small></button>
              <button class="action-card" data-route="review"><span>Review</span><small>Check the current cube state</small></button>
              <button class="action-card" data-route="solve"><span>Solve</span><small>Run standard or beta solve paths</small></button>
              <button class="action-card" data-route="viewer"><span>3D Viewer</span><small>Playback and inspect the cube</small></button>
            </div>
          </div>
          ${betaFeatureCard({
            title: labs.label || "CFOP Beta",
            description: labs.description || "Experimental. May be incomplete or fail on some cases.",
            actionLabel: "Open Solve Options",
            action: "route:solve",
          })}
        </div>
      </div>
      <div class="two-column-grid">
        ${validationCard(review)}
        ${cubeNetCard(review.faces, null, "Latest cube net")}
      </div>
    </div>
  `;
}
