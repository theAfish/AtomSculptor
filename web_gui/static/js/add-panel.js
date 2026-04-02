/**
 * add-panel.js – Add panel with periodic table (atom) and molecule (SMILES / Ketcher) tabs.
 */

import { S } from "./state.js";
import { $, $$, showError, clearError } from "./utils.js";
import { elemColor, elemTextColor } from "./viewer.js";
import { addAtom, addAtomsBatch, snapshotStructureState, LAYERS_CHANGED_EVENT } from "./structure.js";
import { setMode } from "./editor.js";
import { closeAllPanels } from "./panel-core.js";
import { PERIODIC_TABLE_ROWS, buildPeriodicRow } from "./elements.js";
import { updateGizmo } from "./gizmo.js";

/* ── Periodic table helpers ──────────────────────────────────────────────── */

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
  // Use element color as the button background and pick a readable text color
  button.style.background = elemColor(elementSymbol);
  button.style.color = elemTextColor(elementSymbol);
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

/* ── Default position ────────────────────────────────────────────────────── */

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

/* ── Tab switching ────────────────────────────────────────────────────────── */

function switchAddTab(tabName) {
  $$(".add-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.addTab === tabName);
  });
  $$(".add-tab-content").forEach((el) => {
    el.classList.toggle("show", el.id === `add-tab-${tabName}`);
  });
}

/* ── Open / toggle / add ─────────────────────────────────────────────────── */

function openAddPanel() {
  closeAllPanels();
  buildAddPalette();
  clearError("#add-error");
  clearError("#mol-error");
  const pos = computeAddDefaultPosition();
  $("#add-x").value = pos.x.toFixed(3);
  $("#add-y").value = pos.y.toFixed(3);
  $("#add-z").value = pos.z.toFixed(3);
  $("#add-panel").classList.add("show");
  $("#tb-add").classList.add("active");
}

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
  document.dispatchEvent(new CustomEvent(LAYERS_CHANGED_EVENT));
  clearError("#add-error");
  setMode("translate");
}

/* ── Wiring ──────────────────────────────────────────────────────────────── */

/* ── Ketcher modal ───────────────────────────────────────────────────────── */

let ketcherReady = false;
let ketcherLoaded = false;
let pendingKetcherMolecule = null;

function sendKetcherCommand(message) {
  const frame = /** @type {HTMLIFrameElement} */ ($("#ketcher-frame"));
  if (!frame?.contentWindow) return;
  try {
    frame.contentWindow.postMessage(message, "*");
  } catch {
    // no-op if the frame is not ready yet
  }
}

window.addEventListener("message", (event) => {
  if (!event.data || typeof event.data !== "object") return;

  if (event.data.eventType === "init") {
    ketcherReady = true;
    if (pendingKetcherMolecule) {
      sendKetcherCommand({ eventType: "ketcher-set-molecule", smiles: pendingKetcherMolecule });
      pendingKetcherMolecule = null;
    }
  }
});

function setKetcherMolecule(smiles) {
  if (!smiles) return;
  if (ketcherReady) {
    sendKetcherCommand({ eventType: "ketcher-set-molecule", smiles });
  } else {
    pendingKetcherMolecule = smiles;
  }
}

async function requestKetcherSmiles() {
  const frame = /** @type {HTMLIFrameElement} */ ($("#ketcher-frame"));
  if (!frame?.contentWindow) return "";

  if (frame.contentWindow.ketcher?.getSmiles) {
    return frame.contentWindow.ketcher.getSmiles();
  }

  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      window.removeEventListener("message", onMessage);
      reject(new Error("Timeout waiting for Ketcher SMILES response"));
    }, 3000);

    function onMessage(event) {
      if (event.source !== frame.contentWindow) return;
      if (!event.data || typeof event.data !== "object") return;

      if (event.data.eventType === "ketcher-smiles-response") {
        clearTimeout(timeout);
        window.removeEventListener("message", onMessage);
        resolve(event.data.smiles || "");
      } else if (event.data.eventType === "ketcher-smiles-error") {
        clearTimeout(timeout);
        window.removeEventListener("message", onMessage);
        reject(new Error(event.data.error || "Ketcher SMILES request failed"));
      }
    }

    window.addEventListener("message", onMessage);

    try {
      frame.contentWindow.postMessage({ eventType: "ketcher-get-smiles" }, "*");
    } catch (err) {
      clearTimeout(timeout);
      window.removeEventListener("message", onMessage);
      reject(err);
    }
  });
}

