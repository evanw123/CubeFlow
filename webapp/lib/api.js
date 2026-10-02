async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
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
