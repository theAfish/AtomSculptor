/**
 * gizmo.js – Transform gizmo (translate / rotate / scale) for selected atoms.
 *
 * Uses THREE.TransformControls attached to an invisible pivot Object3D placed
 * at the centroid of the current selection.  During a gizmo drag the atom
 * world-coordinates AND their scene-meshes are updated in real time; on release
 * we do a full rebuildScene() so bonds and the centroid are recalculated.
 */

import { S } from "./state.js";
import { $ } from "./utils.js";
import {
  computeCentroid, rebuildScene, setOrbitEnabled, updateAtomVisuals,
} from "./viewer.js";
import { updateStatusBar } from "./structure.js";

/* ── internal state ─────────────────────────────────────────────────────── */

let gizmo = null;   // THREE.TransformControls
let pivot = null;   // THREE.Object3D – gizmo target

// Snapshot taken when the user starts dragging the gizmo.
let snap = null;
// { atoms: Map<id,{x,y,z}>, meshes: Map<id,Vector3>,
//   pivotPos: Vector3, pivotQuat: Quaternion, centroid: {x,y,z} }

/* ── helpers ────────────────────────────────────────────────────────────── */

function selectedAtoms() {
  return S.atoms.filter((a) => S.selected.has(a.id));
}

function selCentroid() {
  const sel = selectedAtoms();
  if (!sel.length) return { x: 0, y: 0, z: 0 };
  let cx = 0, cy = 0, cz = 0;
  for (const a of sel) { cx += a.x; cy += a.y; cz += a.z; }
  return { x: cx / sel.length, y: cy / sel.length, z: cz / sel.length };
}

function meshForAtom(id) {
  return S.atomMeshes.find((m) => m.userData.atomId === id) || null;
}

/* ── snapshot / apply ───────────────────────────────────────────────────── */

function takeSnapshot() {
  const atoms = new Map();
  const meshes = new Map();
  for (const a of selectedAtoms()) {
    atoms.set(a.id, { x: a.x, y: a.y, z: a.z });
    const m = meshForAtom(a.id);
    if (m) meshes.set(a.id, m.position.clone());
  }
  snap = {
    atoms,
    meshes,
    pivotPos: pivot.position.clone(),
    pivotQuat: pivot.quaternion.clone(),
    centroid: selCentroid(),
  };
}

function applyTransform() {
  const mode = S.mode; // always in sync with gizmo.mode

  if (mode === "translate") {
    const delta = pivot.position.clone().sub(snap.pivotPos);
    for (const [id, init] of snap.atoms) {
      const a = S.atoms.find((x) => x.id === id);
      if (!a) continue;
      a.x = init.x + delta.x;
      a.y = init.y + delta.y;
      a.z = init.z + delta.z;
    }
    for (const [id, initP] of snap.meshes) {
      const m = meshForAtom(id);
      if (!m) continue;
      m.position.set(initP.x + delta.x, initP.y + delta.y, initP.z + delta.z);
    }
  } else if (mode === "rotate") {
    const qDelta = pivot.quaternion.clone()
      .multiply(snap.pivotQuat.clone().invert());
    const wc = snap.centroid;
    for (const [id, init] of snap.atoms) {
      const a = S.atoms.find((x) => x.id === id);
      if (!a) continue;
      const v = new THREE.Vector3(
        init.x - wc.x, init.y - wc.y, init.z - wc.z,
      ).applyQuaternion(qDelta);
      a.x = v.x + wc.x;
      a.y = v.y + wc.y;
      a.z = v.z + wc.z;
    }
    const pp = snap.pivotPos;
    for (const [id, initP] of snap.meshes) {
      const m = meshForAtom(id);
      if (!m) continue;
      const v = new THREE.Vector3(
        initP.x - pp.x, initP.y - pp.y, initP.z - pp.z,
      ).applyQuaternion(qDelta);
      m.position.set(v.x + pp.x, v.y + pp.y, v.z + pp.z);
    }
  } else if (mode === "scale") {
    const s = pivot.scale;
    const wc = snap.centroid;
    for (const [id, init] of snap.atoms) {
      const a = S.atoms.find((x) => x.id === id);
      if (!a) continue;
      a.x = wc.x + (init.x - wc.x) * s.x;
      a.y = wc.y + (init.y - wc.y) * s.y;
      a.z = wc.z + (init.z - wc.z) * s.z;
    }
    const pp = snap.pivotPos;
    for (const [id, initP] of snap.meshes) {
      const m = meshForAtom(id);
      if (!m) continue;
      m.position.set(
        pp.x + (initP.x - pp.x) * s.x,
        pp.y + (initP.y - pp.y) * s.y,
        pp.z + (initP.z - pp.z) * s.z,
      );
    }
  }

  updateAtomVisuals();
}

