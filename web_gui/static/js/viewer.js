/**
 * viewer.js – Three.js scene setup, rendering loop, and camera management.
 */

import { S, ELEM_COLOR, ELEM_RADIUS, BOND_TOLERANCE } from "./state.js";
import { $ } from "./utils.js";

const MAX_PIXEL_RATIO = 1.5;
const BOND_AUTO_DISABLE_ATOMS = 900;
const MAX_BOND_MESHES = 30000;
const WORLD_UP = Object.freeze({ x: 0, y: 0, z: 1 });
const INITIAL_VIEW_DIRECTION_XY = Object.freeze({ x: 1, y: 1, z: 0 });
const CAMERA_FIT_MARGIN = 1.2;
const CAMERA_MIN_RADIUS = 3;
const CAMERA_NEAR_FACTOR = 0.001;
const CAMERA_NEAR_MIN = 0.0005;
const CAMERA_FAR_FACTOR = 220;
const CAMERA_FAR_MIN = 50;

let raycaster = null;
let rayNdc = null;
let atomIndexById = new Map();
let lastSelectedIds = new Set();
let lastHoveredId = null;
let visualsNeedFullRefresh = true;

export function elemColor(sym) {
  return ELEM_COLOR[sym] || ELEM_COLOR.default;
}

export function elemRadius(sym) {
  return (ELEM_RADIUS[sym] || ELEM_RADIUS.default) * 0.55;
}

export function computeCentroid() {
  if (!S.atoms.length) return { x: 0, y: 0, z: 0 };
  let cx = 0;
  let cy = 0;
  let cz = 0;
  for (const a of S.atoms) {
    cx += a.x;
    cy += a.y;
    cz += a.z;
  }
  return { x: cx / S.atoms.length, y: cy / S.atoms.length, z: cz / S.atoms.length };
}

export function syncMeshPositionsToAtoms() {
  const c = computeCentroid();
  for (let i = 0; i < S.atomMeshes.length; i += 1) {
    const atom = S.atoms[i];
    if (!atom) continue;
    S.atomMeshes[i].position.set(atom.x - c.x, atom.y - c.y, atom.z - c.z);
  }
}

export function initViewer() {
  const canvas = $("#struct-canvas");
  const wrap = $("#viewer-wrap");

  if (!window.THREE) {
    throw new Error("Three.js failed to load.");
  }
  if (!THREE.OrbitControls) {
    throw new Error("OrbitControls failed to load.");
  }

  S.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  S.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, MAX_PIXEL_RATIO));
  S.renderer.setClearColor(0x181825, 1);

  S.scene = new THREE.Scene();

  S.camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000);
  S.camera.up.set(WORLD_UP.x, WORLD_UP.y, WORLD_UP.z);
  S.camera.position.set(
    INITIAL_VIEW_DIRECTION_XY.x * 20,
    INITIAL_VIEW_DIRECTION_XY.y * 20,
    INITIAL_VIEW_DIRECTION_XY.z * 20,
  );

  S.controls = new THREE.OrbitControls(S.camera, canvas);
  S.controls.enableDamping = true;
  S.controls.dampingFactor = 0.1;
  S.controls.screenSpacePanning = true;
  S.controls.mouseButtons = {
    LEFT: THREE.MOUSE.ROTATE,
    MIDDLE: THREE.MOUSE.PAN,
    RIGHT: THREE.MOUSE.PAN,
  };

  const amb = new THREE.AmbientLight(0xffffff, 0.45);
  const dir = new THREE.DirectionalLight(0xffffff, 0.8);
  dir.position.set(5, 10, 8);
  const fill = new THREE.DirectionalLight(0xffffff, 0.3);
  fill.position.set(-5, -3, -6);
  S.scene.add(amb, dir, fill);

  raycaster = new THREE.Raycaster();
  rayNdc = new THREE.Vector2();

  resizeRenderer();
  new ResizeObserver(resizeRenderer).observe(wrap);
  loop();
}

function resizeRenderer() {
  const wrap = $("#viewer-wrap");
  const w = wrap.clientWidth;
  const h = wrap.clientHeight;
  S.renderer.setSize(w, h, false);
  S.camera.aspect = w / h;
  S.camera.updateProjectionMatrix();
}

function loop() {
  S.rafId = requestAnimationFrame(loop);
  S.controls.update();
  updateCameraClippingPlanes();
  S.renderer.render(S.scene, S.camera);
}

