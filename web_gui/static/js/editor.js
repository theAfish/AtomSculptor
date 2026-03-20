/**
 * editor.js – Canvas interaction: selection, box-select, mode switching,
 *             and keyboard shortcuts for the structure editor.
 *
 * Tool panel UIs (add atom, surface, supercell, lattice) are in panels.js.
 */

import { S } from "./state.js";
import { $, $$ } from "./utils.js";
import {
  raycastAtoms, atomIdFromMesh, setOrbitEnabled,
  updateAtomVisuals, resetCamera, setViewDirection,
} from "./viewer.js";
import {
  deleteAtomById,
  deleteSelected,
  redoStructureEdit,
  saveStructure,
  undoStructureEdit,
  updateStatusBar,
} from "./structure.js";
import { updateGizmo, nudgeTransform, isGizmoActive } from "./gizmo.js";
import { closeAllPanels, toggleAddPanel } from "./panels.js";

const TRANSFORM_MODES = new Set(["translate", "rotate", "scale"]);

// ── Select ──────────────────────────────────────────────────────────────────

function onSelectClick(e) {
  const hit = raycastAtoms(e);
  if (!hit) {
    if (!e.shiftKey) {
      S.selected.clear();
      updateAtomVisuals();
      updateGizmo();
      updateStatusBar();
    }
    return;
  }

  const id = atomIdFromMesh(hit.object);
  if (e.shiftKey) {
    S.selected.add(id);
  } else {
    S.selected.clear();
    S.selected.add(id);
  }

  updateAtomVisuals();
  updateGizmo();
  updateStatusBar();
}

// ── Delete ──────────────────────────────────────────────────────────────────

function onDeleteClick(e) {
  const hit = raycastAtoms(e);
  if (!hit) return;
  deleteAtomById(atomIdFromMesh(hit.object));
  updateGizmo();
}

// ── Box Select ──────────────────────────────────────────────────────────────

function onBoxStart(e) {
  setOrbitEnabled(false);
  const wrap = $("#viewer-wrap");
  const rect = wrap.getBoundingClientRect();
  S.boxStart = { x: e.clientX - rect.left, y: e.clientY - rect.top };

  const overlay = $("#box-select-overlay");
  overlay.style.left = `${S.boxStart.x}px`;
  overlay.style.top = `${S.boxStart.y}px`;
  overlay.style.width = "0px";
  overlay.style.height = "0px";
  overlay.style.display = "block";
}

function onBoxMove(e) {
  if (!S.boxStart) return;
  const wrap = $("#viewer-wrap");
  const rect = wrap.getBoundingClientRect();

  const cx = e.clientX - rect.left;
  const cy = e.clientY - rect.top;
  const x = Math.min(S.boxStart.x, cx);
  const y = Math.min(S.boxStart.y, cy);
  const w = Math.abs(cx - S.boxStart.x);
  const h = Math.abs(cy - S.boxStart.y);

  const o = $("#box-select-overlay");
  o.style.left = `${x}px`;
  o.style.top = `${y}px`;
  o.style.width = `${w}px`;
  o.style.height = `${h}px`;
}

function onBoxEnd(e) {
  if (!S.boxStart) return false;

  const wrap = $("#viewer-wrap");
  const rect = wrap.getBoundingClientRect();
  const ex = e.clientX - rect.left;
  const ey = e.clientY - rect.top;

  const dx = ex - S.boxStart.x;
  const dy = ey - S.boxStart.y;
  const clickThreshold = 4;
  const isClick = Math.abs(dx) < clickThreshold && Math.abs(dy) < clickThreshold;

  if (isClick) {
    S.boxStart = null;
    $("#box-select-overlay").style.display = "none";
    setOrbitEnabled(true);
    return false;
  }

  const x0 = ((Math.min(S.boxStart.x, ex) / rect.width) * 2) - 1;
  const y0 = -((Math.min(S.boxStart.y, ey) / rect.height) * 2) + 1;
  const x1 = ((Math.max(S.boxStart.x, ex) / rect.width) * 2) - 1;
  const y1 = -((Math.max(S.boxStart.y, ey) / rect.height) * 2) + 1;

  if (!e.shiftKey && !e.ctrlKey) S.selected.clear();

  const proj = new THREE.Vector3();
  for (const mesh of S.atomMeshes) {
    proj.copy(mesh.position).project(S.camera);
    if (proj.x >= x0 && proj.x <= x1 && proj.y <= y0 && proj.y >= y1) {
      S.selected.add(mesh.userData.atomId);
    }
  }

  S.boxStart = null;
  $("#box-select-overlay").style.display = "none";
  setOrbitEnabled(true);
  updateAtomVisuals();
  updateGizmo();
  updateStatusBar();
  return true;
}

