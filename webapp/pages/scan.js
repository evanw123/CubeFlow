import { COLOR_HEX, advancedDrawer, cubeNetCard, progressStepper } from "../components/cards.js";
import { actionButton, statusChip } from "../components/ui.js";
import { commandLabel, escapeHtml } from "../lib/format.js";
import { browserScanner } from "../lib/browser-scanner.js";

function renderAdvanced(scanner) {
  const advanced = scanner?.advanced || {};
  return advancedDrawer(
    "Advanced scanner diagnostics",
    `
      <div class="advanced-grid">
        <div>
          <h4>Validation errors</h4>
          <ul>${(advanced.validationErrors || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>None</li>"}</ul>
        </div>
        <div>
          <h4>Deep validation</h4>
          <ul>${(advanced.deepValidationErrors || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>None</li>"}</ul>
        </div>
        <div>
          <h4>Color counts</h4>
          <pre>${escapeHtml(JSON.stringify(advanced.counts || {}, null, 2))}</pre>
        </div>
        <div>
          <h4>Calibration</h4>
          <pre>${escapeHtml(JSON.stringify(advanced.calibration || {}, null, 2))}</pre>
        </div>
      </div>
    `,
  );
}

function renderPreviewFrame(scanner) {
  const cameraIsActive = browserScanner.running;
  return `
    <div class="scanner-preview-stack browser-camera" data-browser-camera>
      <video class="scanner-preview" data-browser-video autoplay muted playsinline aria-label="Live browser camera preview"></video>
      <canvas data-browser-sampling-canvas hidden></canvas>
      <div class="browser-camera__guide" aria-hidden="true">
        ${Array.from({ length: 9 }, () => '<span class="browser-camera__cell"></span>').join("")}
      </div>
      <div class="scanner-preview-stack__badge" data-browser-camera-status>
        ${statusChip(scanner?.running ? "Camera ready" : "Camera off", scanner?.running ? "success" : "neutral")}
      </div>
      <div class="browser-camera__actions">
        <button class="button button--primary" type="button" data-camera-action="start" ${cameraIsActive ? "disabled" : ""}>${cameraIsActive ? "Camera Active" : "Start Camera"}</button>
        <button class="button button--secondary" type="button" data-camera-action="stop" ${cameraIsActive ? "" : "disabled"}>Stop</button>
      </div>
      <div class="scanner-preview-stack__hint">Center one cube face in the 3×3 guide. Keep the requested top color at the top.</div>
    </div>
  `;
}

function renderInstructionCard(scanner) {
  const previewTone = !scanner?.running ? "neutral" : scanner?.previewAvailable ? "success" : "warning";
  const previewLabel = !scanner?.running
    ? "Scanner offline"
    : !scanner?.stateAvailable
      ? "Launching scanner"
      : scanner?.previewAvailable
        ? "Preview live"
        : "Preview connecting";

  return `
    <div>
      <div class="card__eyebrow">Current instruction</div>
      <h3>${escapeHtml(scanner.instruction || `Show ${commandLabel(scanner.currentSlot)} face`)}</h3>
      <p>${escapeHtml(scanner.orientationHint || "Keep the requested top color visible.")}</p>
      <div class="support-text">1. Match the face and top color. 2. Wait for the face to turn stable. 3. Capture once the status turns ready.</div>
    </div>
    <div class="instruction-card__chips">
      ${statusChip(scanner.captureReady ? "Ready to capture" : scanner.captureStatus || "Waiting for stable face", scanner.captureReady ? "success" : scanner.captureStatusTone || (scanner.faceStable ? "warning" : "neutral"))}
      ${statusChip(scanner.centerMatches ? "Center matches" : "Center mismatch", scanner.centerMatches ? "success" : "danger")}
      ${statusChip(scanner.advanced?.solverReady ? "Solver ready" : "Not solver-ready", scanner.advanced?.solverReady ? "success" : "warning")}
      ${statusChip(previewLabel, previewTone)}
    </div>
  `;
}

