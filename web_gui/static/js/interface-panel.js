/**
 * interface-panel.js – Coherent interface builder dialog.
 */

import { $ } from "./utils.js";
import { buildInterfaces, saveInterfaceChoice, isStructureFilename } from "./structure.js";
import { togglePanel } from "./panel-core.js";

// Currently computed candidates
let _candidates = [];
let _selectedId = null;

// ── File tree helpers ─────────────────────────────────────────────────────

function _flattenTree(nodes, out = []) {
  for (const node of nodes || []) {
    if (node.type === "file" && isStructureFilename(node.name || "")) {
      out.push(node.path);
    }
    if (node.children) _flattenTree(node.children, out);
  }
  return out;
}

async function _populateFilePicker(selectEl) {
  const prev = selectEl.value;
  while (selectEl.options.length > 1) selectEl.remove(1);

  try {
    const resp = await fetch("/api/files");
    const data = await resp.json();
    const paths = _flattenTree(data.tree || []);
    for (const p of paths) {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      if (p === prev) opt.selected = true;
      selectEl.appendChild(opt);
    }
  } catch {
    // ignore fetch errors – user can re-open the dialog
  }
}

// ── Candidates list ───────────────────────────────────────────────────────

function _renderCandidates(candidates) {
  const list = $("#if-candidates");
  list.innerHTML = "";
  _selectedId = null;
  _updateOpenBtn();

  if (!candidates.length) {
    list.innerHTML = '<div class="if-candidate-empty">No interfaces generated.</div>';
    return;
  }

  for (const c of candidates) {
    const row = document.createElement("div");
    row.className = "if-candidate";
    row.dataset.id = c.id;

    const strain = c.von_mises_strain != null
      ? (c.von_mises_strain * 100).toFixed(2) + "%"
      : "—";
    const area = c.area != null ? c.area.toFixed(1) + " Å²" : "—";

    row.innerHTML =
      `<span class="if-candidate-id">${c.id}</span>` +
      `<span class="if-candidate-stat" title="Von Mises strain">ε ${strain}</span>` +
      `<span class="if-candidate-stat" title="Interface area">A ${area}</span>` +
      `<span class="if-candidate-stat" title="Atoms">${c.n_atoms} atoms</span>` +
      `<span class="if-candidate-stat" title="Termination index">T${c.termination_index}</span>`;

    row.addEventListener("click", () => {
      document.querySelectorAll(".if-candidate.selected").forEach((el) =>
        el.classList.remove("selected")
      );
      row.classList.add("selected");
      _selectedId = c.id;
      _updateOpenBtn();
    });

    list.appendChild(row);
  }
}

function _updateOpenBtn() {
  const btn = $("#if-open");
  if (btn) btn.disabled = !_selectedId;
}

// ── Panel open callback ────────────────────────────────────────────────────

function onPanelOpen() {
  _candidates = [];
  _selectedId = null;
  $("#if-error").textContent = "";
  $("#if-candidates").innerHTML = "";
  _updateOpenBtn();
  Promise.all([
    _populateFilePicker($("#if-film-path")),
    _populateFilePicker($("#if-substrate-path")),
  ]);
}

// ── Generate handler ──────────────────────────────────────────────────────

async function handleGenerate() {
  const errorEl = $("#if-error");
  errorEl.textContent = "";

  const filmPath = $("#if-film-path").value;
  const substratePath = $("#if-substrate-path").value;

  if (!filmPath) { errorEl.textContent = "Select a film structure."; return; }
  if (!substratePath) { errorEl.textContent = "Select a substrate structure."; return; }
  if (filmPath === substratePath) { errorEl.textContent = "Film and substrate must be different files."; return; }

  const fh = parseInt($("#if-fh").value, 10);
  const fk = parseInt($("#if-fk").value, 10);
  const fl = parseInt($("#if-fl").value, 10);
  const sh = parseInt($("#if-sh").value, 10);
  const sk = parseInt($("#if-sk").value, 10);
  const sl = parseInt($("#if-sl").value, 10);

  if ([fh, fk, fl, sh, sk, sl].some((v) => isNaN(v))) {
    errorEl.textContent = "Miller indices must be integers.";
    return;
  }
  if (fh === 0 && fk === 0 && fl === 0) {
    errorEl.textContent = "Film Miller indices cannot all be zero.";
    return;
  }
  if (sh === 0 && sk === 0 && sl === 0) {
    errorEl.textContent = "Substrate Miller indices cannot all be zero.";
    return;
  }

  const btn = $("#if-generate");
  btn.disabled = true;
  btn.textContent = "Generating…";
  $("#if-candidates").innerHTML = '<div class="if-candidate-empty">Computing…</div>';
  _candidates = [];
  _selectedId = null;
  _updateOpenBtn();

  try {
    const result = await buildInterfaces({
      film_path: filmPath,
      substrate_path: substratePath,
      film_miller: [fh, fk, fl],
      substrate_miller: [sh, sk, sl],
      gap: parseFloat($("#if-gap").value) || 2.0,
      vacuum_over_film: parseFloat($("#if-vacuum").value) || 10.0,
      film_thickness: parseInt($("#if-film-thick").value, 10) || 3,
      substrate_thickness: parseInt($("#if-sub-thick").value, 10) || 3,
      in_layers: $("#if-in-layers").checked,
      max_interfaces: parseInt($("#if-max").value, 10) || 10,
    });

    if (result.error) {
      errorEl.textContent = result.error;
      $("#if-candidates").innerHTML = "";
    } else {
      _candidates = result.interfaces || [];
      _renderCandidates(_candidates);
    }
  } catch (e) {
    errorEl.textContent = String(e);
    $("#if-candidates").innerHTML = "";
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate";
  }
}

// ── Open selected handler ─────────────────────────────────────────────────

async function handleOpen() {
  if (!_selectedId) return;
  const candidate = _candidates.find((c) => c.id === _selectedId);
  if (!candidate || !candidate.poscar) {
    $("#if-error").textContent = "Selected interface has no POSCAR data.";
    return;
  }

  const btn = $("#if-open");
  btn.disabled = true;
  btn.textContent = "Opening…";
  $("#if-error").textContent = "";

  try {
    const result = await saveInterfaceChoice(candidate.poscar, `interface_${_selectedId}.extxyz`);
    if (result.error) {
      $("#if-error").textContent = result.error;
      btn.disabled = false;
      btn.textContent = "Open Selected";
    } else {
      $("#interface-panel").classList.remove("show");
    }
  } catch (e) {
    $("#if-error").textContent = String(e);
    btn.disabled = false;
    btn.textContent = "Open Selected";
  }
}

// ── Wire ──────────────────────────────────────────────────────────────────

export function wireInterfacePanel() {
  $("#tb-interface").addEventListener("click", () => togglePanel("#interface-panel", onPanelOpen));
  $("#if-cancel").addEventListener("click", () => $("#interface-panel").classList.remove("show"));
  $("#if-generate").addEventListener("click", handleGenerate);
  $("#if-open").addEventListener("click", handleOpen);
}
