const S = {
  ws: null,
  cy: null,
  connected: false,
  processing: false,
  todoData: { tasks: [], finished: true },

  renderer: null,
  scene: null,
  camera: null,
  controls: null,
  rafId: null,

  structPath: null,
  atoms: [],
  cell: null,
  pbc: [false, false, false],

  atomMeshes: [],
  bondMeshes: [],
  cellLines: null,

  mode: "orbit",
  selected: new Set(),
  hovered: null,
  addElement: "H",

  dragAtomId: null,
  dragPlane: null,

  boxStart: null,

  rotateActive: false,
  rotateLast: null,
};

const STRUCTURE_EXTS = new Set(["cif", "xyz", "vasp", "poscar", "extxyz", "pdb", "sdf", "mol2"]);
const STRUCTURE_PREFIXES = ["poscar", "contcar"];
const STATUS_COLOR = {
  pending: "#858585",
  ready: "#4fc3f7",
  in_progress: "#ffb74d",
  done: "#81c784",
  blocked: "#e57373",
  deprecated: "#616161",
};

const ELEM_COLOR = {
  H: "#ffffff", C: "#404040", N: "#3050f8", O: "#ff0d0d", F: "#90e050",
  P: "#ff8000", S: "#ffff30", Cl: "#1ff01f", Br: "#a62929", I: "#940094",
  Li: "#cc80ff", Na: "#ab5cf2", K: "#8f40d4", Ca: "#3dff00", Mg: "#8aff00",
  Al: "#bfa6a6", Si: "#f0c8a0", Fe: "#e06633", Cu: "#c88033", Zn: "#7d80b0",
  Ag: "#c0c0c0", Au: "#ffd123", Pt: "#d0d0e0", Pd: "#006985", Ti: "#bfc2c7",
  Co: "#f090a0", Ni: "#50d050", Mn: "#9c7ac7", Cr: "#8a99c7",
  He: "#d9ffff", Ne: "#b3e3f5", Ar: "#80d1e3", Xe: "#429eb0", Kr: "#5cb8d1",
  default: "#ff1493",
};

const ELEM_RADIUS = {
  H: 0.31, C: 0.77, N: 0.75, O: 0.73, F: 0.71,
  P: 1.06, S: 1.02, Cl: 0.99, Br: 1.14, I: 1.33,
  Li: 1.28, Na: 1.66, K: 2.03, Ca: 1.74, Mg: 1.41,
  Al: 1.21, Si: 1.17, Fe: 1.25, Cu: 1.28, Zn: 1.22,
  Ag: 1.44, Au: 1.44, Pt: 1.39, Pd: 1.31, Ti: 1.47,
  Co: 1.25, Ni: 1.24, Mn: 1.29, Cr: 1.29,
  He: 0.28, Ne: 0.58, Ar: 1.06, Xe: 1.31, Kr: 1.16,
  default: 1.2,
};

const BOND_MAX_DIST = 2.5;

const MODE_HINT = {
  orbit: "Drag to rotate · Scroll to zoom · Right-drag to pan",
  select: "Click atom to select · Shift/Ctrl for multi · Click empty to deselect",
  box: "Drag box to select · Shift/Ctrl to add to selection",
  drag: "Click-drag atom to reposition",
  rotate: "Drag to rotate selected atoms",
  add: "Click atom surface to add a neighbor",
  delete: "Click atom to delete",
};

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function truncate(s, n) {
  return s.length > n ? `${s.slice(0, n)}...` : s;
}

function fmtSize(b) {
  if (b < 1024) return `${b}B`;
  if (b < 1048576) return `${(b / 1024).toFixed(1)}K`;
  return `${(b / 1048576).toFixed(1)}M`;
}

function renderMd(text) {
  try {
    return marked.parse(text, { breaks: true });
  } catch (_err) {
    return `<p>${esc(text).replace(/\n/g, "<br>")}</p>`;
  }
}

function jsonPretty(obj) {
  try {
    return JSON.stringify(obj, null, 2);
  } catch (_err) {
    return String(obj);
  }
}

