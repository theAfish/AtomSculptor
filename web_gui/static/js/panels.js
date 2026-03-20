/**
 * panels.js – Tool panel management for the structure editor.
 *
 * Contains all self-contained panel UIs: add atom (with periodic table),
 * surface builder, supercell builder, and lattice operations. Each panel
 * has its own validation, API interaction, and open/close logic.
 */

import { S } from "./state.js";
import { $, $$ } from "./utils.js";
import { elemColor } from "./viewer.js";
import {
  addAtom,
  applyLattice,
  buildSurface,
  buildSupercell,
  exportStructure,
  exportStructureWithPicker,
  snapshotStructureState,
} from "./structure.js";
import { setMode } from "./editor.js";

/* ── Periodic table data ─────────────────────────────────────────────────── */

const PERIODIC_TABLE_ROWS = [
  [[1, "H"], [18, "He"]],
  [[1, "Li"], [2, "Be"], [13, "B"], [14, "C"], [15, "N"], [16, "O"], [17, "F"], [18, "Ne"]],
  [[1, "Na"], [2, "Mg"], [13, "Al"], [14, "Si"], [15, "P"], [16, "S"], [17, "Cl"], [18, "Ar"]],
  [[1, "K"], [2, "Ca"], [3, "Sc"], [4, "Ti"], [5, "V"], [6, "Cr"], [7, "Mn"], [8, "Fe"], [9, "Co"], [10, "Ni"], [11, "Cu"], [12, "Zn"], [13, "Ga"], [14, "Ge"], [15, "As"], [16, "Se"], [17, "Br"], [18, "Kr"]],
  [[1, "Rb"], [2, "Sr"], [3, "Y"], [4, "Zr"], [5, "Nb"], [6, "Mo"], [7, "Tc"], [8, "Ru"], [9, "Rh"], [10, "Pd"], [11, "Ag"], [12, "Cd"], [13, "In"], [14, "Sn"], [15, "Sb"], [16, "Te"], [17, "I"], [18, "Xe"]],
  [[1, "Cs"], [2, "Ba"], [4, "Hf"], [5, "Ta"], [6, "W"], [7, "Re"], [8, "Os"], [9, "Ir"], [10, "Pt"], [11, "Au"], [12, "Hg"], [13, "Tl"], [14, "Pb"], [15, "Bi"], [16, "Po"], [17, "At"], [18, "Rn"]],
  [[1, "Fr"], [2, "Ra"], [4, "Rf"], [5, "Db"], [6, "Sg"], [7, "Bh"], [8, "Hs"], [9, "Mt"], [10, "Ds"], [11, "Rg"], [12, "Cn"], [13, "Nh"], [14, "Fl"], [15, "Mc"], [16, "Lv"], [17, "Ts"], [18, "Og"]],
  [[4, "La"], [5, "Ce"], [6, "Pr"], [7, "Nd"], [8, "Pm"], [9, "Sm"], [10, "Eu"], [11, "Gd"], [12, "Tb"], [13, "Dy"], [14, "Ho"], [15, "Er"], [16, "Tm"], [17, "Yb"], [18, "Lu"]],
  [[4, "Ac"], [5, "Th"], [6, "Pa"], [7, "U"], [8, "Np"], [9, "Pu"], [10, "Am"], [11, "Cm"], [12, "Bk"], [13, "Cf"], [14, "Es"], [15, "Fm"], [16, "Md"], [17, "No"], [18, "Lr"]],
];

/* ── Shared panel helpers ────────────────────────────────────────────────── */

function showError(selector, message) {
  const el = $(selector);
  el.textContent = message;
  el.classList.add("show");
}

function clearError(selector) {
  const el = $(selector);
  el.classList.remove("show");
  el.textContent = "";
}

/** Close every tool panel and deactivate associated toolbar buttons. */
export function closeAllPanels() {
  $("#add-panel").classList.remove("show");
  $("#tb-add").classList.remove("active");
  $("#surface-panel").classList.remove("show");
  $("#supercell-panel").classList.remove("show");
  $("#lattice-panel").classList.remove("show");
}

/**
 * Toggle a single panel: close all others first, then show the target
 * if it was not already open. Runs `onOpen` when the panel is opening.
 */
