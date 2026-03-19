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