function elemColor(sym) {
  return ELEM_COLOR[sym] || ELEM_COLOR.default;
}

function elemRadius(sym) {
  return (ELEM_RADIUS[sym] || ELEM_RADIUS.default) * 0.55;
}

function computeCentroid() {
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

function syncMeshPositionsToAtoms() {
  const c = computeCentroid();
  for (let i = 0; i < S.atomMeshes.length; i += 1) {
    const atom = S.atoms[i];
    if (!atom) continue;
    S.atomMeshes[i].position.set(atom.x - c.x, atom.y - c.y, atom.z - c.z);
  }
}

let reconnectTimer = null;

function connect() {
  if (S.ws && S.ws.readyState <= 1) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  S.ws = new WebSocket(`${proto}://${location.host}/ws`);

  S.ws.onopen = () => {
    S.connected = true;
    $("#ws-dot").classList.add("ok");
    $("#ws-label").textContent = "Connected";
  };

  S.ws.onclose = () => {
    S.connected = false;
    $("#ws-dot").classList.remove("ok");
    $("#ws-label").textContent = "Disconnected";
    if (!reconnectTimer) {
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connect();
      }, 2000);
    }
  };

  S.ws.onerror = () => {};

  S.ws.onmessage = (e) => {
    try {
      handleMsg(JSON.parse(e.data));
    } catch (err) {
      console.error("ws msg error", err);
    }
  };
}

function wsSend(obj) {
  if (S.ws && S.ws.readyState === 1) S.ws.send(JSON.stringify(obj));
}

function handleMsg(m) {
  switch (m.type) {
    case "user_message": appendUser(m.text); break;
    case "agent_message": appendAgent(m.author, m.text); break;
    case "tool_call": appendToolCall(m.author, m.tool, m.args); break;
    case "tool_result": appendToolResult(m.author, m.tool, m.result); break;
    case "todo_flow_update": updateTodo(m.data); break;
    case "files_update": renderFiles(m.data); break;
    case "done": setProcessing(false); break;
    case "error": appendError(m.text, m.traceback); setProcessing(false); break;
    default:
      break;
  }
}

function initGraph() {
  S.cy = cytoscape({
    container: $("#todo-graph"),
    elements: [],
    style: [
      {
        selector: "node",
        style: {
          label: "data(label)",
          "text-valign": "bottom",
          "text-halign": "center",
          "text-margin-y": 8,
          "text-wrap": "wrap",
          "text-max-width": "100px",
          "font-size": "10px",
          color: "#fff",
          "background-color": "data(color)",
          width: 18,
          height: 18,
          "border-width": 2,
          "border-color": "#444",
          shape: "ellipse",
        },
      },
      { selector: "node[status='in_progress']", style: { "border-color": "#ffb74d", "border-width": 3 } },
      { selector: "node[status='done']", style: { "border-color": "#81c784", "border-width": 2 } },
      {
        selector: "edge",
        style: {
          width: 2,
          "line-color": "#555",
          "target-arrow-color": "#888",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          "arrow-scale": 0.8,
        },
      },
    ],
    layout: { name: "grid" },
    userZoomingEnabled: true,
    userPanningEnabled: true,
    boxSelectionEnabled: false,
    autoungrabify: true,
  });

  S.cy.on("mouseover", "node", (e) => showTooltip(e.renderedPosition, e.target.data()));
  S.cy.on("mouseout", "node", () => hideTooltip());
  S.cy.on("drag", "node", () => hideTooltip());
}