function updateCameraClippingPlanes() {
  if (!S.camera || !S.controls) return;
  const dist = S.camera.position.distanceTo(S.controls.target);
  if (!Number.isFinite(dist) || dist <= 0) return;

  const near = Math.max(CAMERA_NEAR_MIN, dist * CAMERA_NEAR_FACTOR);
  const far = Math.max(CAMERA_FAR_MIN, dist * CAMERA_FAR_FACTOR);
  if (Math.abs(S.camera.near - near) < 1e-6 && Math.abs(S.camera.far - far) < 1e-4) return;

  S.camera.near = near;
  S.camera.far = far;
  S.camera.updateProjectionMatrix();
}

export function rebuildScene() {
  for (const m of S.atomMeshes) S.scene.remove(m);
  for (const m of S.bondMeshes) S.scene.remove(m);
  if (S.cellLines) {
    S.scene.remove(S.cellLines);
    S.cellLines = null;
  }
  S.atomMeshes = [];
  S.bondMeshes = [];
  atomIndexById = new Map();
  visualsNeedFullRefresh = true;
  lastSelectedIds = new Set();
  lastHoveredId = null;

  if (!S.atoms.length) return;

  const c = computeCentroid();
  const geoCache = {};
  const atomCount = S.atoms.length;
  const sphereWidthSeg = atomCount > 1800 ? 8 : atomCount > 800 ? 12 : 20;
  const sphereHeightSeg = atomCount > 1800 ? 6 : atomCount > 800 ? 10 : 16;

  for (const atom of S.atoms) {
    const r = elemRadius(atom.symbol);
    if (!geoCache[atom.symbol]) geoCache[atom.symbol] = new THREE.SphereGeometry(r, sphereWidthSeg, sphereHeightSeg);
    const baseColor = new THREE.Color(elemColor(atom.symbol));
    const mat = new THREE.MeshPhongMaterial({
      color: baseColor,
      shininess: 80,
      emissive: 0x000000,
    });
    const mesh = new THREE.Mesh(geoCache[atom.symbol], mat);
    mesh.position.set(atom.x - c.x, atom.y - c.y, atom.z - c.z);
    mesh.userData = { atomId: atom.id, baseColor };
    S.scene.add(mesh);
    atomIndexById.set(atom.id, S.atomMeshes.length);
    S.atomMeshes.push(mesh);
  }

  if (S.atoms.length <= BOND_AUTO_DISABLE_ATOMS) {
    buildBonds(c);
  } else {
    console.info(`Skipping bonds for large structure (${S.atoms.length} atoms) to keep interaction responsive.`);
  }
  if (S.cell) buildCell(c);
  updateAtomVisuals(true);
}


function buildBonds(c) {
  const n = S.atoms.length;
  const cylGeo = new THREE.CylinderGeometry(0.08, 0.08, 1, 8, 1);
  const up = new THREE.Vector3(0, 1, 0);

  // Extract cell vectors
  const [v0, v1, v2] = S.cell;

  const radii = S.atoms.map(a => ELEM_RADIUS[a.symbol] || ELEM_RADIUS.default);
  const atomColors = S.atoms.map(a => new THREE.Color(elemColor(a.symbol)));

  // Determine search ranges for neighboring cells (-1 to 1 for periodic axes)
  const nxRange = S.pbc[0] ? [-1, 0, 1] : [0];
  const nyRange = S.pbc[1] ? [-1, 0, 1] : [0];
  const nzRange = S.pbc[2] ? [-1, 0, 1] : [0];

  // 1. Start j from i to include potential self-bonds across PBC
  for (let i = 0; i < n; i++) {
    for (let j = i; j < n; j++) {
      const a = S.atoms[i];
      const b = S.atoms[j];

      // 2. Explicitly search adjacent cells instead of using Minimum Image Convention
      for (let nx of nxRange) {
        for (let ny of nyRange) {
          for (let nz of nzRange) {

            // 3. Prevent double-counting self-bonds and skip the origin cell (distance 0)
            if (i === j) {
              if (nx < 0) continue;
              if (nx === 0 && ny < 0) continue;
              if (nx === 0 && ny === 0 && nz <= 0) continue; 
            }

            // Apply periodic offset based on cell vectors
            const offsetX = nx * v0[0] + ny * v1[0] + nz * v2[0];
            const offsetY = nx * v0[1] + ny * v1[1] + nz * v2[1];
            const offsetZ = nx * v0[2] + ny * v1[2] + nz * v2[2];

            const dx = (b.x + offsetX) - a.x;
            const dy = (b.y + offsetY) - a.y;
            const dz = (b.z + offsetZ) - a.z;

            const dist2 = dx * dx + dy * dy + dz * dz;
            const cutoff = (radii[i] + radii[j]) * BOND_TOLERANCE;

            // dist2 > 0.1 ensures we still ignore overlapping/duplicate atoms
            if (dist2 > 0.1 && dist2 < cutoff * cutoff) {
              const dist = Math.sqrt(dist2);
              const dir = new THREE.Vector3(dx, dy, dz).normalize();
              const halfLen = dist / 2;

              // Half-bond from A towards image of B
              addHalfBond(a, dir, halfLen, atomColors[i], i, j);
              
              // Half-bond from B towards image of A (Negative direction)
              const invDir = dir.clone().negate();
              addHalfBond(b, invDir, halfLen, atomColors[j], i, j);
            }
          }
        }
      }
    }
  }

  function addHalfBond(atom, direction, length, color, idxA, idxB) {
    const mesh = new THREE.Mesh(cylGeo, new THREE.MeshPhongMaterial({color}));
    const pos = new THREE.Vector3(atom.x, atom.y, atom.z)
      .addScaledVector(direction, length / 2)
      .sub(c); // Apply camera/center offset
    
    mesh.position.copy(pos);
    mesh.scale.set(1, length, 1);
    mesh.quaternion.setFromUnitVectors(up, direction);
    S.scene.add(mesh);
    S.bondMeshes.push(mesh);
  }
}