// ── Canvas event wiring ─────────────────────────────────────────────────────

export function setupCanvasEvents() {
  const canvas = $("#struct-canvas");
  const hoverModes = new Set(["orbit", "delete", "translate", "rotate", "scale"]);
  let pendingHover = null;
  let hoverTickScheduled = false;
  let transientBoxSelectActive = false;
  let suppressNextSelectClick = false;
  let leftDownPos = null;
  let leftDragMoved = false;

  // In orbit / transform modes, Shift+left drag starts box selection.
  // Capture phase runs before OrbitControls' own listeners.
  canvas.addEventListener("mousedown", (e) => {
    if (e.button !== 0 || !e.shiftKey) return;
    if (S.mode !== "orbit" && !TRANSFORM_MODES.has(S.mode)) return;
    if (isGizmoActive()) return;       // don't hijack gizmo interaction
    setOrbitEnabled(false);
  }, true);

  const runHoverHitTest = () => {
    hoverTickScheduled = false;
    if (!pendingHover) return;

    const hoverEvt = pendingHover;
    pendingHover = null;

    const hit = raycastAtoms(hoverEvt);
    const newHover = hit ? atomIdFromMesh(hit.object) : null;
    if (newHover !== S.hovered) {
      S.hovered = newHover;
      updateAtomVisuals();
    }

    const pointerMode = hoverModes.has(S.mode);
    canvas.style.cursor = newHover !== null && pointerMode ? "pointer" : "default";
  };

  canvas.addEventListener("mousemove", (e) => {
    if ((e.buttons & 1) !== 0 && leftDownPos) {
      const dx = e.clientX - leftDownPos.x;
      const dy = e.clientY - leftDownPos.y;
      if ((dx * dx) + (dy * dy) > 9) leftDragMoved = true;
    }

    if (S.mode === "box" || transientBoxSelectActive) {
      onBoxMove(e);
      return;
    }

    if (!hoverModes.has(S.mode)) {
      if (S.hovered !== null) {
        S.hovered = null;
        updateAtomVisuals();
      }
      return;
    }

    // While dragging (button pressed), skip hover raycasts.
    if (e.buttons !== 0) return;

    pendingHover = { clientX: e.clientX, clientY: e.clientY };
    if (!hoverTickScheduled) {
      hoverTickScheduled = true;
      requestAnimationFrame(runHoverHitTest);
    }
  });

  canvas.addEventListener("mouseleave", () => {
    if (S.hovered !== null) {
      S.hovered = null;
      updateAtomVisuals();
    }
  });

  canvas.addEventListener("mousedown", (e) => {
    if (e.button !== 0) return;
    leftDownPos = { x: e.clientX, y: e.clientY };
    leftDragMoved = false;

    // Don't start box-select when interacting with the gizmo
    if (isGizmoActive()) return;

    if ((S.mode === "orbit" || TRANSFORM_MODES.has(S.mode)) && e.shiftKey) {
      transientBoxSelectActive = true;
      suppressNextSelectClick = false;
      onBoxStart(e);
      return;
    }

    if (S.mode === "box") onBoxStart(e);
  });

  canvas.addEventListener("mouseup", (e) => {
    if (e.button !== 0) return;

    if (transientBoxSelectActive) {
      const didBoxSelect = onBoxEnd(e);
      transientBoxSelectActive = false;
      suppressNextSelectClick = didBoxSelect;
      return;
    }

    if (S.mode === "box") onBoxEnd(e);
  });

  canvas.addEventListener("click", (e) => {
    // After a gizmo drag, suppress the click so we don't accidentally deselect.
    if (S.gizmoJustDragged) {
      S.gizmoJustDragged = false;
      leftDownPos = null;
      leftDragMoved = false;
      return;
    }

    // Orbit and transform modes share the same click-to-select behaviour.
    if (S.mode === "orbit" || TRANSFORM_MODES.has(S.mode)) {
      if (suppressNextSelectClick) {
        suppressNextSelectClick = false;
        leftDownPos = null;
        leftDragMoved = false;
        return;
      }
      if (leftDragMoved) {
        leftDownPos = null;
        leftDragMoved = false;
        return;
      }
      onSelectClick(e);
      leftDownPos = null;
      leftDragMoved = false;
      return;
    }

    if (S.mode === "delete") onDeleteClick(e);

    leftDownPos = null;
    leftDragMoved = false;
  });
}

