import { renderAppShell } from "./components/layout.js";
import { renderHomePage } from "./pages/home.js";
import { hydrateScanPage, patchScanPage, renderScanPage, startBrowserCamera, stopBrowserCamera } from "./pages/scan.js";
import { renderReviewPage } from "./pages/review.js";
import { animateViewerTurn, hydrateViewerPage, renderViewerPage } from "./pages/viewer.js";
import { renderSolvePage } from "./pages/solve.js";
import { renderSettingsPage } from "./pages/settings.js";
import { api } from "./lib/api.js";
import { getViewerKeyboardAction } from "./lib/viewer-keyboard.js";

const root = document.getElementById("app");
const DEFAULT_VIEWER_CAMERA = Object.freeze({ yaw: -32, pitch: -28, zoom: 1 });

const PAGE_MAP = {
  home: {
    title: "Home",
    description: "A cleaner, calmer entry point into the scanner workflow.",
    render: renderHomePage,
  },
  scan: {
    title: "Scan",
    description: "Capture the six faces with a clearer, more integrated scanner experience.",
    render: renderScanPage,
  },
  review: {
    title: "Review",
    description: "Confirm the current cube state, make small corrections, and validate before solving.",
    render: renderReviewPage,
  },
  solve: {
    title: "Solve",
    description: "Run the stable solve path first. CFOP Beta stays visible, but clearly secondary.",
    render: renderSolvePage,
  },
  viewer: {
    title: "3D Viewer",
    description: "Inspect the cube from any angle and play solutions directly in the browser.",
    render: renderViewerPage,
  },
  settings: {
    title: "Settings",
    description: "Choose how much detail the product shows by default.",
    render: renderSettingsPage,
  },
};

function normalizeRoute(route) {
  return PAGE_MAP[route] ? route : "home";
}

function createViewerState() {
  return {
    mode: "current",
    session: null,
    loading: false,
    error: null,
    frameIndex: 0,
    playing: false,
    animating: false,
    speed: 1,
    yaw: DEFAULT_VIEWER_CAMERA.yaw,
    pitch: DEFAULT_VIEWER_CAMERA.pitch,
    zoom: DEFAULT_VIEWER_CAMERA.zoom,
  };
}

const APP = {
  route: normalizeRoute(window.location.hash.replace("#", "") || "home"),
  state: null,
  loading: true,
  toast: null,
  toastTimer: null,
  pollHandle: null,
  lastStateSignature: null,
  lastPollAt: 0,
  pollDebugCount: 0,
  reviewEditor: {
    selected: null,
  },
  clientInfoReported: false,
  scanPreviewToken: 0,
  viewerState: createViewerState(),
  viewerPlaybackToken: 0,
};

function updateStateSnapshot(nextState) {
  APP.state = nextState;
  APP.lastStateSignature = JSON.stringify(nextState);

  const selection = APP.reviewEditor.selected;
  if (selection) {
    const face = nextState?.review?.faces?.[selection.slot];
    if (!face) {
      APP.reviewEditor.selected = null;
    } else {
      APP.reviewEditor.selected = {
        ...selection,
        color: face?.[selection.row]?.[selection.col] || selection.color,
      };
    }
  }
}

