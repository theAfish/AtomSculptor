/**
 * utils.js – Pure utility / formatting helpers (no DOM side-effects).
 */

export const $ = (s) => document.querySelector(s);
export const $$ = (s) => document.querySelectorAll(s);

export function esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

export function truncate(s, n) {
  return s.length > n ? `${s.slice(0, n)}...` : s;
}

export function fmtSize(b) {
  if (b < 1024) return `${b}B`;
  if (b < 1048576) return `${(b / 1024).toFixed(1)}K`;
  return `${(b / 1048576).toFixed(1)}M`;
}

export function renderMd(text) {
  try {
    return marked.parse(text, { breaks: true });
  } catch (_err) {
    return `<p>${esc(text).replace(/\n/g, "<br>")}</p>`;
  }
}

export function jsonPretty(obj) {
  try {
    return JSON.stringify(obj, null, 2);
  } catch (_err) {
    return String(obj);
  }
}

/* ── Shared panel utilities ──────────────────────────────────────────────── */

export function showError(selector, message) {
  const el = $(selector);
  el.textContent = message;
  el.classList.add("show");
}

export function clearError(selector) {
  const el = $(selector);
  el.classList.remove("show");
  el.textContent = "";
}

/* ── 3×3 matrix I/O utilities ────────────────────────────────────────────── */

export function setMatrixInputs(prefix, matrix) {
  for (let i = 0; i < 3; i += 1) {
    for (let j = 0; j < 3; j += 1) {
        $(`#${prefix}${i}${j}`).value = parseFloat(Number(matrix[i][j]).toFixed(6)).toString();
    }
  }
}

export function readMatrixInputs(prefix) {
  const m = [];
  for (let i = 0; i < 3; i += 1) {
    m[i] = [];
    for (let j = 0; j < 3; j += 1) {
      const v = parseFloat($(`#${prefix}${i}${j}`).value);
      if (Number.isNaN(v)) throw new Error("Matrix contains invalid numbers.");
      m[i][j] = v;
    }
  }
  return m;
}

export function multiplyMatrices(a, b) {
  const out = [];
  for (let i = 0; i < 3; i += 1) {
    out[i] = [];
    for (let j = 0; j < 3; j += 1) {
      out[i][j] = 0;
      for (let k = 0; k < 3; k += 1) {
        out[i][j] += a[i][k] * b[k][j];
      }
    }
  }
  return out;
}
