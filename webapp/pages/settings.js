import { sectionHeader } from "../components/cards.js";
import { actionButton, statusChip } from "../components/ui.js";
import { escapeHtml } from "../lib/format.js";

function settingToggle(label, description, key, checked) {
  return `
    <label class="setting-row">
      <div>
        <strong>${escapeHtml(label)}</strong>
        <p>${escapeHtml(description)}</p>
      </div>
      <input type="checkbox" data-setting-key="${escapeHtml(key)}" ${checked ? "checked" : ""} />
    </label>
  `;
}

function renderEvaluationCard(state) {
  const evaluation = state.evaluation || {};
  const trial = evaluation.currentTrial || {};
  const solver = trial.solver || {};
  const exportUrls = evaluation.exportUrls || {};

  return `
    <div class="card">
      <div class="card__header">
        <div>
          <div class="card__eyebrow">Evaluation</div>
          <h2>Trial logging and export</h2>
          <p>Keep technical study data out of the beginner flow, but make it easy to export one clean run for evaluation and demos.</p>
        </div>
        ${statusChip(trial.scanCompletedAt ? "Ready to export" : "In progress", trial.scanCompletedAt ? "success" : "warning")}
      </div>
      <div class="field-grid">
        <label class="field">
          <span>Trial identifier</span>
          <input
            type="text"
            data-eval-field="trialId"
            value="${escapeHtml(trial.trialId || "")}"
            placeholder="demo-01"
          />
        </label>
        <label class="field">
          <span>Lighting condition</span>
          <input
            type="text"
            data-eval-field="lightingCondition"
            value="${escapeHtml(trial.lightingCondition || "")}"
            placeholder="Desk lamp / daylight / overhead LEDs"
          />
        </label>
      </div>
      <div class="cta-row cta-row--wrap">
        <button class="button button--secondary" type="button" data-evaluation-action="save-trial">Save trial details</button>
        <button class="button button--ghost" type="button" data-evaluation-action="new-trial">Start new trial</button>
      </div>
      <div class="metric-list">
        <div><span>Trial started</span><strong>${escapeHtml(trial.trialStartedAt || "Not started")}</strong></div>
        <div><span>Scan started</span><strong>${escapeHtml(trial.scanStartedAt || "Waiting for first capture")}</strong></div>
        <div><span>Scan completed</span><strong>${escapeHtml(trial.scanCompletedAt || "Not complete")}</strong></div>
        <div><span>Calibration used</span><strong>${trial.calibrationEnabled ? "Yes" : "No"}</strong></div>
        <div><span>Manual corrections</span><strong>${escapeHtml(String((trial.manualCorrections || []).length || 0))}</strong></div>
        <div><span>Preview FPS (approx.)</span><strong>${trial.previewFpsApprox ? escapeHtml(String(trial.previewFpsApprox)) : "Pending"}</strong></div>
        <div><span>Solver result</span><strong>${solver.kind ? `${escapeHtml(String(solver.kind))} · ${solver.success ? "success" : "failed"}` : "Not run yet"}</strong></div>
      </div>
      <div class="export-actions">
        <button class="button button--primary" type="button" data-evaluation-action="export-json" data-download-url="${escapeHtml(exportUrls.json || "/api/evaluation/export.json")}">Export JSON</button>
        <button class="button button--secondary" type="button" data-evaluation-action="export-csv" data-download-url="${escapeHtml(exportUrls.csv || "/api/evaluation/export.csv")}">Export CSV</button>
      </div>
      <p class="support-text">Exports include capture timing, recognized sticker colors, manual corrections, validation status, solve outcome, and preview performance.</p>
    </div>
  `;
}