/* ── public API ─────────────────────────────────────────────────────────── */

export function initGizmo() {
  if (!window.THREE || !THREE.TransformControls) {
    console.warn("THREE.TransformControls not loaded – gizmo disabled");
    return;
  }

  const canvas = $("#struct-canvas");
  pivot = new THREE.Object3D();
  S.scene.add(pivot);

  gizmo = new THREE.TransformControls(S.camera, canvas);
  gizmo.attach(pivot);
  gizmo.setSize(0.75);
  gizmo.visible = false;
  gizmo.enabled = false;
  S.scene.add(gizmo);

  gizmo.addEventListener("dragging-changed", (ev) => {
    setOrbitEnabled(!ev.value);
    if (ev.value) {
      takeSnapshot();
    } else {
      snap = null;
      S.gizmoJustDragged = true;
      rebuildScene();
      updateGizmo();
      updateStatusBar();
    }
  });

  gizmo.addEventListener("objectChange", () => {
    if (!snap) return;
    applyTransform();
  });
}

/**
 * Reposition (or hide) the gizmo to match the current mode & selection.
 * Call this whenever the selection or mode changes.
 */
export function updateGizmo() {
  if (!gizmo) return;

  const isTransform = S.mode === "translate" || S.mode === "rotate" || S.mode === "scale";
  if (!isTransform || S.selected.size === 0) {
    gizmo.visible = false;
    gizmo.enabled = false;
    return;
  }

  const allC = computeCentroid();
  const sc = selCentroid();
  pivot.position.set(sc.x - allC.x, sc.y - allC.y, sc.z - allC.z);
  pivot.quaternion.identity();
  pivot.scale.set(1, 1, 1);

  gizmo.setMode(S.mode);
  gizmo.visible = true;
  gizmo.enabled = true;
}

/**
 * Fine-adjust selected atoms via keyboard (arrows / A D).
 * @param {"up"|"down"|"left"|"right"} direction
 */
export function nudgeTransform(direction) {
  if (S.selected.size === 0) return;

  const TRANSLATE_STEP = 0.1;           // Angstroms
  const ROTATE_STEP = Math.PI / 180;    // 1 degree
  const SCALE_STEP = 0.02;              // 2 %

  const sel = selectedAtoms();
  if (!sel.length) return;

  // Camera-relative screen axes
  const camDir = new THREE.Vector3();
  S.camera.getWorldDirection(camDir);
  const camUp = new THREE.Vector3().copy(S.camera.up).normalize();
  const camRight = new THREE.Vector3().crossVectors(camDir, camUp).normalize();
  const screenUp = new THREE.Vector3().crossVectors(camRight, camDir).normalize();

  if (S.mode === "translate") {
    const delta = new THREE.Vector3();
    if (direction === "up")         delta.copy(screenUp).multiplyScalar(TRANSLATE_STEP);
    else if (direction === "down")  delta.copy(screenUp).multiplyScalar(-TRANSLATE_STEP);
    else if (direction === "left")  delta.copy(camRight).multiplyScalar(-TRANSLATE_STEP);
    else if (direction === "right") delta.copy(camRight).multiplyScalar(TRANSLATE_STEP);
    for (const a of sel) { a.x += delta.x; a.y += delta.y; a.z += delta.z; }

  } else if (S.mode === "rotate") {
    const sc = selCentroid();
    const origin = new THREE.Vector3(sc.x, sc.y, sc.z);
    let axis, angle;
    if (direction === "up" || direction === "down") {
      axis = camRight;
      angle = direction === "up" ? ROTATE_STEP : -ROTATE_STEP;
    } else {
      axis = screenUp;
      angle = direction === "right" ? ROTATE_STEP : -ROTATE_STEP;
    }
    const q = new THREE.Quaternion().setFromAxisAngle(axis, angle);
    for (const a of sel) {
      const v = new THREE.Vector3(a.x, a.y, a.z).sub(origin).applyQuaternion(q).add(origin);
      a.x = v.x; a.y = v.y; a.z = v.z;
    }

  } else if (S.mode === "scale") {
    const sc = selCentroid();
    const factor = (direction === "up" || direction === "right") ? 1 + SCALE_STEP : 1 - SCALE_STEP;
    for (const a of sel) {
      a.x = sc.x + (a.x - sc.x) * factor;
      a.y = sc.y + (a.y - sc.y) * factor;
      a.z = sc.z + (a.z - sc.z) * factor;
    }
  }

  rebuildScene();
  updateGizmo();
  updateStatusBar();
}

/** True when the pointer is hovering over a gizmo handle. */
export function isGizmoActive() {
  return gizmo ? gizmo.axis !== null : false;
}

/** True when the user is actively dragging the gizmo. */
export function isGizmoDragging() {
  return gizmo ? gizmo.dragging : false;
}