function togglePanel(panelSelector, onOpen) {
  const panel = $(panelSelector);
  const wasOpen = panel.classList.contains("show");
  closeAllPanels();
  if (!wasOpen) {
    if (onOpen) onOpen();
    panel.classList.add("show");
  }
}

/* ── 3×3 matrix I/O utilities ────────────────────────────────────────────── */

function setMatrixInputs(prefix, matrix) {
  for (let i = 0; i < 3; i += 1) {
    for (let j = 0; j < 3; j += 1) {
      $(`#${prefix}${i}${j}`).value = Number(matrix[i][j]).toFixed(3);
    }
  }
}

function readMatrixInputs(prefix) {
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

function multiplyMatrices(a, b) {
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

/* ── Periodic table ──────────────────────────────────────────────────────── */

function buildPeriodicRow(entries) {
  const row = Array(18).fill(null);
  for (const [columnIndex, elementSymbol] of entries) {
    row[columnIndex - 1] = elementSymbol;
  }
  return row;
}

function setSelectedAddElement(elementSymbol) {
  S.addElement = elementSymbol;
  $$(".pt-elem-btn").forEach((button) => {
    button.classList.toggle("selected", button.dataset.element === elementSymbol);
  });
}

function createElementButton(elementSymbol) {
  const button = document.createElement("button");
  button.className = `pt-elem-btn${elementSymbol === S.addElement ? " selected" : ""}`;
  button.type = "button";
  button.textContent = elementSymbol;
  button.title = elementSymbol;
  button.dataset.element = elementSymbol;
  button.style.color = elemColor(elementSymbol);
  button.addEventListener("click", () => setSelectedAddElement(elementSymbol));
  return button;
}

function buildAddPalette() {
  const table = $("#add-periodic-table");
  table.innerHTML = "";

  for (let rowIndex = 0; rowIndex < PERIODIC_TABLE_ROWS.length; rowIndex += 1) {
    const rowEntries = PERIODIC_TABLE_ROWS[rowIndex];
    const rowElement = document.createElement("div");
    rowElement.className = "pt-row";

    if (rowIndex >= 7) {
      rowElement.classList.add("pt-row-series");
      if (rowIndex === 7) rowElement.classList.add("pt-row-series-start");

      const seriesElements = [...rowEntries]
        .sort((left, right) => left[0] - right[0])
        .map((entry) => entry[1]);

      for (const elementSymbol of seriesElements) {
        rowElement.appendChild(createElementButton(elementSymbol));
      }
      table.appendChild(rowElement);
      continue;
    }

    const row = buildPeriodicRow(rowEntries);
    for (const elementSymbol of row) {
      if (!elementSymbol) {
        const spacer = document.createElement("div");
        spacer.className = "pt-spacer";
        rowElement.appendChild(spacer);
        continue;
      }
      rowElement.appendChild(createElementButton(elementSymbol));
    }

    table.appendChild(rowElement);
  }
}

/* ── Add atom panel ──────────────────────────────────────────────────────── */

function computeAddDefaultPosition() {
  if (Array.isArray(S.cell) && S.cell.length === 3) {
    const [a, b, c] = S.cell;
    return {
      x: (a[0] + b[0] + c[0]) / 2,
      y: (a[1] + b[1] + c[1]) / 2,
      z: (a[2] + b[2] + c[2]) / 2,
    };
  }

  if (!S.atoms.length) return { x: 0, y: 0, z: 0 };

  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;

  for (const atom of S.atoms) {
    minX = Math.min(minX, atom.x);
    minY = Math.min(minY, atom.y);
    minZ = Math.min(minZ, atom.z);
    maxX = Math.max(maxX, atom.x);
    maxY = Math.max(maxY, atom.y);
    maxZ = Math.max(maxZ, atom.z);
  }

  return {
    x: (minX + maxX) / 2,
    y: (minY + maxY) / 2,
    z: (minZ + maxZ) / 2,
  };
}

function openAddPanel() {
  closeAllPanels();
  buildAddPalette();
  clearError("#add-error");
  const pos = computeAddDefaultPosition();
  $("#add-x").value = pos.x.toFixed(3);
  $("#add-y").value = pos.y.toFixed(3);
  $("#add-z").value = pos.z.toFixed(3);
  $("#add-panel").classList.add("show");
  $("#tb-add").classList.add("active");
}

/** Toggle the add-atom panel open/closed. */
export function toggleAddPanel() {
  if ($("#add-panel").classList.contains("show")) {
    closeAllPanels();
  } else {
    openAddPanel();
  }
}

function addAtomFromPanel() {
  const x = Number.parseFloat($("#add-x").value);
  const y = Number.parseFloat($("#add-y").value);
  const z = Number.parseFloat($("#add-z").value);
  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) {
    showError("#add-error", "Coordinates must be valid numbers.");
    return;
  }

  const newId = S.atoms.length ? Math.max(...S.atoms.map((a) => a.id)) + 1 : 0;
  const beforeState = snapshotStructureState();
  addAtom({
    id: newId,
    symbol: S.addElement,
    x,
    y,
    z,
  }, beforeState);

  S.selected = new Set([newId]);
  S.hovered = null;
  clearError("#add-error");
  setMode("translate");
}

/* ── Surface builder panel ───────────────────────────────────────────────── */

async function handleSurfaceBuild() {
  clearError("#sf-error");

  if (!S.structPath) {
    showError("#sf-error", "Load a structure first.");
    return;
  }

  const h = parseInt($("#sf-h").value, 10);
  const k = parseInt($("#sf-k").value, 10);
  const l = parseInt($("#sf-l").value, 10);
  const layers = parseInt($("#sf-layers").value, 10);
  const vacuum = parseFloat($("#sf-vacuum").value);

  if ([h, k, l].some(v => isNaN(v))) {
    showError("#sf-error", "Miller indices must be integers.");
    return;
  }
  if (h === 0 && k === 0 && l === 0) {
    showError("#sf-error", "Miller indices cannot all be zero.");
    return;
  }

  const btn = $("#sf-build");
  btn.disabled = true;
  btn.textContent = "Building...";
  try {
    const result = await buildSurface([h, k, l], layers, vacuum);
    if (result.error) {
      showError("#sf-error", result.error);
    } else {
      $("#surface-panel").classList.remove("show");
    }
  } catch (e) {
    showError("#sf-error", String(e));
  } finally {
    btn.disabled = false;
    btn.textContent = "Build";
  }
}

/* ── Supercell builder panel ─────────────────────────────────────────────── */

async function handleSupercellBuild() {
  clearError("#sc-error");

  if (!S.structPath) {
    showError("#sc-error", "Load a structure first.");
    return;
  }

  const ids = [
    ["sc-m00", "sc-m01", "sc-m02"],
    ["sc-m10", "sc-m11", "sc-m12"],
    ["sc-m20", "sc-m21", "sc-m22"],
  ];
  const matrix = ids.map((row) => row.map((id) => parseInt($(`#${id}`).value, 10)));

  if (matrix.flat().some((v) => isNaN(v))) {
    showError("#sc-error", "All matrix entries must be integers.");
    return;
  }

  const btn = $("#sc-build");
  btn.disabled = true;
  btn.textContent = "Building...";
  try {
    const result = await buildSupercell(matrix);
    if (result.error) {
      showError("#sc-error", result.error);
    } else {
      $("#supercell-panel").classList.remove("show");
    }
  } catch (e) {
    showError("#sc-error", String(e));
  } finally {
    btn.disabled = false;
    btn.textContent = "Build";
  }
}

/* ── Lattice operations panel ────────────────────────────────────────────── */

function initializeLatticePanel() {
  setMatrixInputs("la-sm", [[1, 0, 0], [0, 1, 0], [0, 0, 1]]);
  if (Array.isArray(S.cell) && S.cell.length === 3) {
    setMatrixInputs("la-rm", S.cell);
  } else {
    setMatrixInputs("la-rm", [[1, 0, 0], [0, 1, 0], [0, 0, 1]]);
  }
  $("#la-scale-atoms").checked = true;
  clearError("#la-error");
}

function handleScaleUpdate() {
  try {
    const scaleMat = readMatrixInputs("la-sm");
    const currentCell = Array.isArray(S.cell) && S.cell.length === 3
      ? S.cell : [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
    const newReal = multiplyMatrices(currentCell, scaleMat);
    setMatrixInputs("la-rm", newReal);
    clearError("#la-error");
  } catch (e) {
    showError("#la-error", String(e));
  }
}

function handleLatticeApply() {
  try {
    const realMat = readMatrixInputs("la-rm");
    const scaleAtoms = $("#la-scale-atoms").checked;
    applyLattice(realMat, scaleAtoms);
    $("#lattice-panel").classList.remove("show");
  } catch (e) {
    showError("#la-error", String(e));
  }
}

/* ── Export ──────────────────────────────────────────────────────────────── */

/**
 * Click handler for the Export toolbar button.
 * On browsers that support the File System Access API (Chrome/Edge) the OS
 * native "Save As" dialog opens with a format-type selector built in.
 * On other browsers (Firefox) a compact <dialog> modal lets the user pick
 * a format before the browser auto-downloads the file.
 */
async function triggerExport() {
  closeAllPanels();

  if ("showSaveFilePicker" in window) {
    if (!S.structPath) {
      openExportDialog("No structure loaded.");
      return;
    }
    const name = S.structPath.split("/").pop().replace(/\.[^.]+$/, "") || "structure";
    const result = await exportStructureWithPicker(name);
    if (!result.ok && result.error) openExportDialog(result.error);
    return;
  }

  // Fallback: show the modal dialog for format selection
  openExportDialog("");
}

function openExportDialog(errorMsg) {
  const dialog = document.getElementById("export-dialog");
  document.getElementById("ex-error").textContent = errorMsg || "";
  document.getElementById("ex-format").value = "cif";
  dialog.showModal();
}

async function handleDialogExport() {
  const errorEl = document.getElementById("ex-error");
  const btn = document.getElementById("ex-save");
  const format = document.getElementById("ex-format").value;

  errorEl.textContent = "";
  btn.disabled = true;
  btn.textContent = "Downloading...";

  try {
    const result = await exportStructure(format);
    if (!result.ok) {
      errorEl.textContent = result.error || "Export failed.";
      return;
    }
    document.getElementById("export-dialog").close();
  } finally {
    btn.disabled = false;
    btn.textContent = "Download";
  }
}

/* ── Wire all panel controls ─────────────────────────────────────────────── */

/** Attach event listeners for all tool panel toolbar buttons and controls. */
export function wirePanels() {
  // Add atom panel
  $("#tb-add").addEventListener("click", toggleAddPanel);
  $("#add-cancel").addEventListener("click", () => closeAllPanels());
  $("#add-build").addEventListener("click", addAtomFromPanel);

  // Surface builder
  $("#tb-surface").addEventListener("click", () => {
    togglePanel("#surface-panel", () => clearError("#sf-error"));
  });
  $("#sf-cancel").addEventListener("click", () => $("#surface-panel").classList.remove("show"));
  $("#sf-build").addEventListener("click", handleSurfaceBuild);

  // Supercell builder
  $("#tb-supercell").addEventListener("click", () => {
    togglePanel("#supercell-panel", () => clearError("#sc-error"));
  });
  $("#sc-cancel").addEventListener("click", () => $("#supercell-panel").classList.remove("show"));
  $("#sc-build").addEventListener("click", handleSupercellBuild);

  // Lattice operations
  $("#tb-lattice").addEventListener("click", () => {
    togglePanel("#lattice-panel", initializeLatticePanel);
  });
  $("#la-cancel").addEventListener("click", () => $("#lattice-panel").classList.remove("show"));
  $("#la-update-real").addEventListener("click", handleScaleUpdate);
  $("#la-apply").addEventListener("click", handleLatticeApply);

  // Export
  $("#tb-export").addEventListener("click", triggerExport);

  const exportDialog = document.getElementById("export-dialog");
  document.getElementById("ex-cancel").addEventListener("click", () => exportDialog.close());
  document.getElementById("ex-save").addEventListener("click", handleDialogExport);
  // Close on backdrop click (clicking outside the dialog box)
  exportDialog.addEventListener("click", (e) => {
    if (e.target === exportDialog) exportDialog.close();
  });
}