function renderCaptureActions(scanner) {
  return `
    <div class="card scan-action-card">
      <div class="card__header card__header--tight">
        <div>
          <div class="card__eyebrow">Capture controls</div>
          <h3>Capture ${escapeHtml(commandLabel(scanner.currentSlot))} face</h3>
          <p>Use Capture when the live grid is stable and the center matches.</p>
        </div>
      </div>
      <div class="cta-row cta-row--wrap">
        ${actionButton("Capture", "command:capture", "primary", scanner.captureReady ? "" : "disabled")}
        ${actionButton("Next", "command:next-step", "secondary")}
        ${actionButton("Previous", "command:previous-step", "secondary")}
        ${actionButton("Clear Face", "command:clear-face", "ghost")}
        ${actionButton("Reset Cube", "command:reset-cube", "ghost")}
      </div>
    </div>
  `;
}

function updateIfChanged(node, html) {
  if (!node) return;
  if (node.dataset.renderSignature === html) return;
  node.innerHTML = html;
  node.dataset.renderSignature = html;
}

function renderRecognitionGrid(scanner) {
  const grid = scanner?.liveRecognitionGrid || [["UNKNOWN", "UNKNOWN", "UNKNOWN"], ["UNKNOWN", "UNKNOWN", "UNKNOWN"], ["UNKNOWN", "UNKNOWN", "UNKNOWN"]];
  const stable = scanner?.liveRecognitionStableGrid || [[false, false, false], [false, false, false], [false, false, false]];

  return `
    <div class="card recognition-card">
      <div class="card__header card__header--tight">
        <div>
          <div class="card__eyebrow">Recognition preview</div>
          <h3>What the scanner sees</h3>
        </div>
        ${statusChip(scanner.captureReady ? "Ready" : scanner.faceStable ? "Stable" : "Scanning", scanner.captureReady ? "success" : scanner.faceStable ? "warning" : "neutral")}
      </div>
      <div class="recognition-grid">
        ${grid.flatMap((row, rowIndex) => row.map((color, colIndex) => `
          <div class="recognition-grid__sticker ${stable[rowIndex]?.[colIndex] ? "is-stable" : ""}" style="background:${COLOR_HEX[color] || COLOR_HEX.UNKNOWN}">
            ${stable[rowIndex]?.[colIndex] ? '<span class="recognition-grid__dot"></span>' : ""}
          </div>
        `)).join("")}
      </div>
      <p class="support-text">This 3×3 grid is the live interpreted face. Solid dots mean each sticker reading is stable enough to trust.</p>
    </div>
  `;
}

function renderCaptureFeedback(scanner) {
  const tone = scanner?.captureReady ? "success" : scanner?.centerMatches ? scanner?.faceStable ? "warning" : "neutral" : "danger";
  const headline = scanner?.captureReady
    ? "Ready to capture"
    : !scanner?.centerMatches
      ? "Wrong center / orientation"
      : scanner?.faceStable
        ? "Stable, checking center"
        : "Waiting for a stable face";
  const detail = scanner?.lastCaptureMessage
    ? `${scanner.lastCaptureMessage}. The 2D net updates right after every capture.`
    : "Keep the cube steady inside the guide and watch the recognition grid until it settles.";

  return `
    <div class="card capture-feedback-card">
      <div class="card__header card__header--tight">
        <div>
          <div class="card__eyebrow">Capture status</div>
          <h3>${escapeHtml(headline)}</h3>
        </div>
        ${statusChip(scanner?.captureStatus || "Waiting", tone)}
      </div>
      <p class="muted">${escapeHtml(detail)}</p>
      <div class="capture-feedback-card__meta">
        <div>
          <span>Expected center</span>
          <strong>${escapeHtml(scanner?.expectedCenter || "—")}</strong>
        </div>
        <div>
          <span>Detected center</span>
          <strong>${escapeHtml(scanner?.centerLabel || "Unknown")}</strong>
        </div>
        <div>
          <span>Captured faces</span>
          <strong>${escapeHtml(String(scanner?.capturedFaceCount || 0))} / 6</strong>
        </div>
      </div>
    </div>
  `;
}

