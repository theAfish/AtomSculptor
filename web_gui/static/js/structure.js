/**
 * structure.js – Structure data operations: load, save, undo/redo,
 *                format detection, and structure building API calls.
 */

import {
  S,
  STRUCTURE_EXTS,
  STRUCTURE_PREFIXES,
  MODE_HINT,
  MAX_UNDO_ENTRIES,
} from "./state.js";
import { $ } from "./utils.js";
import { rebuildScene, resetCamera } from "./viewer.js";

function cloneAtoms(atoms) {
  return atoms.map((atom) => ({ ...atom }));
}

function cloneCell(cell) {
  return Array.isArray(cell) ? cell.map((vec) => [...vec]) : null;
}

function clonePbc(pbc) {
  return Array.isArray(pbc) ? [...pbc] : [false, false, false];
}

function atomListsEqual(left, right) {
  if (left.length !== right.length) return false;
  for (let i = 0; i < left.length; i += 1) {
    const a = left[i];
    const b = right[i];
    if (
      a.id !== b.id
      || a.symbol !== b.symbol
      || a.x !== b.x
      || a.y !== b.y
      || a.z !== b.z
    ) {
      return false;
    }
  }
  return true;
}

function matrixListsEqual(left, right) {
  if (left === right) return true;
  if (!Array.isArray(left) || !Array.isArray(right)) return false;
  if (left.length !== right.length) return false;
  for (let i = 0; i < left.length; i += 1) {
    const lv = left[i];
    const rv = right[i];
    if (!Array.isArray(lv) || !Array.isArray(rv) || lv.length !== rv.length) return false;
    for (let j = 0; j < lv.length; j += 1) {
      if (lv[j] !== rv[j]) return false;
    }
  }
  return true;
}

function arraysEqual(left, right) {
  if (left === right) return true;
  if (!Array.isArray(left) || !Array.isArray(right)) return false;
  if (left.length !== right.length) return false;
  for (let i = 0; i < left.length; i += 1) {
    if (left[i] !== right[i]) return false;
  }
  return true;
}

function structureStatesEqual(left, right) {
  return (
    atomListsEqual(left.atoms, right.atoms)
    && matrixListsEqual(left.cell, right.cell)
    && arraysEqual(left.pbc, right.pbc)
    && arraysEqual(left.selected, right.selected)
  );
}

function normalizeSelection(selected) {
  const atomIds = new Set(S.atoms.map((atom) => atom.id));
  return new Set(selected.filter((id) => atomIds.has(id)));
}

function applyStructureState(state) {
  S.atoms = cloneAtoms(state.atoms);
  S.cell = cloneCell(state.cell);
  S.pbc = clonePbc(state.pbc);
  S.selected = normalizeSelection(state.selected);
  S.hovered = null;
  rebuildScene();
  updateStatusBar();
}

function pushUndoState(state) {
  S.undoStack.push(state);
  if (S.undoStack.length > MAX_UNDO_ENTRIES) S.undoStack.shift();
}

export function snapshotStructureState() {
  return {
    atoms: cloneAtoms(S.atoms),
    cell: cloneCell(S.cell),
    pbc: clonePbc(S.pbc),
    selected: [...S.selected].sort((left, right) => left - right),
  };
}

export function resetStructureHistory() {
  S.undoStack = [];
  S.redoStack = [];
}

export function recordStructureEdit(beforeState) {
  if (!beforeState) return false;
  const afterState = snapshotStructureState();
  if (structureStatesEqual(beforeState, afterState)) return false;
  pushUndoState(beforeState);
  S.redoStack = [];
  return true;
}

export function undoStructureEdit() {
  const previous = S.undoStack.pop();
  if (!previous) return false;
  S.redoStack.push(snapshotStructureState());
  applyStructureState(previous);
  return true;
}

export function redoStructureEdit() {
  const next = S.redoStack.pop();
  if (!next) return false;
  pushUndoState(snapshotStructureState());
  applyStructureState(next);
  return true;
}

function deleteAtomsByIds(ids, beforeState = null) {
  const toDelete = new Set(ids);
  if (!toDelete.size) return false;

  const existingIds = new Set(S.atoms.map((atom) => atom.id));
  const deletableIds = [...toDelete].filter((id) => existingIds.has(id));
  if (!deletableIds.length) return false;

  const snapshot = beforeState || snapshotStructureState();
  const deletedIdSet = new Set(deletableIds);
  S.atoms = S.atoms.filter((atom) => !deletedIdSet.has(atom.id));
  S.selected = new Set([...S.selected].filter((id) => !deletedIdSet.has(id)));
  if (S.hovered !== null && deletedIdSet.has(S.hovered)) S.hovered = null;
  rebuildScene();
  updateStatusBar();
  recordStructureEdit(snapshot);
  return true;
}

export function isStructureFilename(name) {
  const base = String(name).split("/").pop().toLowerCase();
  const ext = base.includes(".") ? base.split(".").pop() : "";
  if (STRUCTURE_EXTS.has(ext)) return true;
  return STRUCTURE_PREFIXES.some((prefix) => (
    base === prefix
    || base.startsWith(`${prefix}_`)
    || base.startsWith(`${prefix}-`)
    || base.startsWith(`${prefix}.`)
  ));
}

/**
 * Check if a tool result references a structure file and auto-load it.
 * Called from websocket.js after rendering tool results.
 */
