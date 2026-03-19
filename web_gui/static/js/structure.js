/**
 * structure.js – Structure data operations: load, save, format detection.
 */

import { S, STRUCTURE_EXTS, STRUCTURE_PREFIXES, MODE_HINT } from "./state.js";
import { $, $$ } from "./utils.js";
import { rebuildScene, resetCamera, updateAtomVisuals } from "./viewer.js";

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
    S.selected.clear();
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
  S.atoms = S.atoms.filter((a) => a.id !== id);
  S.selected.delete(id);
  if (S.hovered === id) S.hovered = null;
  rebuildScene();
  updateStatusBar();
}

export function deleteSelected() {
  if (!S.selected.size) return;
  const toDelete = [...S.selected];
  for (const id of toDelete) deleteAtomById(id);
  S.selected.clear();
}
