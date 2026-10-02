const EDITABLE_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

export const VIEWER_KEYBOARD_SHORTCUTS = Object.freeze([
  { key: "← / →", label: "Previous / next move" },
  { key: "Space / K", label: "Play / pause playback" },
  { key: "Home / End", label: "Jump to start / solved state" },
  { key: "R", label: "Reset 3D camera view" },
  { key: "Esc", label: "Pause playback" },
]);

export function shouldIgnoreViewerKeyboardEvent(event) {
  if (!event || event.defaultPrevented) return true;
  if (event.metaKey || event.ctrlKey || event.altKey) return true;

  const target = event.target;
  if (!target) return false;
  if (target.isContentEditable) return true;
  if (EDITABLE_TAGS.has(String(target.tagName || "").toUpperCase())) return true;
  return Boolean(target.closest?.("[data-ignore-viewer-shortcuts]"));
}

export function getViewerKeyboardAction(event) {
  if (shouldIgnoreViewerKeyboardEvent(event)) return null;

  switch (event.key) {
    case "ArrowRight":
    case "PageDown":
    case "n":
    case "N":
      return "next";
    case "ArrowLeft":
    case "PageUp":
    case "p":
    case "P":
      return "prev";
    case " ":
    case "Space":
    case "Spacebar":
    case "k":
    case "K":
      return "toggle-play";
    case "Home":
      return "reset-playback";
    case "End":
      return "finish-playback";
    case "r":
    case "R":
      return "reset-view";
    case "Escape":
      return "pause";
    default:
      return null;
  }
}