function updateTodo(data) {
  S.todoData = data;
  const tasks = data.tasks || [];
  const empty = $("#todo-empty");
  const graph = $("#todo-graph");

  if (!tasks.length) {
    empty.style.display = "block";
    graph.style.display = "none";
    S.cy.elements().remove();
    updateSessionInfo(data);
    return;
  }

  empty.style.display = "none";
  graph.style.display = "block";

  const elems = [];
  for (const t of tasks) {
    elems.push({
      data: {
        id: `t${t.id}`,
        label: `#${t.id}\n${truncate(t.description, 28)}`,
        color: STATUS_COLOR[t.status] || "#858585",
        status: t.status,
        taskId: t.id,
        description: t.description,
        result: t.result,
        dependencies: t.dependencies,
      },
    });
  }

  const taskIds = new Set(tasks.map((t) => t.id));
  for (const t of tasks) {
    for (const dep of (t.dependencies || [])) {
      if (taskIds.has(dep)) {
        elems.push({ data: { id: `e${dep}_${t.id}`, source: `t${dep}`, target: `t${t.id}` } });
      }
    }
  }

  S.cy.elements().remove();
  S.cy.add(elems);
  S.cy.layout({
    name: "dagre",
    rankDir: "TB",
    ranker: "tight-tree",
    nodeSep: 24,
    rankSep: 58,
    edgeSep: 10,
    padding: 20,
  }).run();

  updateSessionInfo(data);
}

function updateSessionInfo(data) {
  const tasks = data.tasks || [];
  const done = tasks.filter((t) => t.status === "done").length;
  const active = tasks.find((t) => t.status === "in_progress");

  let html = `<span>Tasks: ${done}/${tasks.length}</span>`;
  if (data.finished && tasks.length > 0) html += "<span style='color:var(--s-done)'>All done</span>";
  if (active) html += `<span style='color:var(--s-progress)'>Active #${active.id}</span>`;
  $("#session-info").innerHTML = html;
}

function showTooltip(pos, d) {
  const tt = $("#tooltip");
  const statusBg = STATUS_COLOR[d.status] || "#858585";
  let html = `<div class='tt-title'>Task #${d.taskId}</div>`;
  html += `<span class='tt-status' style='background:${statusBg}'>${d.status}</span>`;
  html += `<div class='tt-desc'>${esc(d.description)}</div>`;
  if (d.dependencies && d.dependencies.length) {
    html += `<div class='tt-deps'>Depends on: ${d.dependencies.map((i) => `#${i}`).join(", ")}</div>`;
  }
  if (d.result) {
    html += `<div class='tt-result'>${esc(truncate(String(d.result), 200))}</div>`;
  }
  tt.innerHTML = html;
  tt.style.display = "block";

  const rect = $("#panel-todo").getBoundingClientRect();
  let x = rect.left + pos.x + 12;
  let y = rect.top + pos.y + 50;

  if (x + 330 > window.innerWidth) x = window.innerWidth - 340;
  if (y + 200 > window.innerHeight) y -= 220;

  tt.style.left = `${x}px`;
  tt.style.top = `${y}px`;
}

function hideTooltip() {
  $("#tooltip").style.display = "none";
}

const chatEl = $("#chat-messages");
const scrollEl = $("#chat-scroll");

function scrollBottom() {
  requestAnimationFrame(() => {
    scrollEl.scrollTop = scrollEl.scrollHeight;
  });
}

function appendUser(text) {
  const d = document.createElement("div");
  d.className = "msg msg-user";
  d.textContent = text;
  chatEl.appendChild(d);
  scrollBottom();
}

function appendAgent(author, text) {
  removeProcessing();
  const d = document.createElement("div");
  d.className = "msg msg-agent";

  const badge = document.createElement("span");
  badge.className = `author-badge ${author}`;
  badge.textContent = author;

  const body = document.createElement("div");
  body.className = "msg-text";
  body.innerHTML = renderMd(text);

  d.appendChild(badge);
  d.appendChild(body);
  chatEl.appendChild(d);
  scrollBottom();
}

function makeToolCard(cls, icon, name, sub, body) {
  const card = document.createElement("div");
  card.className = `tool-card ${cls}`;

  const hdr = document.createElement("div");
  hdr.className = "tool-card-hdr";
  hdr.innerHTML = `<span class='tool-icon'>${icon}</span><span class='tool-name'>${esc(name)}</span>`
    + `<span class='tool-author'>${esc(sub)}</span><span class='toggle'>▶</span>`;

  const bd = document.createElement("div");
  bd.className = "tool-card-body";
  bd.textContent = body;

  hdr.onclick = () => {
    bd.classList.toggle("show");
    hdr.querySelector(".toggle").classList.toggle("open");
  };

  card.appendChild(hdr);
  card.appendChild(bd);
  return card;
}

