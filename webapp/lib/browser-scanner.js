import { api } from "./api.js";

export const BROWSER_SCANNER_SAMPLE_FPS = 10;
export const GUIDE_FRACTION = 0.56;
export const MAX_SAMPLING_WIDTH = 720;

export function medianRgb(values) {
  if (!values?.length) return [0, 0, 0];
  const channels = [[], [], []];
  for (let index = 0; index < values.length; index += 4) {
    channels[0].push(values[index]);
    channels[1].push(values[index + 1]);
    channels[2].push(values[index + 2]);
  }
  return channels.map((channel) => {
    channel.sort((left, right) => left - right);
    const middle = Math.floor(channel.length / 2);
    return channel.length % 2
      ? channel[middle]
      : Math.round((channel[middle - 1] + channel[middle]) / 2);
  });
}

export function rgbToBgr(rgb) {
  return [rgb[2], rgb[1], rgb[0]];
}

export function computeCoverSourceRect(sourceWidth, sourceHeight, targetWidth, targetHeight) {
  if (![sourceWidth, sourceHeight, targetWidth, targetHeight].every((value) => Number.isFinite(value) && value > 0)) {
    throw new Error("Camera and preview dimensions must be positive numbers.");
  }
  const sourceRatio = sourceWidth / sourceHeight;
  const targetRatio = targetWidth / targetHeight;
  if (sourceRatio > targetRatio) {
    const width = sourceHeight * targetRatio;
    return { x: (sourceWidth - width) / 2, y: 0, width, height: sourceHeight };
  }
  const height = sourceWidth / targetRatio;
  return { x: 0, y: (sourceHeight - height) / 2, width: sourceWidth, height };
}

export function buildGridSamplingGeometry(width, height, guideFraction = GUIDE_FRACTION) {
  const size = Math.min(width, height) * guideFraction;
  const left = (width - size) / 2;
  const top = (height - size) / 2;
  const cellSize = size / 3;
  return {
    left,
    top,
    size,
    cellSize,
    centers: Array.from({ length: 3 }, (_, row) =>
      Array.from({ length: 3 }, (_, col) => ({
        x: left + (col + 0.5) * cellSize,
        y: top + (row + 0.5) * cellSize,
      })),
    ),
  };
}

function samplePatch(context, centerX, centerY, size) {
  const canvas = context.canvas;
  const left = Math.max(0, Math.round(centerX - size / 2));
  const top = Math.max(0, Math.round(centerY - size / 2));
  const width = Math.max(1, Math.min(canvas.width - left, Math.round(size)));
  const height = Math.max(1, Math.min(canvas.height - top, Math.round(size)));
  return medianRgb(context.getImageData(left, top, width, height).data);
}

function sampleCenterMulti(context, center, cellSize) {
  const offset = cellSize * 0.3;
  const patchSize = Math.max(3, cellSize * 0.09);
  const diagonal = offset * 0.7;
  const offsets = [
    [-offset, 0], [offset, 0], [0, -offset], [0, offset],
    [-diagonal, -diagonal], [diagonal, -diagonal],
    [-diagonal, diagonal], [diagonal, diagonal],
  ];
  const pixels = [];
  for (const [dx, dy] of offsets) {
    const rgb = samplePatch(context, center.x + dx, center.y + dy, patchSize);
    pixels.push(...rgb, 255);
  }
  return medianRgb(Uint8ClampedArray.from(pixels));
}

export function sampleVideoToBgr(video, canvas) {
  if (!video.videoWidth || !video.videoHeight) throw new Error("Camera video is not ready yet.");
  const displayWidth = Math.max(320, Math.round(video.clientWidth || 640));
  const displayHeight = Math.max(240, Math.round(video.clientHeight || 480));
  const scale = Math.min(globalThis.devicePixelRatio || 1, 2, MAX_SAMPLING_WIDTH / displayWidth);
  canvas.width = Math.round(displayWidth * scale);
  canvas.height = Math.round(displayHeight * scale);
  const context = canvas.getContext("2d", { willReadFrequently: true });
  const crop = computeCoverSourceRect(video.videoWidth, video.videoHeight, canvas.width, canvas.height);
  context.drawImage(
    video,
    crop.x,
    crop.y,
    crop.width,
    crop.height,
    0,
    0,
    canvas.width,
    canvas.height,
  );
  const geometry = buildGridSamplingGeometry(canvas.width, canvas.height);
  const patchSize = geometry.cellSize * 0.22;
  const samples = geometry.centers.map((row) => row.map((center) => rgbToBgr(samplePatch(context, center.x, center.y, patchSize))));
  const centerRgb = sampleCenterMulti(context, geometry.centers[1][1], geometry.cellSize);
  const centerBgr = rgbToBgr(centerRgb);
  samples[1][1] = centerBgr;
  return {
    samples,
    centerBgr,
    cameraResolution: { width: video.videoWidth, height: video.videoHeight },
  };
}