export function tryAutoLoadFromResult(result) {
  if (!result || typeof result !== "object") return;
  for (const key of Object.keys(result)) {
    const val = result[key];
    if (typeof val !== "string") continue;
    if (isStructureFilename(val)) {
      loadStructure(val);
      return;
    }
  }
}

export function updateStatusBar() {
  $("#sb-mode").textContent = `Mode: ${S.mode.charAt(0).toUpperCase()}${S.mode.slice(1)}`;
  $("#sb-natoms").textContent = `${S.atoms.length} atoms`;
  $("#sb-sel").textContent = S.selected.size ? `${S.selected.size} selected` : "";
  $("#sb-hint").textContent = MODE_HINT[S.mode] || "";
}

export async function loadStructure(path) {
  try {
    const resp = await fetch(`/api/structure?path=${encodeURIComponent(path)}`);
    const data = await resp.json();
    if (data.error) {
      console.error(data.error);
      return;
    }

    S.structPath = path;
    S.atoms = data.atoms;
    S.cell = data.cell;
    S.pbc = data.pbc;
    S.selected = new Set();
    S.hovered = null;
    resetStructureHistory();
    rebuildScene();
    $("#struct-file-label").textContent = data.path;
    $("#viewer-empty").style.display = "none";
    resetCamera();
    updateStatusBar();
  } catch (e) {
    console.error("loadStructure", e);
  }
}

export async function saveStructure() {
  if (!S.structPath) {
    alert("No structure loaded.");
    return;
  }

  try {
    const resp = await fetch("/api/structure/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: S.structPath, atoms: S.atoms, cell: S.cell, pbc: S.pbc }),
    });
    const data = await resp.json();

    if (data.ok) {
      const sb = $("#struct-statusbar");
      const orig = sb.style.borderTop;
      sb.style.borderTop = "1px solid var(--s-done)";
      setTimeout(() => {
        sb.style.borderTop = orig;
      }, 1500);
    } else {
      alert(`Save failed: ${data.error || "unknown"}`);
    }
  } catch (e) {
    alert(`Save error: ${e}`);
  }
}

export function deleteAtomById(id) {
  deleteAtomsByIds([id]);
}

export function deleteSelected() {
  deleteAtomsByIds([...S.selected]);
}

export function addAtom(atom, beforeState = null) {
  const snapshot = beforeState || snapshotStructureState();
  S.atoms.push({ ...atom });
  rebuildScene();
  updateStatusBar();
  recordStructureEdit(snapshot);
}

export function applyLattice(realMatrix, scaleAtoms) {
  const beforeState = snapshotStructureState();
  const currentCell = Array.isArray(S.cell) && S.cell.length === 3 ? S.cell : [[1,0,0],[0,1,0],[0,0,1]];

  const invertMatrix3 = (m) => {
    const a = m[0][0]; const b = m[0][1]; const c = m[0][2];
    const d = m[1][0]; const e = m[1][1]; const f = m[1][2];
    const g = m[2][0]; const h = m[2][1]; const i = m[2][2];
    const det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);
    if (Math.abs(det) < 1e-12) throw new Error("Cell matrix is singular and cannot be inverted.");
    const invDet = 1 / det;
    return [
      [(e * i - f * h) * invDet, (c * h - b * i) * invDet, (b * f - c * e) * invDet],
      [(f * g - d * i) * invDet, (a * i - c * g) * invDet, (c * d - a * f) * invDet],
      [(d * h - e * g) * invDet, (b * g - a * h) * invDet, (a * e - b * d) * invDet],
    ];
  };

  const multVec = (m, v) => [
    m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
    m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
    m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
  ];

  if (scaleAtoms) {
    const invOld = invertMatrix3(currentCell);
    for (const atom of S.atoms) {
      const frac = multVec(invOld, [atom.x, atom.y, atom.z]);
      const newPos = multVec(realMatrix, frac);
      atom.x = newPos[0];
      atom.y = newPos[1];
      atom.z = newPos[2];
    }
  }

  S.cell = realMatrix;
  rebuildScene();
  updateStatusBar();
  recordStructureEdit(beforeState);
}

// ── Structure building tools ────────────────────────────────────────────────

function applyBuiltStructure(data) {
  S.structPath = data.path;
  S.atoms = data.atoms;
  S.cell = data.cell;
  S.pbc = data.pbc;
  S.selected = new Set();
  S.hovered = null;
  resetStructureHistory();
  rebuildScene();
  $("#struct-file-label").textContent = data.path;
  $("#viewer-empty").style.display = "none";
  resetCamera();
  updateStatusBar();
}

async function parseJsonResponseSafe(resp) {
  const text = await resp.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (data && typeof data === "object") {
    return data;
  }

  if (!resp.ok) {
    return { error: `HTTP ${resp.status}: ${text || resp.statusText}` };
  }

  return { error: "Server returned an unexpected response." };
}

export async function buildSurface(millerIndices, layers, vacuum) {
  if (!S.structPath) return { error: "No structure loaded." };

  const resp = await fetch("/api/structure/build-surface", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      path: S.structPath,
      miller_indices: millerIndices,
      layers,
      vacuum,
    }),
  });
  const data = await parseJsonResponseSafe(resp);
  if (data.error) return data;
  applyBuiltStructure(data);
  return data;
}

export async function buildSupercell(matrix) {
  if (!S.structPath) return { error: "No structure loaded." };

  const resp = await fetch("/api/structure/build-supercell", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      path: S.structPath,
      matrix,
    }),
  });
  const data = await parseJsonResponseSafe(resp);
  if (data.error) return data;
  applyBuiltStructure(data);
  return data;
}