function openKetcherModal() {
  const modal = $("#ketcher-modal");
  modal.classList.add("show");

  const frame = /** @type {HTMLIFrameElement} */ ($("#ketcher-frame"));

  // Lazy-load the Ketcher editor on first open
  if (!ketcherLoaded) {
    ketcherLoaded = true;
    frame.src = "/static/ketcher/index.html";
  }

  const existing = $("#mol-smiles").value.trim();
  if (existing) {
    setKetcherMolecule(existing);
  }
}

function closeKetcherModal() {
  $("#ketcher-modal").classList.remove("show");
}

function adjustMolSmilesInput() {
  const field = $("#mol-smiles");
  if (!field) return;

  field.style.height = "auto";
  field.style.height = `${Math.min(180, field.scrollHeight)}px`;

  const length = field.value.length;
  const widthPercent = Math.min(100, Math.max(40, Math.ceil(length / 3)));
  field.style.width = `${widthPercent}%`;
}

async function ketcherAddMolecule() {
  try {
    const smiles = await requestKetcherSmiles();
    if (smiles) {
      $("#mol-smiles").value = smiles;
      adjustMolSmilesInput();
    }
  } catch (err) {
    console.warn("Could not get SMILES from Ketcher:", err);
  }

  closeKetcherModal();

  // Immediately add drawn molecule to viewport without extra manual Add Molecule click
  await addMoleculeFromPanel();
}

/* ── Add molecule ────────────────────────────────────────────────────────── */

async function addMoleculeFromPanel() {
  const smiles = $("#mol-smiles").value.trim();
  if (!smiles) {
    showError("#mol-error", "Enter a SMILES string or draw a molecule.");
    return;
  }
  clearError("#mol-error");

  const btn = $("#mol-add");
  btn.disabled = true;
  btn.textContent = "Adding…";

  try {
    const resp = await fetch("/api/structure/add-molecule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ smiles }),
    });
    const data = await resp.json();

    if (data.error) {
      showError("#mol-error", data.error);
      return;
    }

    const offset = computeAddDefaultPosition();
    let nextId = S.atoms.length ? Math.max(...S.atoms.map((a) => a.id)) + 1 : 0;

    const newAtoms = data.atoms.map((a) => ({
      id: nextId++,
      symbol: a.symbol,
      x: a.x + offset.x,
      y: a.y + offset.y,
      z: a.z + offset.z,
    }));

    const ids = addAtomsBatch(newAtoms);
    S.selected = new Set(ids);
    S.hovered = null;
    document.dispatchEvent(new CustomEvent(LAYERS_CHANGED_EVENT));
    clearError("#mol-error");
    updateGizmo();
    setMode("translate");

    // Clear SMILES after successful add to avoid leftover text.
    $("#mol-smiles").value = "";
    adjustMolSmilesInput();
  } catch (e) {
    showError("#mol-error", `Request failed: ${e}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "Add Molecule";
  }
}

/* ── Wire everything ─────────────────────────────────────────────────────── */

export function wireAddPanel() {
  $("#tb-add").addEventListener("click", toggleAddPanel);

  // Tab switching
  $$(".add-tab").forEach((btn) => {
    btn.addEventListener("click", () => switchAddTab(btn.dataset.addTab));
  });

  // Atom tab
  $("#add-cancel").addEventListener("click", () => closeAllPanels());
  $("#add-build").addEventListener("click", addAtomFromPanel);

  // Molecule tab
  $("#mol-draw-btn").addEventListener("click", openKetcherModal);
  $("#mol-add").addEventListener("click", addMoleculeFromPanel);
  $("#mol-smiles").addEventListener("input", adjustMolSmilesInput);
  $("#mol-cancel").addEventListener("click", () => closeAllPanels());

  // Ketcher modal
  $("#ketcher-add").addEventListener("click", ketcherAddMolecule);
  $("#ketcher-cancel").addEventListener("click", closeKetcherModal);
}
