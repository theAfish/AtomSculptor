/**
 * state.js – Global application state and constants.
 */

export const S = {
  ws: null,
  cy: null,
  connected: false,
  processing: false,
  aggregatorStatus: null,
  todoData: { tasks: [], finished: true },

  renderer: null,
  scene: null,
  camera: null,
  controls: null,
  rafId: null,

  structPath: null,
  atoms: [],
  layers: [],
  selectedLayerIds: new Set(),
  layerSeq: 0,
  cell: null,
  pbc: [false, false, false],
  undoStack: [],
  redoStack: [],

  atomMeshes: [],
  bondMeshes: [],
  cellLines: null,

  mode: "orbit",
  selected: new Set(),
  hovered: null,
  addElement: "H",

  gizmoJustDragged: false,

  boxStart: null,
};

export const STRUCTURE_EXTS = new Set([
  "cif", "xyz", "vasp", "poscar", "extxyz", "pdb", "sdf", "mol2",
]);
export const STRUCTURE_PREFIXES = ["poscar", "contcar"];

export const MAX_UNDO_ENTRIES = 100;

export const STATUS_COLOR = {
  pending: "#858585",
  ready: "#4fc3f7",
  in_progress: "#ffb74d",
  done: "#81c784",
  blocked: "#e57373",
  deprecated: "#616161",
};

export const ELEM_COLOR = {
  H: "#ffffff", C: "#404040", N: "#3050f8", O: "#ff0d0d", F: "#90e050",
  P: "#ff8000", S: "#ffff30", Cl: "#1ff01f", Br: "#a62929", I: "#940094",
  Li: "#cc80ff", Na: "#ab5cf2", K: "#8f40d4", Ca: "#3dff00", Mg: "#8aff00",
  Al: "#bfa6a6", Si: "#f0c8a0", Fe: "#e06633", Cu: "#c88033", Zn: "#7d80b0",
  Ag: "#c0c0c0", Au: "#ffd123", Pt: "#d0d0e0", Pd: "#006985", Ti: "#bfc2c7",
  Co: "#f090a0", Ni: "#50d050", Mn: "#9c7ac7", Cr: "#8a99c7",
  He: "#d9ffff", Ne: "#b3e3f5", Ar: "#80d1e3", Xe: "#429eb0", Kr: "#5cb8d1",
  default: "#ff1493",
};

export const ELEM_RADIUS = {
  H: 0.31, C: 0.77, N: 0.75, O: 0.73, F: 0.71,
  P: 1.06, S: 1.02, Cl: 0.99, Br: 1.14, I: 1.33,
  Li: 1.28, Na: 1.66, K: 2.03, Ca: 1.74, Mg: 1.41,
  Al: 1.21, Si: 1.17, Fe: 1.25, Cu: 1.28, Zn: 1.22,
  Ag: 1.44, Au: 1.44, Pt: 1.39, Pd: 1.31, Ti: 1.47,
  Co: 1.25, Ni: 1.24, Mn: 1.29, Cr: 1.29,
  He: 0.28, Ne: 0.58, Ar: 1.06, Xe: 1.31, Kr: 1.16,
  default: 1.2,
};

// Bond tolerance: bond drawn when dist < (rCov_A + rCov_B) * BOND_TOLERANCE
export const BOND_TOLERANCE = 1.2;

export const MODE_HINT = {
  orbit: "Drag to rotate · Scroll to zoom · Right-drag to pan · Click atom to select",
  box: "Drag box to select · Shift/Ctrl to add to selection",
  translate: "Select atoms then drag gizmo axes · Arrows/WASD to nudge 0.1 Å",
  rotate: "Select atoms then drag gizmo rings · Arrows/WASD to nudge 1°",
  scale: "Select atoms then drag gizmo handles · Arrows/WASD to nudge",
  add: "Pick element and coordinates in the Add Atom panel",
  delete: "Click atom to delete",
};
