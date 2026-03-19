/**
 * editor.js – Edit-mode interactions: select, box-select, drag, rotate, add, delete.
 */

import { S } from "./state.js";
import { $, $$ } from "./utils.js";
import {
  raycastAtoms, atomIdFromMesh, setOrbitEnabled,
  rebuildScene, updateAtomVisuals, syncMeshPositionsToAtoms,
  computeCentroid, elemColor, resetCamera,
} from "./viewer.js";
import { updateStatusBar, deleteAtomById, deleteSelected, saveStructure } from "./structure.js";

// ── Select ──────────────────────────────────────────────────────────────────

function onSelectClick(e) {
  const hit = raycastAtoms(e);
  if (!hit) {
    if (!e.shiftKey && !e.ctrlKey) {
      S.selected.clear();
      updateAtomVisuals();
      updateStatusBar();
    }
    return;
  }

  const id = atomIdFromMesh(hit.object);
  if (e.shiftKey || e.ctrlKey) {
    if (S.selected.has(id)) S.selected.delete(id);
    else S.selected.add(id);
  } else {
    S.selected.clear();
    S.selected.add(id);
  }

  updateAtomVisuals();
  updateStatusBar();
}

// ── Delete ──────────────────────────────────────────────────────────────────

function onDeleteClick(e) {
  const hit = raycastAtoms(e);
  if (!hit) return;
  deleteAtomById(atomIdFromMesh(hit.object));
}

// ── Add Atom ────────────────────────────────────────────────────────────────

export function buildAddPalette() {
  const palette = $("#add-atom-palette");
  palette.innerHTML = "";
  const common = ["H", "C", "N", "O", "F", "P", "S", "Cl", "Na", "K", "Ca", "Mg", "Fe", "Cu", "Zn", "Li", "Si", "Al", "Au", "Pt"];

  for (const el of common) {
    const btn = document.createElement("button");
    btn.className = `elem-btn${el === S.addElement ? " selected" : ""}`;
    btn.textContent = el;
    btn.style.color = elemColor(el);
    btn.onclick = () => {
      S.addElement = el;
      $$(".elem-btn").forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");
    };
    palette.appendChild(btn);
  }
}

function onAddClick(e) {
  if (!S.atoms.length) return;
  const hit = raycastAtoms(e);
  if (!hit) return;

  const norm = hit.face.normal.clone().transformDirection(hit.object.matrixWorld).normalize();
  const bondLen = 1.5;
  const hitIdx = S.atomMeshes.indexOf(hit.object);
  const hitAtom = S.atoms[hitIdx];
  if (!hitAtom) return;

  const newId = S.atoms.length ? Math.max(...S.atoms.map((a) => a.id)) + 1 : 0;
  S.atoms.push({
    id: newId,
    symbol: S.addElement,
    x: hitAtom.x + (norm.x * bondLen),
    y: hitAtom.y + (norm.y * bondLen),
    z: hitAtom.z + (norm.z * bondLen),
  });

  rebuildScene();
  updateStatusBar();
}

// ── Drag ────────────────────────────────────────────────────────────────────

function onDragStart(e) {
  const hit = raycastAtoms(e);
  if (!hit) return;

  S.dragAtomId = atomIdFromMesh(hit.object);
  setOrbitEnabled(false);

  const normal = new THREE.Vector3().copy(S.camera.position).normalize();
  S.dragPlane = new THREE.Plane().setFromNormalAndCoplanarPoint(normal, hit.point);
}

function onDragMove(e) {
  if (S.dragAtomId === null) return;

  const wrap = $("#viewer-wrap");
  const rect = wrap.getBoundingClientRect();
  const x = (((e.clientX - rect.left) / rect.width) * 2) - 1;
  const y = -(((e.clientY - rect.top) / rect.height) * 2) + 1;

  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(new THREE.Vector2(x, y), S.camera);
  const target = new THREE.Vector3();
  if (!raycaster.ray.intersectPlane(S.dragPlane, target)) return;

  const c = computeCentroid();
  const atom = S.atoms.find((a) => a.id === S.dragAtomId);
  if (!atom) return;

  atom.x = target.x + c.x;
  atom.y = target.y + c.y;
  atom.z = target.z + c.z;
  syncMeshPositionsToAtoms();
}

function onDragEnd() {
  if (S.dragAtomId === null) return;
  S.dragAtomId = null;
  setOrbitEnabled(true);
  rebuildScene();
  updateStatusBar();
}

// ── Rotate ──────────────────────────────────────────────────────────────────

function onRotateStart(e) {
  if (S.selected.size === 0) {
    const hit = raycastAtoms(e);
    if (!hit) return;
    S.selected.add(atomIdFromMesh(hit.object));
    updateAtomVisuals();
    updateStatusBar();
  }

  S.rotateActive = true;
  S.rotateLast = { x: e.clientX, y: e.clientY };
  setOrbitEnabled(false);
}

function rotateSelectedByQuaternion(q) {
  if (!S.selected.size) return;

  const selectedAtoms = S.atoms.filter((a) => S.selected.has(a.id));
  if (!selectedAtoms.length) return;

  let cx = 0;
  let cy = 0;
  let cz = 0;
  for (const a of selectedAtoms) {
    cx += a.x;
    cy += a.y;
    cz += a.z;
  }
  cx /= selectedAtoms.length;
  cy /= selectedAtoms.length;
  cz /= selectedAtoms.length;

  const origin = new THREE.Vector3(cx, cy, cz);
  for (const a of selectedAtoms) {
    const v = new THREE.Vector3(a.x, a.y, a.z).sub(origin).applyQuaternion(q).add(origin);
    a.x = v.x;
    a.y = v.y;
    a.z = v.z;
  }
}

