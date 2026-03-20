/**
 * layers.js – Layer panel UI for lattice + atom layers.
 */

import { S } from "./state.js";
import { $, esc } from "./utils.js";
import {
  LAYERS_CHANGED_EVENT,
  addAtomsLayer,
  appendStructureToLayer,
  deleteSelectedAtomLayers,
  mergeSelectedAtomLayers,
  setSelectedAtomLayers,
  useLatticeFromLayer,
} from "./structure.js";

function layerLabel(layer) {
  if (layer.type === "lattice") return "Lattice";
  const count = S.atoms.filter((atom) => atom.layerId === layer.id).length;
  return `${layer.name} (${count})`;
}

function updateActionState() {
  const selectedCount = [...S.selectedLayerIds].length;
  $("#btn-merge-layer").disabled = selectedCount < 2;
  $("#btn-del-layer").disabled = selectedCount < 1;
}

function renderLayerList() {
  const list = $("#layer-list");
  const empty = $("#layer-empty");
  list.innerHTML = "";

  if (!Array.isArray(S.layers) || !S.layers.length) {
    empty.style.display = "block";
    updateActionState();
    return;
  }
  empty.style.display = "none";

  for (const layer of S.layers) {
    const row = document.createElement("div");
    row.className = `layer-item ${layer.type === "lattice" ? "lattice" : "atoms"}`;
    if (layer.type === "atoms" && S.selectedLayerIds.has(layer.id)) {
      row.classList.add("selected");
    }

    const icon = layer.type === "lattice" ? "▦" : "●";
    const meta = layer.type === "lattice" ? "base" : layer.id;
    const actionHtml = layer.type === "atoms"
      ? "<span class='li-actions'><button type='button' class='li-use-lattice' title='Apply this layer lattice metadata to base lattice'>Use lattice</button></span>"
      : "";
    row.innerHTML = `<span class='li-icon'>${icon}</span><span class='li-name'>${esc(layerLabel(layer))}</span><span class='li-meta'>${esc(meta)}</span>${actionHtml}`;

    if (layer.type === "atoms") {
      row.querySelector(".li-use-lattice")?.addEventListener("click", (event) => {
        event.stopPropagation();
        const result = useLatticeFromLayer(layer.id);
        if (!result.ok) {
          alert(result.error);
        }
      });

      row.addEventListener("click", (event) => {
        if (event.shiftKey) {
          const next = new Set(S.selectedLayerIds);
          if (next.has(layer.id)) next.delete(layer.id);
          else next.add(layer.id);
          setSelectedAtomLayers([...next]);
          return;
        }
        setSelectedAtomLayers([layer.id]);
      });

      row.addEventListener("dragover", (event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
        row.classList.add("drop-target");
      });

      row.addEventListener("dragleave", () => {
        row.classList.remove("drop-target");
      });

      row.addEventListener("drop", async (event) => {
        event.preventDefault();
        row.classList.remove("drop-target");
        const path = event.dataTransfer.getData("application/x-atomsculptor-structure-path")
          || event.dataTransfer.getData("text/plain");
        if (!path) return;

        const result = await appendStructureToLayer(path, layer.id);
        if (!result.ok) {
          alert(`Layer import failed: ${result.error || "unknown"}`);
        }
      });
    }

    list.appendChild(row);
  }

  updateActionState();
}

export function initLayersPanel() {
  document.addEventListener(LAYERS_CHANGED_EVENT, renderLayerList);

  const dropHost = $("#layers-body");
  dropHost.addEventListener("dragover", (event) => {
    const hasStructure = event.dataTransfer.types.includes("application/x-atomsculptor-structure-path")
      || event.dataTransfer.types.includes("text/plain");
    if (!hasStructure) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  });

  dropHost.addEventListener("drop", async (event) => {
    // Row-level handlers own in-row drops; this is for empty panel space.
    if (event.target.closest(".layer-item.atoms")) return;
    const path = event.dataTransfer.getData("application/x-atomsculptor-structure-path")
      || event.dataTransfer.getData("text/plain");
    if (!path) return;

    event.preventDefault();
    const layerId = addAtomsLayer();
    const result = await appendStructureToLayer(path, layerId);
    if (!result.ok) {
      alert(`Layer import failed: ${result.error || "unknown"}`);
    }
  });

  $("#btn-add-layer").addEventListener("click", () => {
    addAtomsLayer();
  });

  $("#btn-del-layer").addEventListener("click", () => {
    const result = deleteSelectedAtomLayers();
    if (!result.ok) {
      alert(result.error);
    }
  });

  $("#btn-merge-layer").addEventListener("click", () => {
    const result = mergeSelectedAtomLayers();
    if (!result.ok) {
      alert(result.error);
    }
  });

  renderLayerList();
}
