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
import { rebuildScene, resetCamera, updateAtomVisuals } from "./viewer.js";

export const LAYERS_CHANGED_EVENT = "atomsculptor:layers-changed";

function cloneAtoms(atoms) {
  return atoms.map((atom) => ({ ...atom }));
}

function cloneCell(cell) {
  return Array.isArray(cell) ? cell.map((vec) => [...vec]) : null;
}

function clonePbc(pbc) {
  return Array.isArray(pbc) ? [...pbc] : [false, false, false];
}

function cloneLayers(layers) {
  return layers.map((layer) => ({
    ...layer,
    cell: cloneCell(layer.cell),
    pbc: clonePbc(layer.pbc),
  }));
}

function sortComparable(left, right) {
  return String(left).localeCompare(String(right), undefined, { numeric: true });
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
      || a.layerId !== b.layerId
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

function layerListsEqual(left, right) {
  if (left.length !== right.length) return false;
  for (let i = 0; i < left.length; i += 1) {
    const a = left[i];
    const b = right[i];
    if (
      a.id !== b.id
      || a.type !== b.type
      || a.name !== b.name
      || !matrixListsEqual(a.cell, b.cell)
      || !arraysEqual(a.pbc, b.pbc)
    ) {
      return false;
    }
  }
  return true;
}

function structureStatesEqual(left, right) {
  return (
    atomListsEqual(left.atoms, right.atoms)
    && layerListsEqual(left.layers, right.layers)
    && matrixListsEqual(left.cell, right.cell)
    && arraysEqual(left.pbc, right.pbc)
    && arraysEqual(left.selected, right.selected)
    && arraysEqual(left.selectedLayers, right.selectedLayers)
    && left.layerSeq === right.layerSeq
  );
}

function emitLayersChanged() {
  document.dispatchEvent(new CustomEvent(LAYERS_CHANGED_EVENT));
}

function createLayerId() {
  S.layerSeq += 1;
  return `atoms-${S.layerSeq}`;
}

function getLatticeLayer() {
  return S.layers.find((layer) => layer.type === "lattice") || null;
}

function getAtomLayerMap() {
  return new Map(S.layers.filter((layer) => layer.type === "atoms").map((layer) => [layer.id, layer]));
}

export function getAtomLayers() {
  return S.layers.filter((layer) => layer.type === "atoms");
}

export function getPrimarySelectedAtomLayerId() {
  for (const layer of S.layers) {
    if (layer.type === "atoms" && S.selectedLayerIds.has(layer.id)) return layer.id;
  }
  return getAtomLayers()[0]?.id || null;
}

export function isAtomIdInSelectedLayers(atomId) {
  const atom = S.atoms.find((candidate) => candidate.id === atomId);
  if (!atom) return false;
  return S.selectedLayerIds.has(atom.layerId);
}

function initializeDefaultLayers(cell, pbc) {
  S.layerSeq = 1;
  const atomLayerId = "atoms-1";
  S.layers = [
    {
      id: "lattice",
      type: "lattice",
      name: "Lattice",
      cell: cloneCell(cell),
      pbc: clonePbc(pbc),
    },
    {
      id: atomLayerId,
      type: "atoms",
      name: "Atoms 1",
      cell: cloneCell(cell),
      pbc: clonePbc(pbc),
    },
  ];
  S.selectedLayerIds = new Set([atomLayerId]);
}

function normalizeLayerState() {
  if (!Array.isArray(S.layers) || !S.layers.length) {
    initializeDefaultLayers(S.cell, S.pbc);
  }

  let lattice = getLatticeLayer();
  if (!lattice) {
    lattice = {
      id: "lattice",
      type: "lattice",
      name: "Lattice",
      cell: cloneCell(S.cell),
      pbc: clonePbc(S.pbc),
    };
    S.layers.unshift(lattice);
  }

  if (!Array.isArray(lattice.cell) || lattice.cell.length !== 3) lattice.cell = cloneCell(S.cell);
  if (!Array.isArray(lattice.pbc) || lattice.pbc.length !== 3) lattice.pbc = clonePbc(S.pbc);

  let atomLayers = getAtomLayers();
  if (!atomLayers.length) {
    const id = createLayerId();
    S.layers.push({ id, type: "atoms", name: "Atoms", cell: cloneCell(S.cell), pbc: clonePbc(S.pbc) });
    atomLayers = getAtomLayers();
  }

  const atomLayerIds = new Set(atomLayers.map((layer) => layer.id));
  if (!(S.selectedLayerIds instanceof Set)) {
    S.selectedLayerIds = new Set();
  }
  S.selectedLayerIds = new Set([...S.selectedLayerIds].filter((id) => atomLayerIds.has(id)));
  if (!S.selectedLayerIds.size) {
    S.selectedLayerIds = new Set([atomLayers[0].id]);
  }

  for (const atom of S.atoms) {
    if (!atom.layerId || !atomLayerIds.has(atom.layerId)) {
      atom.layerId = atomLayers[0].id;
    }
  }

  const seqCandidate = atomLayers
    .map((layer) => Number.parseInt(String(layer.id).replace("atoms-", ""), 10))
    .filter((value) => Number.isFinite(value));
  S.layerSeq = Math.max(S.layerSeq || 0, seqCandidate.length ? Math.max(...seqCandidate) : 1);
}

function normalizeSelection(selected) {
  const atomIds = new Set(S.atoms.map((atom) => atom.id));
  return new Set(selected.filter((id) => atomIds.has(id) && isAtomIdInSelectedLayers(id)));
}

export function enforceLayerSelectionConstraints() {
  S.selected = normalizeSelection([...S.selected]);
  if (S.hovered !== null && !isAtomIdInSelectedLayers(S.hovered)) {
    S.hovered = null;
  }
}

function applyStructureState(state) {
  S.atoms = cloneAtoms(state.atoms || []);
  S.layers = cloneLayers(state.layers || []);
  S.selectedLayerIds = new Set(state.selectedLayers || []);
  S.layerSeq = Number.isFinite(state.layerSeq) ? state.layerSeq : 1;
  S.cell = cloneCell(state.cell);
  S.pbc = clonePbc(state.pbc);
  normalizeLayerState();
  S.selected = normalizeSelection(state.selected || []);
  S.hovered = null;
  rebuildScene();
  updateStatusBar();
  emitLayersChanged();
}

function pushUndoState(state) {
  S.undoStack.push(state);
  if (S.undoStack.length > MAX_UNDO_ENTRIES) S.undoStack.shift();
}

export function snapshotStructureState() {
  normalizeLayerState();
  return {
    atoms: cloneAtoms(S.atoms),
    layers: cloneLayers(S.layers),
    cell: cloneCell(S.cell),
    pbc: clonePbc(S.pbc),
    selected: [...S.selected].sort(sortComparable),
    selectedLayers: [...S.selectedLayerIds].sort(sortComparable),
    layerSeq: S.layerSeq,
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
  emitLayersChanged();
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
  const layerCount = S.selectedLayerIds.size;
  $("#sb-sel").textContent = `${S.selected.size} selected · ${layerCount} layer${layerCount === 1 ? "" : "s"}`;
  $("#sb-hint").textContent = MODE_HINT[S.mode] || "";
}

function initializeLoadedStructureLayers(data) {
  const loadedLayers = Array.isArray(data.layers) ? cloneLayers(data.layers) : [];
  const hasLayeredPayload = loadedLayers.length > 0;

  if (!hasLayeredPayload) {
    initializeDefaultLayers(data.cell, data.pbc);
    const layerId = getPrimarySelectedAtomLayerId();
    S.atoms = (data.atoms || []).map((atom) => ({ ...atom, layerId }));
    return;
  }

  S.layers = loadedLayers;
  normalizeLayerState();

  const atomLayers = getAtomLayers();
  const fallbackLayerId = atomLayers[0]?.id || "atoms-1";
  const atomLayerIds = new Set(atomLayers.map((layer) => layer.id));
  S.atoms = (data.atoms || []).map((atom) => {
    const layerId = atomLayerIds.has(atom.layerId) ? atom.layerId : fallbackLayerId;
    return { ...atom, layerId };
  });

  S.selectedLayerIds = new Set([fallbackLayerId]);
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
    S.cell = data.cell;
    S.pbc = data.pbc;
    initializeLoadedStructureLayers(data);
    normalizeLayerState();
    S.selected = new Set();
    S.hovered = null;
    resetStructureHistory();
    rebuildScene();
    $("#struct-file-label").textContent = data.path;
    $("#viewer-empty").style.display = "none";
    resetCamera();
    updateStatusBar();
    emitLayersChanged();
  } catch (e) {
    console.error("loadStructure", e);
  }
}

function deriveLayeredSavePath(path) {
  if (!path) return path;
  if (path.toLowerCase().endsWith(".lxyz")) return path;

  const slash = path.lastIndexOf("/");
  const dir = slash >= 0 ? path.slice(0, slash + 1) : "";
  const name = slash >= 0 ? path.slice(slash + 1) : path;
  const dot = name.lastIndexOf(".");
  if (dot > 0) {
    return `${dir}${name.slice(0, dot)}.lxyz`;
  }
  return `${dir}${name}.lxyz`;
}

export async function saveStructure() {
  if (!S.structPath) {
    alert("No structure loaded.");
    return;
  }

  try {
    const savePath = deriveLayeredSavePath(S.structPath);
    const resp = await fetch("/api/structure/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path: savePath,
        atoms: S.atoms,
        layers: S.layers,
        cell: S.cell,
        pbc: S.pbc,
      }),
    });
    const data = await resp.json();

    if (data.ok) {
      S.structPath = data.path || savePath;
      $("#struct-file-label").textContent = S.structPath;
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

export async function exportStructure(exportFormat) {
  if (!S.structPath) {
    return { ok: false, error: "No structure loaded." };
  }

  try {
    const resp = await fetch("/api/structure/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path: S.structPath,
        format: exportFormat,
      }),
    });

    if (!resp.ok) {
      const err = await parseJsonResponseSafe(resp);
      return { ok: false, error: err.error || `HTTP ${resp.status}` };
    }

    const blob = await resp.blob();
    const dispo = resp.headers.get("Content-Disposition") || "";
    const match = /filename="?([^";]+)"?/i.exec(dispo);
    const filename = match ? match[1] : `export.${exportFormat}`;

    const url = URL.createObjectURL(blob);
    try {
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } finally {
      URL.revokeObjectURL(url);
    }

    return { ok: true };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