function onRotateMove(e) {
  if (!S.rotateActive || !S.rotateLast) return;

  const dx = e.clientX - S.rotateLast.x;
  const dy = e.clientY - S.rotateLast.y;
  S.rotateLast = { x: e.clientX, y: e.clientY };

  if (dx === 0 && dy === 0) return;

  const camDir = new THREE.Vector3();
  S.camera.getWorldDirection(camDir);
  const camUp = new THREE.Vector3().copy(S.camera.up).normalize();
  const camRight = new THREE.Vector3().crossVectors(camDir, camUp).normalize();

  const qYaw = new THREE.Quaternion().setFromAxisAngle(camUp, dx * 0.01);
  const qPitch = new THREE.Quaternion().setFromAxisAngle(camRight, dy * 0.01);
  const q = qYaw.multiply(qPitch);

  rotateSelectedByQuaternion(q);
  syncMeshPositionsToAtoms();
  updateAtomVisuals();
}

function onRotateEnd() {
  if (!S.rotateActive) return;
  S.rotateActive = false;
  S.rotateLast = null;
  setOrbitEnabled(true);
  rebuildScene();
  updateStatusBar();
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
  if (!S.boxStart) return;

  const wrap = $("#viewer-wrap");
  const rect = wrap.getBoundingClientRect();
  const ex = e.clientX - rect.left;
  const ey = e.clientY - rect.top;

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
  updateStatusBar();
}

// ── Canvas event wiring ─────────────────────────────────────────────────────

export function setupCanvasEvents() {
  const canvas = $("#struct-canvas");

  canvas.addEventListener("mousemove", (e) => {
    if (S.mode === "box") {
      onBoxMove(e);
      return;
    }
    if (S.mode === "drag" && S.dragAtomId !== null) {
      onDragMove(e);
      return;
    }
    if (S.mode === "rotate" && S.rotateActive) {
      onRotateMove(e);
      return;
    }

    const hit = raycastAtoms(e);
    const newHover = hit ? atomIdFromMesh(hit.object) : null;
    if (newHover !== S.hovered) {
      S.hovered = newHover;
      updateAtomVisuals();
    }

    if (S.mode === "rotate") {
      canvas.style.cursor = S.rotateActive ? "grabbing" : "grab";
    } else {
      const pointerMode = S.mode === "select" || S.mode === "delete" || S.mode === "drag";
      canvas.style.cursor = newHover !== null && pointerMode ? "pointer" : "default";
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
    if (S.mode === "box") onBoxStart(e);
    else if (S.mode === "drag") onDragStart(e);
    else if (S.mode === "rotate") onRotateStart(e);
  });

  canvas.addEventListener("mouseup", (e) => {
    if (e.button !== 0) return;
    if (S.mode === "box") onBoxEnd(e);
    else if (S.mode === "drag") onDragEnd();
    else if (S.mode === "rotate") onRotateEnd();
  });

  canvas.addEventListener("click", (e) => {
    if (S.mode === "select") onSelectClick(e);
    else if (S.mode === "delete") onDeleteClick(e);
    else if (S.mode === "add") onAddClick(e);
  });
}

// ── Mode switching & toolbar ────────────────────────────────────────────────

export function setMode(mode) {
  S.mode = mode;
  $$(".tb-btn[data-mode]").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === mode && mode !== "");
  });

  setOrbitEnabled(mode === "orbit");
  updateAtomVisuals();
  updateStatusBar();

  const palette = $("#add-atom-palette");
  if (mode === "add") {
    buildAddPalette();
    palette.classList.add("show");
  } else {
    palette.classList.remove("show");
  }
}

export function wireToolbar() {
  document.querySelectorAll(".tb-btn[data-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.dataset.mode;
      if (mode) setMode(mode);
    });
  });

  $("#tb-reset").addEventListener("click", resetCamera);
  $("#tb-save").addEventListener("click", saveStructure);
  $("#tb-delete").addEventListener("click", () => {
    if (S.mode === "delete") deleteSelected();
    else setMode("delete");
  });
}

// ── Keyboard shortcuts ──────────────────────────────────────────────────────

export function wireKeyboardShortcuts() {
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT") return;

    if (e.key === "1") setMode("orbit");
    else if (e.key === "2") setMode("select");
    else if (e.key === "3") setMode("box");
    else if (e.key === "4") setMode("drag");
    else if (e.key === "5") setMode("rotate");
    else if (e.key === "6") setMode("add");
    else if (e.key === "7") setMode("delete");
    else if (e.key === "Delete" || e.key === "Backspace") deleteSelected();
    else if (e.key === "Escape") {
      S.selected.clear();
      updateAtomVisuals();
      updateStatusBar();
    } else if ((e.ctrlKey || e.metaKey) && e.key === "s") {
      e.preventDefault();
      saveStructure();
    } else if (e.key.toLowerCase() === "a" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      S.selected = new Set(S.atoms.map((a) => a.id));
      updateAtomVisuals();
      updateStatusBar();
    }
  });
}
