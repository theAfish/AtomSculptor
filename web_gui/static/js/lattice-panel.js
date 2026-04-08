/**
 * lattice-panel.js – Lattice operations tool panel.
 */

import { S } from "./state.js";
import { $, showError, clearError, setMatrixInputs, readMatrixInputs, multiplyMatrices } from "./utils.js";
import { applyLattice } from "./structure.js";
import { togglePanel } from "./panel-core.js";

let activeMode = "scale"; // "scale" | "real"

const SM_IDS = ["sm00","sm01","sm02","sm10","sm11","sm12","sm20","sm21","sm22"];
const RM_IDS = ["rm00","rm01","rm02","rm10","rm11","rm12","rm20","rm21","rm22"];
const IDENTITY_CELL = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];

function getCurrentLatticeCell() {
  const latticeLayer = Array.isArray(S.layers)
    ? S.layers.find((layer) => layer.type === "lattice")
    : null;
  const cell = latticeLayer?.cell;
  if (
    Array.isArray(cell)
    && cell.length === 3
    && cell.every((row) => Array.isArray(row) && row.length === 3 && row.every((v) => Number.isFinite(v)))
  ) {
    return cell;
  }
  return IDENTITY_CELL;
}

function setMode(mode) {
  activeMode = mode;
  const scaleActive = mode === "scale";
  $("#la-mode-scale").checked = scaleActive;
  $("#la-mode-real").checked = !scaleActive;
  SM_IDS.forEach(id => { $(`#la-${id}`).disabled = !scaleActive; });
  RM_IDS.forEach(id => { $(`#la-${id}`).disabled = scaleActive; });
}

function initializeLatticePanel() {
  setMatrixInputs("la-sm", IDENTITY_CELL);
  setMatrixInputs("la-rm", getCurrentLatticeCell());
  $("#la-scale-atoms").checked = true;
  clearError("#la-error");
  setMode("scale");
}

function handleApply() {
  try {
    const scaleAtoms = $("#la-scale-atoms").checked;
    if (activeMode === "scale") {
      const scaleMat = readMatrixInputs("la-sm");
      const currentCell = getCurrentLatticeCell();
      const newReal = multiplyMatrices(currentCell, scaleMat);
      applyLattice(newReal, scaleAtoms);
    } else {
      const realMat = readMatrixInputs("la-rm");
      applyLattice(realMat, scaleAtoms);
    }
    $("#lattice-panel").classList.remove("show");
  } catch (e) {
    showError("#la-error", String(e));
  }
}

export function wireLatticePanel() {
  $("#tb-lattice").addEventListener("click", () => {
    togglePanel("#lattice-panel", initializeLatticePanel);
  });
  $("#la-cancel").addEventListener("click", () => $("#lattice-panel").classList.remove("show"));
  $("#la-mode-scale").addEventListener("change", () => setMode("scale"));
  $("#la-mode-real").addEventListener("change", () => setMode("real"));
  $("#la-apply").addEventListener("click", handleApply);
}