function renderSystemInfoCard(state) {
  const system = state.evaluation?.systemInfo || {};
  const browser = system.browser || {};
  const camera = system.camera || {};
  const preview = system.preview || {};
  const solvers = system.solvers || {};
  const exportUrl = state.evaluation?.exportUrls?.system || "/api/evaluation/system-info.json";
  const resolution = camera.resolution
    ? `${camera.resolution.width} × ${camera.resolution.height}`
    : "Unavailable";

  return `
    <div class="card">
      <div class="card__header card__header--tight">
        <div>
          <div class="card__eyebrow">Advanced</div>
          <h3>System information</h3>
        </div>
      </div>
      <div class="metric-list">
        <div><span>Python</span><strong>${escapeHtml(system.pythonVersion || "Unavailable")}</strong></div>
        <div><span>OpenCV</span><strong>${escapeHtml(system.opencvVersion || "Unavailable")}</strong></div>
        <div><span>Camera resolution</span><strong>${escapeHtml(resolution)}</strong></div>
        <div><span>Preview target FPS</span><strong>${escapeHtml(String(preview.configuredTargetFps || "—"))}</strong></div>
        <div><span>Browser / app</span><strong>${escapeHtml(browser.appVersion || browser.userAgent || "Pending browser report")}</strong></div>
        <div><span>Standard solver</span><strong>${escapeHtml(solvers.standard?.engine || "kociemba")}${solvers.standard?.version ? ` · ${escapeHtml(String(solvers.standard.version))}` : ""}</strong></div>
        <div><span>CFOP Beta engine</span><strong>${escapeHtml(solvers.cfopBeta?.engine || "PyCube-Solver")}${solvers.cfopBeta?.version ? ` · ${escapeHtml(String(solvers.cfopBeta.version))}` : ""}</strong></div>
      </div>
      <div class="cta-row">
        <button class="button button--ghost" type="button" data-evaluation-action="export-system" data-download-url="${escapeHtml(exportUrl)}">Export system info</button>
      </div>
    </div>
  `;
}

export function renderSettingsPage(state) {
  const settings = state.settings || {};
  const shortcuts = state.shortcuts || [];

  return `
    <div class="stack-lg">
      ${sectionHeader("Settings", "Control the app shell", "Keep the main experience calm by default and move lower-level diagnostics behind deliberate toggles.")}
      <div class="two-column-grid">
        <div class="stack-md">
          <div class="card">
            <div class="card__header">
              <div>
                <div class="card__eyebrow">Preferences</div>
                <h2>App behavior</h2>
              </div>
              ${statusChip(settings.debugMode ? "Advanced Mode" : "Normal Mode", settings.debugMode ? "warning" : "success")}
            </div>
            <div class="setting-list">
              ${settingToggle("Debug mode", "Show lower-level diagnostics and expose the app as advanced mode.", "debugMode", settings.debugMode)}
              ${settingToggle("Show advanced scanner info", "Expose calibration and validation details in the Scan experience.", "showAdvancedScannerInfo", settings.showAdvancedScannerInfo)}
              ${settingToggle("Enable beta features", "Keep CFOP Beta visible in the product shell.", "betaFeaturesEnabled", settings.betaFeaturesEnabled)}
              ${settingToggle("Show analysis overlay", "Use optional analysis overlays when playback supports them.", "showAnalysisOverlay", settings.showAnalysisOverlay)}
            </div>
          </div>
          <div class="card">
            <div class="card__header card__header--tight">
              <div>
                <div class="card__eyebrow">Maintenance</div>
                <h3>Reset state</h3>
              </div>
            </div>
            <p class="muted">Resetting clears the app shell state and any saved solve summaries, but preserves the underlying backend code and viewer.</p>
            <div class="cta-row">
              ${actionButton("Reset App State", "reset-state", "ghost")}
            </div>
          </div>
        </div>
        <div class="stack-md">
          ${renderEvaluationCard(state)}
          <div class="card">
            <div class="card__header card__header--tight">
              <div>
                <div class="card__eyebrow">Device</div>
                <h3>Camera and controls</h3>
              </div>
            </div>
            <div class="metric-list">
              <div><span>Theme</span><strong>${escapeHtml(settings.theme || "dark")}</strong></div>
              <div><span>Accent</span><strong>${escapeHtml(settings.accentColor || "cyan")}</strong></div>
              <div><span>Camera device</span><strong>${escapeHtml(String(settings.cameraDeviceIndex ?? 0))}</strong></div>
            </div>
          </div>
          <div class="card">
            <div class="card__header card__header--tight">
              <div>
                <div class="card__eyebrow">Help</div>
                <h3>Keyboard shortcuts</h3>
              </div>
            </div>
            <div class="shortcut-list">
              ${shortcuts.map((shortcut) => `<div class="shortcut-item"><kbd>${escapeHtml(shortcut.key)}</kbd><span>${escapeHtml(shortcut.label)}</span></div>`).join("")}
            </div>
          </div>
          ${renderSystemInfoCard(state)}
        </div>
      </div>
    </div>
  `;
}