function renderHealthCard(scanner) {
  const processLabel = scanner?.source === "browser" ? (scanner?.running ? "Browser camera" : "Stopped") : scanner?.processRunning ? "Native fallback" : scanner?.running ? "Launching" : "Offline";
  const previewLabel = scanner?.previewAvailable ? "Live in browser" : scanner?.running ? "Connecting" : "Unavailable";
  const stateLabel = scanner?.stateAvailable ? "Fresh" : "Stale";

  return `
    <div class="card compact-status-card">
      <div class="card__header card__header--tight">
        <div>
          <div class="card__eyebrow">Status</div>
          <h3>Scanner health</h3>
        </div>
      </div>
      <div class="metric-list">
        <div><span>Process</span><strong>${escapeHtml(processLabel)}</strong></div>
        <div><span>Preview</span><strong>${escapeHtml(previewLabel)}</strong></div>
        <div><span>State</span><strong>${escapeHtml(stateLabel)}</strong></div>
        <div><span>Stability</span><strong>${scanner?.faceStable ? "Stable" : "Settling"}</strong></div>
        <div><span>Center</span><strong>${escapeHtml(scanner?.centerLabel || "Unknown")}</strong></div>
        <div><span>Expected</span><strong>${escapeHtml(scanner?.expectedCenter || "—")}</strong></div>
      </div>
      ${scanner?.lastError ? `<div class="notice notice--warning">${escapeHtml(scanner.lastError)}</div>` : ""}
      <div class="card__actions">
        ${actionButton("Validate", "command:validate", "secondary")}
        ${actionButton("Go to Review", "route:review", "ghost")}
      </div>
    </div>
  `;
}

function renderCalibrationCard(scanner, calibration) {
  const rows = calibration?.rows || [];
  const detectedCenter = scanner?.centerLabel || "Unknown";
  const currentSample = Array.isArray(scanner?.currentCenterBgr) ? scanner.currentCenterBgr.join(", ") : "No live sample";

  return `
    <div class="card calibration-card" data-scan-calibration-card>
      <div class="card__header card__header--tight">
        <div>
          <div class="card__eyebrow">Calibration</div>
          <h3>Cube colors</h3>
          <p>Point the center sticker at the scanner, then capture the current center color.</p>
        </div>
        ${statusChip(calibration?.allCaptured ? "All calibrated" : `${calibration?.capturedCount || 0} / 6 captured`, calibration?.allCaptured ? "success" : "warning")}
      </div>
      <div class="calibration-card__meta">
        <div>
          <span>Detected center</span>
          <strong>${escapeHtml(detectedCenter)}</strong>
        </div>
        <div>
          <span>Current sample</span>
          <strong>${escapeHtml(currentSample)}</strong>
        </div>
      </div>
      <div class="calibration-list">
        ${rows.map((row) => `
          <div class="calibration-row">
            <div class="calibration-row__color">
              <span class="calibration-row__swatch" style="background:${COLOR_HEX[row.name] || COLOR_HEX.UNKNOWN}"></span>
              <div>
                <strong>${escapeHtml(row.name)}</strong>
                <div>${statusChip(row.captured ? "Calibrated" : "Missing", row.captured ? "success" : "neutral")}</div>
              </div>
            </div>
            <div class="calibration-row__actions">
              <button
                type="button"
                class="button button--secondary"
                data-calibration-capture="${escapeHtml(row.name)}"
                ${scanner?.running && Array.isArray(scanner?.currentCenterBgr) ? "" : "disabled"}
              >
                Capture current center
              </button>
              <button
                type="button"
                class="button button--ghost"
                data-calibration-clear="${escapeHtml(row.name)}"
                ${row.captured ? "" : "disabled"}
              >
                Clear
              </button>
            </div>
          </div>
        `).join("")}
      </div>
      <div class="card__actions">
        <button
          type="button"
          class="button button--ghost"
          data-calibration-clear-all
          ${calibration?.capturedCount ? "" : "disabled"}
        >
          Clear all calibration
        </button>
      </div>
    </div>
  `;
}

