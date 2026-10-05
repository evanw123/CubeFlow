let memorySessionId = null;

function createSessionId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const bytes = new Uint8Array(16);
  globalThis.crypto?.getRandomValues?.(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function getSessionId() {
  if (memorySessionId) return memorySessionId;
  try {
    const stored = globalThis.sessionStorage?.getItem("cubeflow.session");
    if (stored) {
      memorySessionId = stored;
      return memorySessionId;
    }
  } catch (_error) {
    // Privacy modes may disable storage; the in-memory ID still isolates this page.
  }
  memorySessionId = createSessionId();
  try {
    globalThis.sessionStorage?.setItem("cubeflow.session", memorySessionId);
  } catch (_error) {
    // Keep the generated in-memory ID.
  }
  return memorySessionId;
}

async function request(path, options = {}) {
  const { headers: optionHeaders = {}, ...requestOptions } = options;
  const response = await fetch(path, {
    ...requestOptions,
    headers: {
      "Content-Type": "application/json",
      "X-CubeFlow-Session": getSessionId(),
      ...optionHeaders,
    },
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json() : null;

  if (!response.ok) {
    throw new Error(payload?.error || `Request failed: ${response.status}`);
  }

  return payload;
}

export const api = {
  getState: () => request("/api/state"),
  getScannerState: () => request("/api/scanner/state"),
  getCalibration: () => request("/api/calibration"),
  getEvaluation: () => request("/api/evaluation"),
  saveSettings: (settings) => request("/api/settings", { method: "POST", body: JSON.stringify(settings) }),
  resetState: () => request("/api/state/reset", { method: "POST" }),
  launchScanner: () => request("/api/actions/launch-scanner", { method: "POST" }),
  openViewer: () => request("/api/actions/open-viewer", { method: "POST" }),
  queueCommand: (action, payload = {}) => request("/api/actions/command", { method: "POST", body: JSON.stringify({ action, payload }) }),
  setBrowserCameraRunning: (running, error = null) => request("/api/scanner/camera", { method: "POST", body: JSON.stringify({ running, error }) }),
  submitBrowserSamples: (payload) => request("/api/scanner/samples", { method: "POST", body: JSON.stringify(payload) }),
  runBrowserScannerAction: (action) => request("/api/scanner/action", { method: "POST", body: JSON.stringify({ action }) }),
  updateEvaluationTrial: (payload) => request("/api/evaluation/trial", { method: "POST", body: JSON.stringify(payload) }),
  sendClientInfo: (payload) => request("/api/evaluation/client-info", { method: "POST", body: JSON.stringify(payload) }),
  reportPreviewMetrics: (payload) => request("/api/evaluation/preview-metrics", { method: "POST", body: JSON.stringify(payload) }),
  captureCalibration: (color) => request("/api/calibration/capture", { method: "POST", body: JSON.stringify({ color }) }),
  clearCalibration: (color) => request("/api/calibration/clear", { method: "POST", body: JSON.stringify({ color }) }),
  clearAllCalibration: () => request("/api/calibration/clear_all", { method: "POST" }),
  editSticker: (slot, row, col, color) => request("/api/cube/edit", { method: "POST", body: JSON.stringify({ slot, row, col, color }) }),
  undoStickerEdit: () => request("/api/cube/undo", { method: "POST" }),
  resetStickerEdits: () => request("/api/cube/reset-edits", { method: "POST" }),
  getViewerSession: (mode) => request("/api/viewer/session", { method: "POST", body: JSON.stringify({ mode }) }),
  solveStandard: () => request("/api/solve/standard", { method: "POST" }),
  solveCfop: () => request("/api/solve/cfop", { method: "POST" }),
  playbackStandard: () => request("/api/playback/standard", { method: "POST" }),
  playbackCfop: () => request("/api/playback/cfop", { method: "POST" }),
};
