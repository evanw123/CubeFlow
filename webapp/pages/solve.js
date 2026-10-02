import { betaFeatureCard, sectionHeader, solveResultCard } from "../components/cards.js";
import { actionButton, emptyState, statusChip } from "../components/ui.js";
import { escapeHtml } from "../lib/format.js";

export function renderSolvePage(state) {
  const review = state.review || {};
  const standard = state.solves?.standard;
  const cfop = state.solves?.cfop;

  if (!review.capturedFaceCount) {
    return `
      <div class="stack-lg">
        ${sectionHeader("Solve", "Choose a solve path", "Standard solve stays primary. CFOP remains clearly experimental.")}
        ${emptyState("No cube ready yet", "Capture and review a cube first, then come back here to solve it.", actionButton("Go to Scan", "route:scan", "primary"))}
      </div>
    `;
  }

  return `
    <div class="stack-lg">
      ${sectionHeader("Solve", "Standard first, experiments second", "The stable Kociemba-based solve is the main path. CFOP Beta is visible, but clearly secondary.")}
      <div class="solve-layout">
        <div class="stack-md">
          <div class="card solve-choice-card solve-choice-card--primary">
            <div class="card__header">
              <div>
                <div class="card__eyebrow">Primary</div>
                <h2>Standard Solve</h2>
                <p>Stable, reliable, and the default solve path for the product.</p>
              </div>
              ${statusChip("Stable", "success")}
            </div>
            <div class="cta-row">
              ${actionButton("Run Standard Solve", "solve-standard", "primary")}
              ${actionButton("Back to Review", "route:review", "secondary")}
            </div>
          </div>
          ${solveResultCard(standard, { beta: false })}
        </div>
        <div class="stack-md">
          <div class="card solve-choice-card solve-choice-card--beta">
            <div class="card__header">
              <div>
                <div class="card__eyebrow">Labs</div>
                <h2>CFOP Beta</h2>
                <p>Experimental. Powered by PyCube-Solver. Use it as a preview of the human-style path, not the main solve option.</p>
              </div>
              ${statusChip("BETA", "warning")}
            </div>
            <div class="notice notice--warning">If CFOP Beta cannot solve this cube yet, the app will steer you back to Standard Solve instead of feeling broken.</div>
            <div class="cta-row">
              ${actionButton("Run CFOP Beta", "solve-cfop", "ghost")}
              ${actionButton("Open Viewer", "route:viewer", "secondary")}
            </div>
          </div>
          ${solveResultCard(cfop, { beta: true })}
          ${betaFeatureCard({ title: "Why beta?", description: "CFOP is still being expanded and is deliberately de-emphasized so the product stays trustworthy.", actionLabel: "Back to Stable Solve", action: "solve-standard" })}
        </div>
      </div>
    </div>
  `;
}