function buildCell(c) {
  const [a, b, cc] = S.cell;
  const v = (ix, iy, iz) => new THREE.Vector3(
    (ix * a[0]) + (iy * b[0]) + (iz * cc[0]) - c.x,
    (ix * a[1]) + (iy * b[1]) + (iz * cc[1]) - c.y,
    (ix * a[2]) + (iy * b[2]) + (iz * cc[2]) - c.z,
  );

  const corners = [
    v(0, 0, 0), v(1, 0, 0), v(1, 1, 0), v(0, 1, 0),
    v(0, 0, 1), v(1, 0, 1), v(1, 1, 1), v(0, 1, 1),
  ];

  const edges = [
    [0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6],
    [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7],
  ];

  const pts = [];
  for (const [i, j] of edges) pts.push(corners[i], corners[j]);

  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = new THREE.LineBasicMaterial({ color: 0x4477aa, transparent: true, opacity: 0.7 });
  S.cellLines = new THREE.LineSegments(geo, mat);
  S.scene.add(S.cellLines);
}

function applyAtomVisualById(id) {
  const idx = atomIndexById.get(id);
  if (idx === undefined) return;
  const mesh = S.atomMeshes[idx];
  if (!mesh) return;
  const atom = S.atoms[idx];
  const inSelectedLayer = Boolean(atom && S.selectedLayerIds.has(atom.layerId));

  const base = mesh.userData.baseColor;
  if (!inSelectedLayer) {
    mesh.material.color.copy(base).lerp(new THREE.Color(0x555555), 0.6);
    mesh.material.emissive.set(0x000000);
    mesh.scale.setScalar(1);
    return;
  }

  if (S.selected.has(id)) {
    mesh.material.color.set(0xffdd44);
    mesh.material.emissive.set(0x443300);
    mesh.scale.setScalar(1.15);
    return;
  }

  if (S.hovered === id) {
    mesh.material.color.copy(base).lerp(new THREE.Color(0xffffff), 0.4);
    mesh.material.emissive.set(0x222222);
    mesh.scale.setScalar(1.1);
    return;
  }

  mesh.material.color.copy(base);
  mesh.material.emissive.set(0x000000);
  mesh.scale.setScalar(1);
}

function areSetsEqual(a, b) {
  if (a.size !== b.size) return false;
  for (const v of a) {
    if (!b.has(v)) return false;
  }
  return true;
}

export function updateAtomVisuals(forceFull = false) {
  if (forceFull || visualsNeedFullRefresh || !areSetsEqual(lastSelectedIds, S.selected)) {
    if (forceFull || visualsNeedFullRefresh || S.atomMeshes.length <= 300) {
      for (const atom of S.atoms) applyAtomVisualById(atom.id);
    } else {
      const dirty = new Set();
      for (const id of lastSelectedIds) if (!S.selected.has(id)) dirty.add(id);
      for (const id of S.selected) if (!lastSelectedIds.has(id)) dirty.add(id);
      if (lastHoveredId !== null && lastHoveredId !== S.hovered) dirty.add(lastHoveredId);
      if (S.hovered !== null && S.hovered !== lastHoveredId) dirty.add(S.hovered);
      for (const id of dirty) applyAtomVisualById(id);
    }
  } else if (lastHoveredId !== S.hovered) {
    if (lastHoveredId !== null) applyAtomVisualById(lastHoveredId);
    if (S.hovered !== null) applyAtomVisualById(S.hovered);
  }

  lastSelectedIds = new Set(S.selected);
  lastHoveredId = S.hovered;
  visualsNeedFullRefresh = false;
  updateAtomInfoPanel();
}