/** – format types understood by the OS save dialog and our backend */
const EXPORT_FORMAT_TYPES = [
  { description: "CIF",                accept: { "chemical/x-cif":    [".cif"]    }, format: "cif"    },
  { description: "XYZ",                accept: { "chemical/x-xyz":    [".xyz"]    }, format: "xyz"    },
  { description: "Extended XYZ",       accept: { "chemical/x-extxyz": [".extxyz"] }, format: "extxyz" },
  { description: "POSCAR / VASP",      accept: { "text/plain":        [".vasp"]   }, format: "poscar" },
  { description: "PDB",                accept: { "chemical/x-pdb":    [".pdb"]    }, format: "pdb"    },
];

/**
 * Open the OS-native "Save As" dialog (via the File System Access API) and
 * write the converted structure to the chosen location.
 * Returns { ok, error }.  `ok` is true even when the user cancels.
 */
export async function exportStructureWithPicker(suggestedName) {
  if (!S.structPath) {
    return { ok: false, error: "No structure loaded." };
  }

  let handle;
  try {
    handle = await window.showSaveFilePicker({
      suggestedName: `${suggestedName}.cif`,
      types: EXPORT_FORMAT_TYPES.map(({ description, accept }) => ({ description, accept })),
    });
  } catch (e) {
    if (e.name === "AbortError") return { ok: true }; // user cancelled — not an error
    return { ok: false, error: String(e) };
  }

  // Derive the format from the extension the user typed/chose
  const ext = handle.name.split(".").pop().toLowerCase();
  const spec = EXPORT_FORMAT_TYPES.find(
    (f) => Object.values(f.accept)[0].includes(`.${ext}`)
  );
  const fmt = spec ? spec.format : "cif";

  try {
    const resp = await fetch("/api/structure/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: S.structPath, format: fmt }),
    });

    if (!resp.ok) {
      const err = await parseJsonResponseSafe(resp);
      return { ok: false, error: err.error || `HTTP ${resp.status}` };
    }

    const blob = await resp.blob();
    const writable = await handle.createWritable();
    await writable.write(blob);
    await writable.close();
    return { ok: true };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

export function deleteAtomById(id) {
  deleteAtomsByIds([id]);
}

export function deleteSelected() {
  deleteAtomsByIds([...S.selected]);
}

export function addAtom(atom, beforeState = null) {
  normalizeLayerState();
  const snapshot = beforeState || snapshotStructureState();
  const layerId = atom.layerId || getPrimarySelectedAtomLayerId() || getAtomLayers()[0].id;
  S.atoms.push({ ...atom, layerId });
  rebuildScene();
  updateStatusBar();
  emitLayersChanged();
  recordStructureEdit(snapshot);
}

/** Add multiple atoms in a single undo-able operation. Returns their IDs. */
export function addAtomsBatch(atoms) {
  normalizeLayerState();
  const snapshot = snapshotStructureState();
  const layerId = getPrimarySelectedAtomLayerId() || getAtomLayers()[0].id;
  const ids = [];
  for (const atom of atoms) {
    const lid = atom.layerId || layerId;
    S.atoms.push({ ...atom, layerId: lid });
    ids.push(atom.id);
  }
  rebuildScene();
  updateStatusBar();
  emitLayersChanged();
  recordStructureEdit(snapshot);
  return ids;
}

export function setSelectedAtomsSymbol(symbol) {
  const nextSymbol = String(symbol || "").trim();
  if (!nextSymbol) return false;
  if (!S.selected || S.selected.size === 0) return false;

  const snapshot = snapshotStructureState();
  let changed = false;
  for (const atom of S.atoms) {
    if (!S.selected.has(atom.id)) continue;
    if (atom.symbol === nextSymbol) continue;
    atom.symbol = nextSymbol;
    changed = true;
  }

  if (!changed) return false;
  rebuildScene();
  updateStatusBar();
  emitLayersChanged();
  recordStructureEdit(snapshot);
  return true;
}

export function applyLattice(realMatrix, scaleAtoms) {
  const beforeState = snapshotStructureState();
  const currentCell = Array.isArray(S.cell) && S.cell.length === 3 ? S.cell : [[1, 0, 0], [0, 1, 0], [0, 0, 1]];

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
  const lattice = getLatticeLayer();
  if (lattice) {
    lattice.cell = cloneCell(realMatrix);
    lattice.pbc = clonePbc(S.pbc);
  }
  rebuildScene();
  updateStatusBar();
  emitLayersChanged();
  recordStructureEdit(beforeState);
}

export function setSelectedAtomLayers(layerIds) {
  normalizeLayerState();
  const atomLayerMap = getAtomLayerMap();
  const selected = [...new Set(layerIds)].filter((id) => atomLayerMap.has(id));
  if (!selected.length) selected.push(getAtomLayers()[0].id);

  const before = [...S.selectedLayerIds].sort(sortComparable);
  const after = [...selected].sort(sortComparable);
  if (arraysEqual(before, after)) return false;

  S.selectedLayerIds = new Set(selected);
  // If the user explicitly changed which atom layers are selected, ensure
  // any temporary selection-overlay hiding is reset so future selections
  // are visible (don't keep atoms invisibly hidden from a previous state).
  S.selectionLayerHidden = false;
  enforceLayerSelectionConstraints();
  updateAtomVisuals();
  updateStatusBar();
  emitLayersChanged();
  return true;
}

export function addAtomsLayer() {
  normalizeLayerState();
  const beforeState = snapshotStructureState();
  const id = createLayerId();
  S.layers.push({
    id,
    type: "atoms",
    name: `Atoms ${S.layerSeq}`,
    cell: cloneCell(S.cell),
    pbc: clonePbc(S.pbc),
  });
  S.selectedLayerIds = new Set([id]);
  // Ensure selection overlay is visible/reset after creating/selecting a new layer
  S.selectionLayerHidden = false;
  enforceLayerSelectionConstraints();
  updateAtomVisuals();
  updateStatusBar();
  emitLayersChanged();
  recordStructureEdit(beforeState);
  return id;
}

export function deleteSelectedAtomLayers() {
  normalizeLayerState();
  const atomLayers = getAtomLayers();
  const selectedIds = atomLayers.map((layer) => layer.id).filter((id) => S.selectedLayerIds.has(id));
  if (!selectedIds.length) return { ok: false, error: "Select at least one atom layer." };
  if (selectedIds.length >= atomLayers.length) {
    return { ok: false, error: "At least one atom layer must remain." };
  }

  const beforeState = snapshotStructureState();
  const deleted = new Set(selectedIds);
  S.layers = S.layers.filter((layer) => layer.type !== "atoms" || !deleted.has(layer.id));
  S.atoms = S.atoms.filter((atom) => !deleted.has(atom.layerId));

  const fallback = getAtomLayers()[0]?.id;
  S.selectedLayerIds = fallback ? new Set([fallback]) : new Set();
  // Reset selection-overlay hiding when layers are removed so subsequent
  // selections aren't inadvertently invisible due to a previous hide toggle.
  S.selectionLayerHidden = false;
  enforceLayerSelectionConstraints();
  rebuildScene();
  updateStatusBar();
  emitLayersChanged();
  recordStructureEdit(beforeState);
  return { ok: true };
}

export function mergeSelectedAtomLayers() {
  normalizeLayerState();
  const orderedSelected = S.layers
    .filter((layer) => layer.type === "atoms" && S.selectedLayerIds.has(layer.id))
    .map((layer) => layer.id);
  if (orderedSelected.length < 2) {
    return { ok: false, error: "Select at least two atom layers to merge." };
  }

  const beforeState = snapshotStructureState();
  const target = orderedSelected[0];
  const merged = new Set(orderedSelected.slice(1));

  for (const atom of S.atoms) {
    if (merged.has(atom.layerId)) atom.layerId = target;
  }
  S.layers = S.layers.filter((layer) => !(layer.type === "atoms" && merged.has(layer.id)));
  S.selectedLayerIds = new Set([target]);
  // Merging changes which layers are active; reset selection overlay hiding
  // so visual state isn't carried unexpectedly into the merged layer.
  S.selectionLayerHidden = false;

  enforceLayerSelectionConstraints();
  rebuildScene();
  updateStatusBar();
  emitLayersChanged();
  recordStructureEdit(beforeState);
  return { ok: true, targetLayerId: target };
}

export function useLatticeFromLayer(layerId) {
  normalizeLayerState();
  const source = S.layers.find((layer) => layer.type === "atoms" && layer.id === layerId);
  if (!source) return { ok: false, error: "Atom layer not found." };

  if (!Array.isArray(source.cell) || source.cell.length !== 3) {
    return { ok: false, error: "This atom layer has no lattice metadata." };
  }

  const lattice = getLatticeLayer();
  if (!lattice) return { ok: false, error: "Lattice layer not found." };

  const beforeState = snapshotStructureState();
  lattice.cell = cloneCell(source.cell);
  lattice.pbc = clonePbc(source.pbc);
  S.cell = cloneCell(source.cell);
  S.pbc = clonePbc(source.pbc);

  rebuildScene();
  updateStatusBar();
  recordStructureEdit(beforeState);
  emitLayersChanged();
  return { ok: true };
}

export function toggleLayerVisibility(layerId) {
  const layer = S.layers.find((l) => l.id === layerId);
  if (!layer) return;
  layer.hidden = !layer.hidden;
  rebuildScene();
  emitLayersChanged();
}

export function toggleSelectionLayerVisibility() {
  S.selectionLayerHidden = !S.selectionLayerHidden;
  rebuildScene();
  emitLayersChanged();
  return { ok: true, hidden: S.selectionLayerHidden };
}

export function extractSelectedToNewLayer() {
  if (!S.selected || S.selected.size === 0) return { ok: false, error: "No atoms selected." };
  normalizeLayerState();
  const before = snapshotStructureState();
  const id = createLayerId();
  const layer = {
    id,
    type: "atoms",
    name: `Atoms ${S.layerSeq}`,
    cell: cloneCell(S.cell),
    pbc: clonePbc(S.pbc),
  };
  S.layers.push(layer);

  // Move selected atoms onto the new layer
  for (const atom of S.atoms) {
    if (S.selected.has(atom.id)) atom.layerId = id;
  }

  // Select the new layer and clear selection of layers as appropriate
  S.selectedLayerIds = new Set([id]);
  // Reset any selection-overlay hiding when we change selection layers via extraction
  S.selectionLayerHidden = false;
  enforceLayerSelectionConstraints();
  rebuildScene();
  updateStatusBar();
  emitLayersChanged();
  recordStructureEdit(before);
  return { ok: true, layerId: id };
}

/* ── Selection utilities ─────────────────────────────────────────────────── */

export async function selectAtomsByTypes(symbols) {
  if (!Array.isArray(symbols)) symbols = [symbols];
  const set = new Set(symbols.map(s => String(s).trim()).filter(Boolean));
  const before = snapshotStructureState();
  S.selected = new Set(S.atoms.filter((a) => set.has(a.symbol) && S.selectedLayerIds.has(a.layerId)).map((a) => a.id));
  enforceLayerSelectionConstraints();
  rebuildScene();
  updateStatusBar();
  emitLayersChanged();
  recordStructureEdit(before);
  return { ok: true, count: S.selected.size };
}

export async function expandSelectionByRadius(radius) {
  const before = snapshotStructureState();
  if (!Number.isFinite(radius) || radius <= 0) return { ok: false, error: 'Invalid radius' };
  const sel = new Set(S.selected);
  const selAtoms = S.atoms.filter((a) => sel.has(a.id));
  if (!selAtoms.length) return { ok: false, error: 'No atoms selected to expand from' };
  const r2 = radius * radius;
  for (const atom of S.atoms) {
    if (!S.selectedLayerIds.has(atom.layerId)) continue;
    if (sel.has(atom.id)) continue;
    for (const s of selAtoms) {
      const dx = atom.x - s.x; const dy = atom.y - s.y; const dz = atom.z - s.z;
      if ((dx*dx + dy*dy + dz*dz) <= r2) { sel.add(atom.id); break; }
    }
  }
  S.selected = sel;
  enforceLayerSelectionConstraints();
  rebuildScene();
  updateStatusBar();
  emitLayersChanged();
  recordStructureEdit(before);
  return { ok: true, count: S.selected.size };
}

export async function invertSelection() {
  const before = snapshotStructureState();
  const newSel = new Set();
  for (const atom of S.atoms) {
    if (!S.selectedLayerIds.has(atom.layerId)) continue;
    if (!S.selected.has(atom.id)) newSel.add(atom.id);
  }
  S.selected = newSel;
  enforceLayerSelectionConstraints();
  rebuildScene();
  updateStatusBar();
  emitLayersChanged();
  recordStructureEdit(before);
  return { ok: true, count: S.selected.size };
}

// ── Structure building tools ────────────────────────────────────────────────

function applyBuiltStructure(data) {
  S.structPath = data.path;
  S.cell = data.cell;
  S.pbc = data.pbc;
  initializeLoadedStructureLayers(data);
  normalizeLayerState();
  S.selected = new Set();
  S.hovered = null;
  resetStructureHistory();
  rebuildScene();
  $("#struct-file-label").textContent = data.path;
  $("#viewer-empty").style.display = "none";
  resetCamera();
  updateStatusBar();
  emitLayersChanged();
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

export async function appendStructureToLayer(path, targetLayerId) {
  if (!S.structPath && !S.atoms.length) {
    await loadStructure(path);
    return { ok: true, mode: "loaded", addedCount: S.atoms.length };
  }

  normalizeLayerState();
  const target = S.layers.find((layer) => layer.type === "atoms" && layer.id === targetLayerId);
  if (!target) return { ok: false, error: "Target atoms layer not found." };

  const resp = await fetch(`/api/structure?path=${encodeURIComponent(path)}`);
  const data = await parseJsonResponseSafe(resp);
  if (data.error) return { ok: false, error: data.error };

  const beforeState = snapshotStructureState();
  const targetWasEmpty = !S.atoms.some((atom) => atom.layerId === target.id);
  let nextId = S.atoms.length ? Math.max(...S.atoms.map((atom) => atom.id)) + 1 : 0;
  const imported = (data.atoms || []).map((atom) => ({ ...atom, id: nextId++, layerId: target.id }));
  S.atoms.push(...imported);

  // A fresh atoms layer should carry the source structure's lattice metadata.
  if (targetWasEmpty) {
    target.cell = cloneCell(data.cell);
    target.pbc = clonePbc(data.pbc);
  }

  rebuildScene();
  updateStatusBar();
  emitLayersChanged();
  recordStructureEdit(beforeState);
  return { ok: true, mode: "append", addedCount: imported.length };
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

export async function buildInterfaces(params) {
  const resp = await fetch("/api/structure/build-interfaces", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return parseJsonResponseSafe(resp);
}

export async function saveInterfaceChoice(poscar, filename) {
  const resp = await fetch("/api/structure/build-interfaces/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ poscar, filename }),
  });
  const data = await parseJsonResponseSafe(resp);
  if (data.error) return data;
  applyBuiltStructure(data);
  return data;
}

// Listen for viewer-driven open requests (e.g., drag-and-drop onto viewer)
document.addEventListener("atomsculptor:open-structure", async (event) => {
  try {
    if (!event || !event.detail || !event.detail.path) return;
    const path = event.detail.path;
    const addToNew = Boolean(event.detail.addToNewLayer);

    // If the viewer requested appending to a new atoms layer and we already have layers,
    // create a new layer and append the structure into it. Otherwise, open as a new structure.
    if (addToNew && Array.isArray(S.layers) && S.layers.length > 0) {
      try {
        const layerId = addAtomsLayer();
        const result = await appendStructureToLayer(path, layerId);
        if (!result.ok) console.error("appendStructureToLayer failed", result.error);
      } catch (e) {
        console.error("open-structure append handler", e);
      }
      return;
    }

    loadStructure(path);
  } catch (e) {
    console.error("open-structure handler", e);
  }
});