function renderScanPageBody(state) {
  const scanner = state.scanner || {};
  const calibration = state.calibration || {};
  return `
    <div class="scan-layout" data-scan-page>
      <aside class="scan-camera-pane" aria-label="Live scanner camera">
        <div class="card scanner-card">
          <div class="scanner-card__frame" data-scan-preview-frame>${renderPreviewFrame(scanner)}</div>
        </div>
        <div class="scan-context-stack">
          <div class="card instruction-card" data-scan-instruction-card>${renderInstructionCard(scanner)}</div>
          <div data-scan-recognition>${renderRecognitionGrid(scanner)}</div>
        </div>
      </aside>
      <section class="scan-task-pane" aria-label="Scan controls and capture progress">
        <div class="scan-control-stack">
          <div data-scan-capture-actions>${renderCaptureActions(scanner)}</div>
          <div data-scan-capture-feedback>${renderCaptureFeedback(scanner)}</div>
          <div class="card scan-progress-card">
            <div class="card__header card__header--tight">
              <div>
                <div class="card__eyebrow">Face progress</div>
                <h3>Scan order</h3>
                <p>Keep the camera visible and work through the six faces in order.</p>
              </div>
            </div>
            <div data-scan-stepper>${progressStepper(scanner)}</div>
          </div>
          <div data-scan-calibration>${renderCalibrationCard(scanner, calibration)}</div>
          <div data-scan-cube-net>${cubeNetCard(scanner.faces, scanner.currentSlot, "Captured faces", { activeLabel: scanner.lastCaptureMessage || "Live cube net" })}</div>
          <div data-scan-health>${renderHealthCard(scanner)}</div>
          <div data-scan-advanced>${renderAdvanced(scanner)}</div>
        </div>
      </section>
    </div>
  `;
}

export function renderScanPage(state) {
  return renderScanPageBody(state);
}

export function patchScanPage(state) {
  const scanner = state.scanner || {};
  const calibration = state.calibration || {};
  const page = document.querySelector("[data-scan-page]");
  if (!page) return false;

  const stepper = page.querySelector("[data-scan-stepper]");
  if (stepper) updateIfChanged(stepper, progressStepper(scanner));

  const instructionCard = page.querySelector("[data-scan-instruction-card]");
  if (instructionCard) updateIfChanged(instructionCard, renderInstructionCard(scanner));

  const captureActions = page.querySelector("[data-scan-capture-actions]");
  if (captureActions) updateIfChanged(captureActions, renderCaptureActions(scanner));

  const recognition = page.querySelector("[data-scan-recognition]");
  if (recognition) updateIfChanged(recognition, renderRecognitionGrid(scanner));

  const captureFeedback = page.querySelector("[data-scan-capture-feedback]");
  if (captureFeedback) updateIfChanged(captureFeedback, renderCaptureFeedback(scanner));

  const advanced = page.querySelector("[data-scan-advanced]");
  if (advanced) updateIfChanged(advanced, renderAdvanced(scanner));

  const cubeNet = page.querySelector("[data-scan-cube-net]");
  if (cubeNet) updateIfChanged(cubeNet, cubeNetCard(scanner.faces, scanner.currentSlot, "Captured faces", { activeLabel: scanner.lastCaptureMessage || "Live cube net" }));

  const health = page.querySelector("[data-scan-health]");
  if (health) updateIfChanged(health, renderHealthCard(scanner));

  const calibrationCard = page.querySelector("[data-scan-calibration]");
  if (calibrationCard) updateIfChanged(calibrationCard, renderCalibrationCard(scanner, calibration));

  return true;
}

export function hydrateScanPage(app) {
  const page = document.querySelector("[data-scan-page]");
  const video = page?.querySelector("[data-browser-video]");
  const canvas = page?.querySelector("[data-browser-sampling-canvas]");
  if (!page || !video || !canvas) return;

  browserScanner.attach({
    video,
    canvas,
    onState: (nextState) => {
      app.state = nextState;
      app.lastStateSignature = JSON.stringify(nextState);
      patchScanPage(nextState);
    },
    onStatus: ({ state: cameraState, message }) => updateCameraStatus(cameraState, message),
  });
}

function updateCameraStatus(cameraState, message) {
  const status = document.querySelector("[data-browser-camera-status]");
  const start = document.querySelector('[data-camera-action="start"]');
  const stop = document.querySelector('[data-camera-action="stop"]');
  const tone = cameraState === "error" ? "danger" : ["ready", "scanning"].includes(cameraState) ? "success" : cameraState === "requesting" ? "warning" : "neutral";
  const cameraIsActive = ["ready", "scanning"].includes(cameraState);
  if (status) status.innerHTML = statusChip(message || "Camera off", tone);
  if (start) {
    start.disabled = cameraState === "requesting" || cameraIsActive;
    start.textContent = cameraState === "requesting" ? "Starting..." : cameraIsActive ? "Camera Active" : "Start Camera";
  }
  if (stop) stop.disabled = !cameraIsActive;
}

export async function startBrowserCamera() {
  await browserScanner.start();
}

export function stopBrowserCamera() {
  browserScanner.stop();
}