function cameraErrorMessage(error) {
  if (!globalThis.isSecureContext && globalThis.location?.hostname !== "localhost" && globalThis.location?.hostname !== "127.0.0.1") {
    return "Camera access requires HTTPS.";
  }
  switch (error?.name) {
    case "NotAllowedError": return "Camera permission was denied. Allow camera access in your browser and try again.";
    case "NotFoundError": return "No camera was found on this device.";
    case "NotReadableError": return "The camera is already in use or could not be opened.";
    case "OverconstrainedError": return "The requested camera mode is not available.";
    default: return error?.message || "The camera could not be started.";
  }
}

class BrowserScannerController {
  constructor() {
    this.stream = null;
    this.video = null;
    this.canvas = null;
    this.timer = null;
    this.inFlight = false;
    this.onState = null;
    this.onStatus = null;
    this.sampleCount = 0;
    this.metricsStartedAt = 0;
  }

  attach({ video, canvas, onState, onStatus }) {
    this.video = video;
    this.canvas = canvas;
    this.onState = onState;
    this.onStatus = onStatus;
    if (this.stream && this.video) {
      this.video.srcObject = this.stream;
      this.video.play().catch(() => {});
      this.onStatus?.({ state: "ready", message: "Camera ready" });
    }
  }

  get running() {
    return Boolean(this.stream?.getTracks().some((track) => track.readyState === "live"));
  }

  async start() {
    if (this.running) return;
    if (!globalThis.navigator?.mediaDevices?.getUserMedia) {
      const message = "This browser does not support camera access.";
      this.onStatus?.({ state: "error", message });
      throw new Error(message);
    }
    if (!globalThis.isSecureContext && !["localhost", "127.0.0.1"].includes(globalThis.location?.hostname)) {
      const message = "Camera access requires HTTPS.";
      this.onStatus?.({ state: "error", message });
      throw new Error(message);
    }
    this.onStatus?.({ state: "requesting", message: "Requesting camera access..." });
    try {
      this.stream = await globalThis.navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
      });
      if (!this.video) throw new Error("Camera preview is not mounted.");
      this.video.srcObject = this.stream;
      await this.video.play();
      await api.setBrowserCameraRunning(true);
      this.onStatus?.({ state: "ready", message: "Camera ready" });
      this.sampleCount = 0;
      this.metricsStartedAt = performance.now();
      this.timer = globalThis.setInterval(() => this.sample(), 1000 / BROWSER_SCANNER_SAMPLE_FPS);
    } catch (error) {
      this.stop({ notifyServer: false });
      const message = cameraErrorMessage(error);
      this.onStatus?.({ state: "error", message });
      throw new Error(message);
    }
  }

  async sample() {
    if (!this.running || this.inFlight || !this.video || !this.canvas || this.video.readyState < 2) return;
    this.inFlight = true;
    try {
      const guide = this.video.closest("[data-browser-camera]")?.querySelector(".browser-camera__guide");
      if (guide) {
        const guideSize = Math.min(this.video.clientWidth, this.video.clientHeight) * GUIDE_FRACTION;
        guide.style.width = `${guideSize}px`;
        guide.style.height = `${guideSize}px`;
      }
      const response = await api.submitBrowserSamples(sampleVideoToBgr(this.video, this.canvas));
      this.sampleCount += 1;
      this.onState?.(response.state);
      this.onStatus?.({ state: "scanning", message: response.state?.scanner?.captureReady ? "Ready to capture" : "Scanning" });
      const elapsed = performance.now() - this.metricsStartedAt;
      if (elapsed >= 5000) {
        const fpsApprox = this.sampleCount / Math.max(elapsed / 1000, 0.001);
        api.reportPreviewMetrics({ fpsApprox, targetFps: BROWSER_SCANNER_SAMPLE_FPS, source: "browser-camera" }).catch(() => {});
        this.sampleCount = 0;
        this.metricsStartedAt = performance.now();
      }
    } catch (error) {
      this.onStatus?.({ state: "error", message: error.message || "Recognition update failed." });
    } finally {
      this.inFlight = false;
    }
  }

  stop({ notifyServer = true } = {}) {
    const wasRunning = this.running;
    if (this.timer) globalThis.clearInterval(this.timer);
    this.timer = null;
    this.inFlight = false;
    for (const track of this.stream?.getTracks?.() || []) track.stop();
    this.stream = null;
    if (this.video) this.video.srcObject = null;
    this.onStatus?.({ state: "stopped", message: "Camera stopped" });
    if (notifyServer && wasRunning) api.setBrowserCameraRunning(false).catch(() => {});
  }
}

export const browserScanner = new BrowserScannerController();