function setToast(message, tone = "neutral") {
  APP.toast = { message, tone };
  window.clearTimeout(APP.toastTimer);
  APP.toastTimer = window.setTimeout(() => {
    APP.toast = null;
    render();
  }, 3600);
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function maybeReportClientInfo() {
  if (APP.clientInfoReported) return;
  if (!window.navigator) return;

  APP.clientInfoReported = true;
  api.sendClientInfo({
    userAgent: window.navigator.userAgent || null,
    appVersion: window.navigator.appVersion || null,
    platform: window.navigator.platform || null,
  }).catch(() => {
    APP.clientInfoReported = false;
  });
}

function triggerDownload(url) {
  if (!url) return;
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.rel = "noopener";
  anchor.download = "";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

function readEvaluationFields() {
  const trialId = document.querySelector('[data-eval-field="trialId"]')?.value || "";
  const lightingCondition = document.querySelector('[data-eval-field="lightingCondition"]')?.value || "";
  return {
    trialId: String(trialId).trim(),
    lightingCondition: String(lightingCondition).trim(),
  };
}

function stopViewerPlayback({ rerender = false } = {}) {
  APP.viewerPlaybackToken += 1;
  APP.viewerState.playing = false;
  APP.viewerState.animating = false;
  if (rerender) render();
}

function viewerStepPauseMs() {
  return Math.max(45, Math.round(110 / Number(APP.viewerState.speed || 1)));
}

async function stepViewerFrame(delta, { animate = true, token = APP.viewerPlaybackToken } = {}) {
  const session = APP.viewerState.session;
  const moves = session?.moves || [];
  const currentIndex = APP.viewerState.frameIndex;
  const nextIndex = Math.max(0, Math.min(moves.length, currentIndex + delta));

  if (nextIndex === currentIndex) {
    return false;
  }

  const move = delta > 0 ? moves[currentIndex] : moves[currentIndex - 1];
  APP.viewerState.animating = true;

  if (animate && move) {
    await animateViewerTurn(move, {
      reverse: delta < 0,
      speed: APP.viewerState.speed,
    });
  }

  if (token !== APP.viewerPlaybackToken) {
    APP.viewerState.animating = false;
    return false;
  }

  APP.viewerState.frameIndex = nextIndex;
  APP.viewerState.animating = false;
  render();
  return true;
}

async function playViewerSequence({ endIndex = null } = {}) {
  const session = APP.viewerState.session;
  if (!session?.moves?.length) return;

  const playbackEnd = Math.max(0, Math.min(session.moves.length, endIndex ?? session.moves.length));

  if (APP.viewerState.frameIndex >= playbackEnd) {
    APP.viewerState.frameIndex = 0;
  }

  const token = APP.viewerPlaybackToken + 1;
  APP.viewerPlaybackToken = token;
  APP.viewerState.playing = true;
  render();

  while (
    token === APP.viewerPlaybackToken &&
    APP.viewerState.playing &&
    APP.route === "viewer" &&
    APP.viewerState.frameIndex < playbackEnd
  ) {
    const advanced = await stepViewerFrame(1, { animate: true, token });
    if (!advanced) break;
    await sleep(viewerStepPauseMs());
  }

  if (token !== APP.viewerPlaybackToken) return;
  APP.viewerState.playing = false;
  render();
}

async function runViewerPlaybackAction(action) {
  const session = APP.viewerState.session;
  const moves = session?.moves || [];
  const busy = Boolean(APP.viewerState.animating);

  switch (action) {
    case "prev":
      if (APP.viewerState.playing || busy) {
        stopViewerPlayback({ rerender: true });
        return true;
      }
      await stepViewerFrame(-1, { animate: true });
      return true;
    case "next":
      if (APP.viewerState.playing || busy) {
        stopViewerPlayback({ rerender: true });
        return true;
      }
      await stepViewerFrame(1, { animate: true });
      return true;
    case "toggle-play":
      if (!moves.length) return false;
      if (APP.viewerState.playing || busy) {
        stopViewerPlayback({ rerender: true });
        return true;
      }
      await playViewerSequence();
      return true;
    case "pause":
      if (APP.viewerState.playing || busy) {
        stopViewerPlayback({ rerender: true });
      }
      return true;
    case "reset-playback":
      stopViewerPlayback();
      APP.viewerState.frameIndex = 0;
      render();
      return true;
    case "finish-playback":
      stopViewerPlayback();
      APP.viewerState.frameIndex = moves.length;
      render();
      return true;
    case "reset-view":
      APP.viewerState.yaw = DEFAULT_VIEWER_CAMERA.yaw;
      APP.viewerState.pitch = DEFAULT_VIEWER_CAMERA.pitch;
      APP.viewerState.zoom = DEFAULT_VIEWER_CAMERA.zoom;
      render();
      return true;
    default:
      return false;
  }
}

async function loadViewerSession(mode, { preserveCamera = true, silent = false } = {}) {
  APP.viewerState.loading = true;
  APP.viewerState.error = null;
  APP.viewerState.mode = mode;
  stopViewerPlayback();
  if (!silent) render();

  try {
    const response = await api.getViewerSession(mode);
    APP.viewerState.session = response.session;
    APP.viewerState.mode = response.session.mode;
    APP.viewerState.frameIndex = 0;
    APP.viewerState.loading = false;
    APP.viewerState.error = null;
    if (!preserveCamera) {
      APP.viewerState.yaw = DEFAULT_VIEWER_CAMERA.yaw;
      APP.viewerState.pitch = DEFAULT_VIEWER_CAMERA.pitch;
      APP.viewerState.zoom = DEFAULT_VIEWER_CAMERA.zoom;
    }
    render();
  } catch (error) {
    APP.viewerState.loading = false;
    APP.viewerState.error = error.message || "Could not load viewer session.";
    render();
  }
}

async function refreshState({ silent = false } = {}) {
  const startedAt = performance.now();
  let patchedScanPage = false;
  let shouldRender = !silent || !APP.state;
  let stateChanged = false;
  try {
    if (!silent) APP.loading = true;
    const nextState = APP.route === "scan" ? await api.getScannerState() : await api.getState();
    const nextSignature = JSON.stringify(nextState);
    stateChanged = nextSignature !== APP.lastStateSignature;

    if (stateChanged || !APP.state) {
      updateStateSnapshot(nextState);
      const preserveActiveViewer = silent && APP.route === "viewer" && Boolean(APP.viewerState.session);
      if (!preserveActiveViewer) {
        shouldRender = true;
      }
    }
    maybeReportClientInfo();

    if (APP.route === "scan") {
      const intervalMs = APP.lastPollAt ? Math.round(performance.now() - APP.lastPollAt) : 0;
      APP.lastPollAt = performance.now();
      APP.pollDebugCount += 1;
      if (APP.pollDebugCount % 10 === 0) {
        console.debug("[scan-state] poll", {
          intervalMs,
          durationMs: Math.round(performance.now() - startedAt),
          processRunning: nextState?.scanner?.processRunning,
          previewAvailable: nextState?.scanner?.previewAvailable,
        });
      }
    }

    if (APP.route === "scan" && !APP.loading && patchScanPage(APP.state)) {
      hydrateScanPage(APP);
      patchedScanPage = true;
    }
  } catch (error) {
    if (APP.route === "scan") {
      console.warn("[scan-state] polling error", error);
    }
    shouldRender = true;
    setToast(error.message || "Could not refresh app state.", "danger");
  } finally {
    APP.loading = false;
    if (!patchedScanPage && shouldRender) {
      render();
    }
  }
}

async function runAction(action) {
  try {
    if (action.startsWith("route:")) {
      navigate(action.split(":", 2)[1]);
      return;
    }

    if (action.startsWith("command:")) {
      const command = action.split(":", 2)[1];
      const response = await api.runBrowserScannerAction(command);
      updateStateSnapshot(response.state);
      setToast(command === "capture" ? "Face captured." : "Scanner updated.", "success");
      return refreshState({ silent: true });
    }

    if (action.startsWith("viewer:")) {
      const mode = action.split(":", 2)[1] || "current";
      if (APP.route !== "viewer") {
        APP.route = "viewer";
        window.history.replaceState({}, "", "#viewer");
        render();
        restartPolling();
      }
      await loadViewerSession(mode, { preserveCamera: false, silent: true });
      return;
    }

    switch (action) {
      case "launch-scanner": {
        const result = await api.launchScanner();
        setToast(result.alreadyRunning ? "Scanner is already running." : "Scanner launched.", "success");
        break;
      }
      case "open-viewer": {
        const result = await api.openViewer();
        if (result.ok && result.browserMode) {
          navigate("viewer");
          await loadViewerSession(result.browserMode, { preserveCamera: false, silent: true });
        }
        setToast(result.ok ? "Opened 3D viewer." : result.error, result.ok ? "success" : "warning");
        break;
      }
      case "solve-standard": {
        const result = await api.solveStandard();
        setToast(
          result.result?.status === "success" ? "Standard solve ready." : result.result?.error || "Standard solve could not run.",
          result.result?.status === "success" ? "success" : "warning",
        );
        break;
      }
      case "solve-cfop": {
        const result = await api.solveCfop();
        setToast(
          result.result?.status === "success" ? "CFOP Beta finished." : result.result?.error || "CFOP Beta could not solve this cube yet.",
          result.result?.status === "success" ? "success" : "warning",
        );
        break;
      }
      case "playback-standard": {
        const result = await api.playbackStandard();
        if (result.ok && result.browserMode) {
          navigate("viewer");
          await loadViewerSession(result.browserMode, { preserveCamera: false, silent: true });
        }
        setToast(result.ok ? "Opened standard playback." : result.error || "Could not open standard playback.", result.ok ? "success" : "warning");
        break;
      }
      case "playback-cfop": {
        const result = await api.playbackCfop();
        if (result.ok && result.browserMode) {
          navigate("viewer");
          await loadViewerSession(result.browserMode, { preserveCamera: false, silent: true });
        }
        setToast(result.ok ? "Opened CFOP Beta playback." : result.error || "CFOP Beta playback is not available for this cube.", result.ok ? "success" : "warning");
        break;
      }
      case "reset-state":
        await api.resetState();
        APP.reviewEditor.selected = null;
        APP.viewerState = createViewerState();
        setToast("App state reset.", "success");
        break;
      default:
        setToast(`Unknown action: ${action}`, "warning");
        return;
    }
  } catch (error) {
    setToast(error.message || "Action failed.", "danger");
  } finally {
    refreshState({ silent: true });
  }
}

async function saveSetting(key, value) {
  try {
    const nextSettings = {
      ...(APP.state?.settings || {}),
      [key]: value,
    };
    await api.saveSettings(nextSettings);
    setToast("Settings updated.", "success");
    refreshState({ silent: true });
  } catch (error) {
    setToast(error.message || "Could not save settings.", "danger");
  }
}

function navigate(route) {
  const next = normalizeRoute(route);
  if (APP.route !== "viewer" && next === "viewer") {
    APP.viewerState.error = null;
  }
  if (APP.route === "scan" && next !== "scan") {
    APP.scanPreviewToken += 1;
    stopBrowserCamera();
  }
  if (APP.route === "viewer" && next !== "viewer") {
    stopViewerPlayback();
  }
  APP.route = next;
  window.history.replaceState({}, "", `#${next}`);
  render();
  restartPolling();
  refreshState({ silent: true });
  if (next === "viewer" && !APP.viewerState.session && !APP.viewerState.loading) {
    loadViewerSession(APP.viewerState.mode || "current", { silent: true });
  }
}

function restartPolling() {
  window.clearInterval(APP.pollHandle);
  const interval = APP.route === "scan"
    ? Math.max(500, APP.state?.scanner?.statePollMs || 700)
    : APP.route === "viewer"
      ? 3500
      : 2200;
  APP.pollHandle = window.setInterval(() => refreshState({ silent: true }), interval);
}

function render() {
  const page = PAGE_MAP[APP.route] || PAGE_MAP.home;
  const pageHtml = page.render(APP.state || {}, APP);

  root.innerHTML = renderAppShell({
    route: APP.route,
    state: APP.state,
    pageTitle: page.title,
    pageDescription: page.description,
    pageHtml,
    toast: APP.toast,
    isLoading: APP.loading,
  });

  document.body.dataset.theme = APP.state?.settings?.theme || "dark";

  if (APP.route === "scan") {
    hydrateScanPage(APP);
  }
  if (APP.route === "viewer") {
    hydrateViewerPage(APP);
  }
}

root.addEventListener("click", async (event) => {
  const cameraAction = event.target.closest("[data-camera-action]");
  if (cameraAction && !cameraAction.disabled) {
    try {
      if (cameraAction.dataset.cameraAction === "start") {
        await startBrowserCamera();
        setToast("Browser camera started.", "success");
      } else {
        stopBrowserCamera();
        setToast("Camera stopped.", "neutral");
      }
    } catch (error) {
      setToast(error.message || "Could not start the camera.", "danger");
    }
    return;
  }

  const routeTrigger = event.target.closest("[data-route]");
  if (routeTrigger) {
    navigate(routeTrigger.dataset.route);
    return;
  }

  const stickerTrigger = event.target.closest("[data-sticker-slot]");
  if (stickerTrigger) {
    APP.reviewEditor.selected = {
      slot: stickerTrigger.dataset.stickerSlot,
      row: Number(stickerTrigger.dataset.stickerRow),
      col: Number(stickerTrigger.dataset.stickerCol),
      color: stickerTrigger.dataset.stickerColor || "UNKNOWN",
    };
    render();
    return;
  }

  const colorChoice = event.target.closest("[data-color-choice]");
  if (colorChoice && APP.reviewEditor.selected) {
    try {
      const payload = await api.editSticker(
        APP.reviewEditor.selected.slot,
        APP.reviewEditor.selected.row,
        APP.reviewEditor.selected.col,
        colorChoice.dataset.colorChoice,
      );
      updateStateSnapshot(payload.state);
      APP.reviewEditor.selected = {
        ...APP.reviewEditor.selected,
        color: colorChoice.dataset.colorChoice,
      };
      setToast("Sticker updated.", "success");
      render();
    } catch (error) {
      setToast(error.message || "Could not update sticker.", "danger");
      render();
    }
    return;
  }

  const editAction = event.target.closest("[data-edit-action]");
  if (editAction) {
    try {
      if (editAction.dataset.editAction === "undo") {
        const payload = await api.undoStickerEdit();
        updateStateSnapshot(payload.state);
        setToast("Last sticker edit undone.", "success");
      } else if (editAction.dataset.editAction === "reset") {
        const payload = await api.resetStickerEdits();
        updateStateSnapshot(payload.state);
        APP.reviewEditor.selected = null;
        setToast("Manual edits reset.", "success");
      } else if (editAction.dataset.editAction === "close-picker") {
        APP.reviewEditor.selected = null;
      }
      render();
    } catch (error) {
      setToast(error.message || "Could not update manual edits.", "danger");
      render();
    }
    return;
  }

  const viewerModeTrigger = event.target.closest("[data-viewer-mode]");
  if (viewerModeTrigger && !viewerModeTrigger.disabled) {
    loadViewerSession(viewerModeTrigger.dataset.viewerMode, { preserveCamera: true });
    return;
  }

  const calibrationCapture = event.target.closest("[data-calibration-capture]");
  if (calibrationCapture && !calibrationCapture.disabled) {
    try {
      const payload = await api.captureCalibration(calibrationCapture.dataset.calibrationCapture);
      updateStateSnapshot(payload.state);
      setToast(`Captured calibration for ${calibrationCapture.dataset.calibrationCapture}.`, "success");
      render();
    } catch (error) {
      setToast(error.message || "Could not capture calibration.", "danger");
      render();
    }
    return;
  }

  const calibrationClear = event.target.closest("[data-calibration-clear]");
  if (calibrationClear && !calibrationClear.disabled) {
    try {
      const payload = await api.clearCalibration(calibrationClear.dataset.calibrationClear);
      updateStateSnapshot(payload.state);
      setToast(`Cleared calibration for ${calibrationClear.dataset.calibrationClear}.`, "success");
      render();
    } catch (error) {
      setToast(error.message || "Could not clear calibration.", "danger");
      render();
    }
    return;
  }

  const calibrationClearAll = event.target.closest("[data-calibration-clear-all]");
  if (calibrationClearAll && !calibrationClearAll.disabled) {
    try {
      const payload = await api.clearAllCalibration();
      updateStateSnapshot(payload.state);
      setToast("Cleared all calibration data.", "success");
      render();
    } catch (error) {
      setToast(error.message || "Could not clear calibration.", "danger");
      render();
    }
    return;
  }

  const evaluationAction = event.target.closest("[data-evaluation-action]");
  if (evaluationAction && !evaluationAction.disabled) {
    try {
      switch (evaluationAction.dataset.evaluationAction) {
        case "save-trial": {
          const fields = readEvaluationFields();
          const payload = await api.updateEvaluationTrial(fields);
          updateStateSnapshot(payload.state);
          setToast("Evaluation trial details saved.", "success");
          render();
          break;
        }
        case "new-trial": {
          const fields = readEvaluationFields();
          const payload = await api.updateEvaluationTrial({
            ...fields,
            startNew: true,
          });
          updateStateSnapshot(payload.state);
          setToast("Started a new evaluation trial.", "success");
          render();
          break;
        }
        case "export-json":
        case "export-csv":
        case "export-system":
          triggerDownload(evaluationAction.dataset.downloadUrl);
          setToast("Download started.", "success");
          break;
        default:
          break;
      }
    } catch (error) {
      setToast(error.message || "Could not update evaluation settings.", "danger");
      render();
    }
    return;
  }

  const viewerAction = event.target.closest("[data-viewer-action]");
  if (viewerAction && !viewerAction.disabled) {
    await runViewerPlaybackAction(viewerAction.dataset.viewerAction);
    return;
  }

  const viewerStagePlay = event.target.closest("[data-viewer-stage-play]");
  if (viewerStagePlay && !viewerStagePlay.disabled) {
    const [startValue, endValue] = (viewerStagePlay.dataset.viewerStagePlay || "").split(":");
    const startIndex = Number(startValue);
    const endIndex = Number(endValue);
    if (Number.isInteger(startIndex) && Number.isInteger(endIndex)) {
      stopViewerPlayback();
      APP.viewerState.frameIndex = startIndex;
      render();
      await playViewerSequence({ endIndex });
    }
    return;
  }

  const viewerStageJump = event.target.closest("[data-viewer-stage-start]");
  if (viewerStageJump && !viewerStageJump.disabled) {
    const startIndex = Number(viewerStageJump.dataset.viewerStageStart);
    if (Number.isInteger(startIndex)) {
      stopViewerPlayback();
      APP.viewerState.frameIndex = startIndex;
      render();
    }
    return;
  }

  const copyTrigger = event.target.closest("[data-copy-text]");
  if (copyTrigger) {
    try {
      await navigator.clipboard.writeText(copyTrigger.dataset.copyText || "");
      setToast("Move list copied.", "success");
      render();
    } catch (_error) {
      setToast("Could not copy to clipboard.", "warning");
      render();
    }
    return;
  }

  const actionTrigger = event.target.closest("[data-action]");
  if (actionTrigger && !actionTrigger.disabled) {
    runAction(actionTrigger.dataset.action);
  }
});

root.addEventListener("change", (event) => {
  const setting = event.target.closest("[data-setting-key]");
  if (setting) {
    const key = setting.dataset.settingKey;
    const value = setting.type === "checkbox" ? setting.checked : setting.value;
    saveSetting(key, value);
    return;
  }

  const viewerSpeed = event.target.closest("[data-viewer-speed]");
  if (viewerSpeed) {
    APP.viewerState.speed = Number(viewerSpeed.value) || 1;
    render();
  }
});

window.addEventListener("keydown", async (event) => {
  if (APP.route !== "viewer") return;

  const action = getViewerKeyboardAction(event);
  if (!action) return;

  event.preventDefault();
  if (event.repeat) return;

  await runViewerPlaybackAction(action);
});

window.addEventListener("hashchange", () => {
  const nextRoute = normalizeRoute(window.location.hash.replace("#", "") || "home");
  if (APP.route === "scan" && nextRoute !== "scan") {
    APP.scanPreviewToken += 1;
    stopBrowserCamera();
  }
  if (APP.route === "viewer" && nextRoute !== "viewer") {
    stopViewerPlayback();
  }
  APP.route = nextRoute;
  render();
  restartPolling();
  if (APP.route === "viewer" && !APP.viewerState.session && !APP.viewerState.loading) {
    loadViewerSession(APP.viewerState.mode || "current", { silent: true });
  }
});

refreshState().then(() => {
  if (APP.route === "viewer" && !APP.viewerState.session && !APP.viewerState.loading) {
    loadViewerSession(APP.viewerState.mode || "current", { silent: true });
  }
});
restartPolling();