// ── Mode switching & toolbar ────────────────────────────────────────────────

export function setMode(mode) {
  S.mode = mode;
  $$(".tb-btn[data-mode]").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === mode && mode !== "");
  });

  // Orbit stays enabled in transform modes; gizmo disables it during drag.
  const orbitActive = mode === "orbit" || TRANSFORM_MODES.has(mode);
  setOrbitEnabled(orbitActive);
  updateAtomVisuals();
  updateGizmo();
  updateStatusBar();
  closeAllPanels();
}

export function wireToolbar() {
  document.querySelectorAll(".tb-btn[data-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.dataset.mode;
      if (mode) setMode(mode);
    });
  });

  $("#tb-reset").addEventListener("click", () => {
    closeAllPanels();
    resetCamera();
  });
  $("#tb-save").addEventListener("click", () => {
    closeAllPanels();
    saveStructure();
  });
  $("#tb-delete").addEventListener("click", () => {
    if (S.mode === "delete") { deleteSelected(); updateGizmo(); }
    else setMode("delete");
  });
}

// ── Keyboard shortcuts ──────────────────────────────────────────────────────

export function wireKeyboardShortcuts() {
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT") return;

    if (e.ctrlKey || e.metaKey) {
      const key = e.key.toLowerCase();

      if (key === "z" && !e.shiftKey) {
        e.preventDefault();
        if (undoStructureEdit()) updateGizmo();
        return;
      }

      if (key === "y" || (key === "z" && e.shiftKey)) {
        e.preventDefault();
        if (redoStructureEdit()) updateGizmo();
        return;
      }
    }

    // ── Fine adjustment (WASD + arrows) when in a transform mode with selection ──
    if (TRANSFORM_MODES.has(S.mode) && S.selected.size > 0) {
      let dir = null;
      if (e.key === "ArrowUp" || e.key.toLowerCase() === "w")                              dir = "up";
      else if (e.key === "ArrowDown" || e.key.toLowerCase() === "s")                        dir = "down";
      else if (e.key === "ArrowLeft" || (e.key.toLowerCase() === "a" && !e.ctrlKey && !e.metaKey)) dir = "left";
      else if (e.key === "ArrowRight" || e.key.toLowerCase() === "d")                       dir = "right";

      if (dir) { e.preventDefault(); nudgeTransform(dir); return; }
    }

    // ── Mode switches ──
    if (e.key === "1") { setMode("orbit"); return; }
    if (e.key === "2") { setMode("box"); return; }
    if (e.key === "5") { toggleAddPanel(); return; }
    if (e.key === "6") { setMode("delete"); return; }

    if (!e.ctrlKey && !e.metaKey) {
      if (e.key.toLowerCase() === "t") { setMode("translate"); return; }
      if (e.key.toLowerCase() === "r") { setMode("rotate"); return; }
    }
      if (e.key.toLowerCase() === "e") { setMode("scale"); return; }

    // ── View direction ──
    if (e.key.toLowerCase() === "x") { setViewDirection("x"); return; }
    if (e.key.toLowerCase() === "y") { setViewDirection("y"); return; }
    if (e.key.toLowerCase() === "z") { setViewDirection("z"); return; }

    // ── Delete / Escape / Save / Select-all ──
    if (e.key === "Delete" || e.key === "Backspace") {
      deleteSelected();
      updateGizmo();
      return;
    }
    if (e.key === "Escape") {
      S.selected.clear();
      updateAtomVisuals();
      updateGizmo();
      updateStatusBar();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      saveStructure();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
      e.preventDefault();
      S.selected = new Set(S.atoms.map((a) => a.id));
      updateAtomVisuals();
      updateGizmo();
      updateStatusBar();
    }
  });
}