function appendToolCall(author, tool, args) {
  removeProcessing();
  const card = makeToolCard("call", "TOOL", tool, author, jsonPretty(args));
  chatEl.appendChild(card);
  addProcessing();
  scrollBottom();
}

function appendToolResult(_author, tool, result) {
  removeProcessing();
  const card = makeToolCard("result", "OK", tool, "result", jsonPretty(result));
  chatEl.appendChild(card);
  scrollBottom();
  autoLoadStructure(result);
}

function appendError(text, tb) {
  removeProcessing();
  const d = document.createElement("div");
  d.className = "msg-error";
  d.innerHTML = `<strong>Error:</strong> ${esc(text)}`;

  if (tb) {
    const pre = document.createElement("pre");
    pre.style.cssText = "font-size:10px;margin-top:6px;max-height:120px;overflow:auto;color:#e0a0a0";
    pre.textContent = tb;
    d.appendChild(pre);
  }

  chatEl.appendChild(d);
  scrollBottom();
}

function addProcessing() {
  removeProcessing();
  const d = document.createElement("div");
  d.className = "processing";
  d.id = "proc-indicator";
  d.innerHTML = "<div class='spinner'></div> Processing...";
  chatEl.appendChild(d);
  scrollBottom();
}

function removeProcessing() {
  const el = $("#proc-indicator");
  if (el) el.remove();
}

function setProcessing(v) {
  S.processing = v;
  $("#chat-input").disabled = v;
  $("#send-btn").disabled = v;
  if (!v) removeProcessing();
}

