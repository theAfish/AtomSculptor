/**
 * viewer.js – Three.js scene setup, rendering loop, and camera management.
 */

import { S, ELEM_COLOR, ELEM_RADIUS, BOND_MAX_DIST } from "./state.js";
import { $ } from "./utils.js";

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
  S.renderer.setPixelRatio(window.devicePixelRatio);
  S.renderer.setClearColor(0x181825, 1);

  S.scene = new THREE.Scene();

  S.camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000);
  S.camera.position.set(0, 0, 20);

  S.controls = new THREE.OrbitControls(S.camera, canvas);
  S.controls.enableDamping = true;
  S.controls.dampingFactor = 0.1;
  S.controls.screenSpacePanning = true;

  const amb = new THREE.AmbientLight(0xffffff, 0.45);
  const dir = new THREE.DirectionalLight(0xffffff, 0.8);
  dir.position.set(5, 10, 8);
  const fill = new THREE.DirectionalLight(0xffffff, 0.3);
  fill.position.set(-5, -3, -6);
  S.scene.add(amb, dir, fill);

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
  S.renderer.render(S.scene, S.camera);
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

  if (!S.atoms.length) return;

  const c = computeCentroid();
  const geoCache = {};

  for (const atom of S.atoms) {
    const r = elemRadius(atom.symbol);
    if (!geoCache[atom.symbol]) geoCache[atom.symbol] = new THREE.SphereGeometry(r, 20, 16);
    const mat = new THREE.MeshPhongMaterial({
      color: new THREE.Color(elemColor(atom.symbol)),
      shininess: 80,
    });
    const mesh = new THREE.Mesh(geoCache[atom.symbol], mat);
    mesh.position.set(atom.x - c.x, atom.y - c.y, atom.z - c.z);
    mesh.userData = { atomId: atom.id };
    S.scene.add(mesh);
    S.atomMeshes.push(mesh);
  }

  buildBonds(c);
  if (S.cell) buildCell(c);
  updateAtomVisuals();
}

function buildBonds(c) {
  const n = S.atoms.length;
  const cylGeo = new THREE.CylinderGeometry(0.08, 0.08, 1, 8, 1);
  const bondMat = new THREE.MeshPhongMaterial({ color: 0x888888 });

  for (let i = 0; i < n; i += 1) {
    for (let j = i + 1; j < n; j += 1) {
      const a = S.atoms[i];
      const b = S.atoms[j];
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const dz = a.z - b.z;
      const dist = Math.sqrt((dx * dx) + (dy * dy) + (dz * dz));
      if (dist > BOND_MAX_DIST) continue;

      const mesh = new THREE.Mesh(cylGeo, bondMat.clone());
      mesh.position.set((a.x + b.x) / 2 - c.x, (a.y + b.y) / 2 - c.y, (a.z + b.z) / 2 - c.z);
      mesh.scale.set(1, dist, 1);
      const dir = new THREE.Vector3(b.x - a.x, b.y - a.y, b.z - a.z).normalize();
      mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
      mesh.userData = { isBond: true, atomA: i, atomB: j };
      S.scene.add(mesh);
      S.bondMeshes.push(mesh);
    }
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

export function updateAtomVisuals() {
  for (let i = 0; i < S.atomMeshes.length; i += 1) {
    const mesh = S.atomMeshes[i];
    const atom = S.atoms[i];
    if (!atom) continue;

    const id = atom.id;
    const sym = atom.symbol;
    const base = new THREE.Color(elemColor(sym));

    if (S.selected.has(id)) {
      mesh.material.color.set(0xffdd44);
      mesh.material.emissive.set(0x443300);
      mesh.scale.setScalar(1.15);
    } else if (S.hovered === id) {
      mesh.material.color.copy(base).lerp(new THREE.Color(0xffffff), 0.4);
      mesh.material.emissive.set(0x222222);
      mesh.scale.setScalar(1.1);
    } else {
      mesh.material.color.copy(base);
      mesh.material.emissive.set(0x000000);
      mesh.scale.setScalar(1);
    }
  }
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

  const a = S.atoms.find((atom) => atom.id === id);
  if (!a) {
    info.style.display = "none";
    return;
  }

  $("#ai-title").textContent = `Atom #${a.id}`;
  $("#ai-sym").textContent = a.symbol;
  $("#ai-x").textContent = `${a.x.toFixed(4)} A`;
  $("#ai-y").textContent = `${a.y.toFixed(4)} A`;
  $("#ai-z").textContent = `${a.z.toFixed(4)} A`;
}

export function resetCamera() {
  if (!S.atoms.length) return;
  let maxR = 0;
  for (const m of S.atomMeshes) maxR = Math.max(maxR, m.position.length());
  maxR = Math.max(maxR, 3);
  S.camera.position.set(0, 0, maxR * 2.5);
  S.camera.near = maxR * 0.001;
  S.camera.far = maxR * 100;
  S.camera.updateProjectionMatrix();
  S.controls.target.set(0, 0, 0);
  S.controls.update();
}

export function raycastAtoms(event) {
  const wrap = $("#viewer-wrap");
  const rect = wrap.getBoundingClientRect();
  const x = (((event.clientX - rect.left) / rect.width) * 2) - 1;
  const y = -(((event.clientY - rect.top) / rect.height) * 2) + 1;
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(new THREE.Vector2(x, y), S.camera);
  const hits = raycaster.intersectObjects(S.atomMeshes);
  return hits.length > 0 ? hits[0] : null;
}

export function atomIdFromMesh(mesh) {
  return mesh.userData.atomId;
}

export function setOrbitEnabled(v) {
  S.controls.enabled = v;
}