function updateAtomInfoPanel() {
  const info = $("#atom-info");
  if (S.selected.size === 0 && S.hovered === null) {
    info.style.display = "none";
    return;
  }

  info.style.display = "block";
  if (S.selected.size > 1) {
    $("#ai-title").textContent = "Selection";
    $("#ai-sym").textContent = "-";
    $("#ai-x").textContent = "-";
    $("#ai-y").textContent = "-";
    $("#ai-z").textContent = "-";
    $("#ai-count").style.display = "block";
    $("#ai-count").textContent = `${S.selected.size} atoms selected`;
    return;
  }

  $("#ai-count").style.display = "none";
  const id = S.selected.size === 1 ? [...S.selected][0] : S.hovered;
  if (id === null) {
    info.style.display = "none";
    return;
  }

  const idx = atomIndexById.get(id);
  const a = idx === undefined ? null : S.atoms[idx];
  if (!a) {
    info.style.display = "none";
    return;
  }

  $("#ai-title").textContent = `Atom #${a.id}`;
  $("#ai-sym").textContent = a.symbol;
  $("#ai-x").textContent = `${a.x.toFixed(4)} Å`;
  $("#ai-y").textContent = `${a.y.toFixed(4)} Å`;
  $("#ai-z").textContent = `${a.z.toFixed(4)} Å`;
}

function computeFitRadius() {
  let fitRadius = 0;
  for (let i = 0; i < S.atomMeshes.length; i += 1) {
    const mesh = S.atomMeshes[i];
    const atom = S.atoms[i];
    if (!mesh || !atom) continue;
    fitRadius = Math.max(fitRadius, mesh.position.length() + elemRadius(atom.symbol));
  }
  return Math.max(fitRadius, CAMERA_MIN_RADIUS);
}

function setCameraViewDirection(viewDir) {
  if (!S.atoms.length) return;

  const fitRadius = computeFitRadius();
  const vFov = THREE.MathUtils.degToRad(S.camera.fov);
  const hFov = 2 * Math.atan(Math.tan(vFov / 2) * Math.max(S.camera.aspect, 1e-3));
  const limitingHalfFov = Math.min(vFov, hFov) / 2;
  const camDistance = (fitRadius * CAMERA_FIT_MARGIN) / Math.sin(limitingHalfFov);

  S.camera.up.set(WORLD_UP.x, WORLD_UP.y, WORLD_UP.z);
  S.camera.position.copy(viewDir.clone().normalize().multiplyScalar(camDistance));
  S.controls.target.set(0, 0, 0);
  updateCameraClippingPlanes();
  S.controls.update();
}

export function setViewDirection(axis) {
  if (!S.atoms.length) return;

  const map = {
    x: new THREE.Vector3(1, 0, 0),
    y: new THREE.Vector3(0, 1, 0),
    z: new THREE.Vector3(0, 0, 1),
  };
  const viewDir = map[axis] || map.x;
  setCameraViewDirection(viewDir);
}

export function resetCamera() {
  if (!S.atoms.length) return;

  const viewDir = new THREE.Vector3(
    0, //INITIAL_VIEW_DIRECTION_XY.x,
    INITIAL_VIEW_DIRECTION_XY.y,
    INITIAL_VIEW_DIRECTION_XY.z,
  ).normalize();
  setCameraViewDirection(viewDir);
}

export function raycastAtoms(event) {
  if (!S.atomMeshes.length) return null;
  if (!raycaster || !rayNdc) {
    raycaster = new THREE.Raycaster();
    rayNdc = new THREE.Vector2();
  }
  const wrap = $("#viewer-wrap");
  const rect = wrap.getBoundingClientRect();
  const x = (((event.clientX - rect.left) / rect.width) * 2) - 1;
  const y = -(((event.clientY - rect.top) / rect.height) * 2) + 1;
  rayNdc.set(x, y);
  raycaster.setFromCamera(rayNdc, S.camera);
  const hits = raycaster.intersectObjects(S.atomMeshes);
  return hits.length > 0 ? hits[0] : null;
}

export function atomIdFromMesh(mesh) {
  return mesh.userData.atomId;
}

export function setOrbitEnabled(v) {
  S.controls.enabled = v;
}
