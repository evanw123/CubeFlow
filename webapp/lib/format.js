export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function formatTimestamp(value) {
  if (!value) return "No recent activity";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function joinMoves(moves) {
  if (!Array.isArray(moves) || moves.length === 0) return "No moves";
  return moves.join(" ");
}

export function toneForValidation(review) {
  if (!review?.capturedFaceCount) return "neutral";
  if (!review.complete) return "warning";
  if (review.deepValidation?.ok) return "success";
  if (review.basicValidation?.ok) return "warning";
  return "danger";
}

export function validationLabel(review) {
  if (!review?.capturedFaceCount) return "No scan yet";
  if (!review.complete) return `${review.capturedFaceCount} of 6 faces captured`;
  if (review.deepValidation?.ok) return "Solver ready";
  if (review.basicValidation?.ok) return "Needs review";
  return "Invalid cube";
}

export function commandLabel(slot) {
  return {
    F: "Front",
    R: "Right",
    B: "Back",
    L: "Left",
    U: "Up",
    D: "Down",
  }[slot] || slot || "Face";
}
