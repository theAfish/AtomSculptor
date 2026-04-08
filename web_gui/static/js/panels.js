/**
 * panels.js – Panel barrel module.
 *
 * Re-exports the public API from individual panel modules and wires
 * all panel event listeners in a single `wirePanels()` call.
 *
 * Individual panel modules:
 *   panel-core.js       – closeAllPanels, togglePanel
 *   add-panel.js        – Add atom (periodic table)
 *   surface-panel.js    – Surface builder
 *   supercell-panel.js  – Supercell builder
 *   lattice-panel.js    – Lattice operations
 *   selection-panel.js  – Selection operations
 *   export-panel.js     – Structure export
 */

export { closeAllPanels } from "./panel-core.js";
export { toggleAddPanel } from "./add-panel.js";
export { toggleSelectionPanel } from "./selection-panel.js";

import { wireAddPanel } from "./add-panel.js";
import { wireSurfacePanel } from "./surface-panel.js";
import { wireSupercellPanel } from "./supercell-panel.js";
import { wireLatticePanel } from "./lattice-panel.js";
import { wireExportPanel } from "./export-panel.js";
import { wireInterfacePanel } from "./interface-panel.js";

/** Attach event listeners for all tool-panel toolbar buttons and controls. */
export function wirePanels() {
  wireAddPanel();
  wireSurfacePanel();
  wireSupercellPanel();
  wireLatticePanel();
  wireExportPanel();
  wireInterfacePanel();
}