function autoLoadStructure(result) {
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

function isStructureFilename(name) {
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

function isStructureItem(item) {
  return Boolean(item && (item.is_structure || isStructureFilename(item.name || item.path || "")));
}

function initViewer() {
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

async function loadStructure(path) {
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

function rebuildScene() {
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

function updateAtomVisuals() {
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

function resetCamera() {
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

function raycastAtoms(event) {
  const wrap = $("#viewer-wrap");
  const rect = wrap.getBoundingClientRect();
  const x = (((event.clientX - rect.left) / rect.width) * 2) - 1;
  const y = -(((event.clientY - rect.top) / rect.height) * 2) + 1;
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(new THREE.Vector2(x, y), S.camera);
  const hits = raycaster.intersectObjects(S.atomMeshes);
  return hits.length > 0 ? hits[0] : null;
}

function atomIdFromMesh(mesh) {
  return mesh.userData.atomId;
}

function setOrbitEnabled(v) {
  S.controls.enabled = v;
}

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

function onDeleteClick(e) {
  const hit = raycastAtoms(e);
  if (!hit) return;
  deleteAtomById(atomIdFromMesh(hit.object));
}

function deleteSelected() {
  if (!S.selected.size) return;
  const toDelete = [...S.selected];
  for (const id of toDelete) deleteAtomById(id);
  S.selected.clear();
}

function deleteAtomById(id) {
  S.atoms = S.atoms.filter((a) => a.id !== id);
  S.selected.delete(id);
  if (S.hovered === id) S.hovered = null;
  rebuildScene();
  updateStatusBar();
}

function buildAddPalette() {
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

function setupCanvasEvents() {
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

function updateStatusBar() {
  $("#sb-mode").textContent = `Mode: ${S.mode.charAt(0).toUpperCase()}${S.mode.slice(1)}`;
  $("#sb-natoms").textContent = `${S.atoms.length} atoms`;
  $("#sb-sel").textContent = S.selected.size ? `${S.selected.size} selected` : "";
  $("#sb-hint").textContent = MODE_HINT[S.mode] || "";
}

async function saveStructure() {
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

function setMode(mode) {
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

function wireToolbar() {
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

function fileIcon(item) {
  const name = typeof item === "string" ? item : (item.name || "");
  const ext = name.includes(".") ? name.split(".").pop().toLowerCase() : "";
  if (typeof item === "object" && isStructureItem(item)) return "🔬";
  if (isStructureFilename(name)) return "🔬";
  if (ext === "py") return "🐍";
  if (ext === "md") return "📝";
  if (["json", "yaml", "yml", "toml"].includes(ext)) return "⚙";
  if (["png", "jpg", "svg"].includes(ext)) return "🖼";
  return "📄";
}

function renderFiles(tree) {
  const container = $("#file-tree");
  const empty = $("#file-empty");
  container.innerHTML = "";
  if (!tree || !tree.length) {
    empty.style.display = "block";
    container.style.display = "none";
    return;
  }
  empty.style.display = "none";
  container.style.display = "block";
  buildTree(tree, container, 0);
}

function buildTree(items, container, level) {
  for (const item of items) {
    if (item.type === "directory") {
      const row = document.createElement("div");
      row.className = "tree-item";
      row.style.paddingLeft = `${(level * 14) + 6}px`;
      row.innerHTML = `<span class='tree-toggle'>▶</span><span class='tree-icon'>📁</span><span class='tree-name'>${esc(item.name)}</span>`;
      container.appendChild(row);

      const kids = document.createElement("div");
      kids.className = "tree-children";
      buildTree(item.children || [], kids, level + 1);
      container.appendChild(kids);

      row.addEventListener("click", () => {
        const open = kids.classList.toggle("open");
        row.querySelector(".tree-toggle").classList.toggle("open", open);
        row.querySelector(".tree-icon").textContent = open ? "📂" : "📁";
      });
    } else {
      const row = document.createElement("div");
      row.className = "tree-item";
      row.style.paddingLeft = `${(level * 14) + 20}px`;
      const icon = fileIcon(item);
      row.innerHTML = `<span class='tree-icon'>${icon}</span><span class='tree-name'>${esc(item.name)}</span>`
        + `<span class='tree-size'>${fmtSize(item.size)}</span>`;
      if (isStructureItem(item)) {
        row.style.cursor = "pointer";
        row.addEventListener("click", () => loadStructure(item.path));
      }
      container.appendChild(row);
    }
  }
}

function sendChat() {
  const input = $("#chat-input");
  const text = input.value.trim();
  if (!text || S.processing) return;
  wsSend({ type: "chat", message: text });
  input.value = "";
  input.style.height = "auto";
  setProcessing(true);
  addProcessing();
}

function wireChat() {
  $("#chat-input").addEventListener("input", function onInput() {
    this.style.height = "auto";
    this.style.height = `${Math.min(this.scrollHeight, 120)}px`;
  });

  $("#chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendChat();
    }
  });

  $("#send-btn").addEventListener("click", sendChat);
  $("#btn-clear-chat").addEventListener("click", () => { chatEl.innerHTML = ""; });
  $("#btn-refresh-todo").addEventListener("click", () => wsSend({ type: "refresh_todo" }));
  $("#btn-refresh-files").addEventListener("click", () => wsSend({ type: "refresh_files" }));
}

function wireKeyboardShortcuts() {
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

function reportStartupError(label, err) {
  console.error(`${label} startup error`, err);

  const text = err instanceof Error ? err.message : String(err);
  const status = $("#ws-label");
  if (status && !S.connected) {
    status.textContent = `${label} error`;
  }

  const messages = $("#chat-messages");
  if (messages) {
    const d = document.createElement("div");
    d.className = "msg-error";
    d.textContent = `${label} failed: ${text}`;
    messages.appendChild(d);
  }
}

function safeInit(label, fn) {
  try {
    fn();
    return true;
  } catch (err) {
    reportStartupError(label, err);
    return false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  safeInit("Chat", wireChat);
  safeInit("Toolbar", wireToolbar);
  safeInit("Keyboard", wireKeyboardShortcuts);
  safeInit("Task graph", initGraph);
  connect();

  const viewerReady = safeInit("Viewer", initViewer);
  if (viewerReady) {
    safeInit("Canvas controls", setupCanvasEvents);
    setMode("orbit");
  } else {
    $("#viewer-empty").textContent = "Viewer failed to initialize. Chat and workspace remain available.";
  }
});
