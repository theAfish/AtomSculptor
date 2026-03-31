/**
 * filesystem.js – Workspace file-tree rendering.
 */

import { $, esc, fmtSize } from "./utils.js";
import { loadStructure, isStructureFilename } from "./structure.js";

// Context menu singleton
let __fileContextMenu = null;
let __fileMarquee = null;

const __selectedFilePaths = new Set();
const __fileRowsByPath = new Map();
let __fileClipboard = [];
let __marqueeState = null;
let __fileHotkeysBound = false;

const PROTECTED_PATH_PARTS = new Set(["toolbox", "instructions"]);

function normalizePath(path) {
  return String(path || "").replace(/\\/g, "/").replace(/^\/+/, "");
}

function isProtectedPath(path) {
  const rel = normalizePath(path);
  if (!rel) return false;
  return rel.split("/").some((part) => PROTECTED_PATH_PARTS.has(part));
}

function parentDir(path) {
  const rel = normalizePath(path);
  const idx = rel.lastIndexOf("/");
  return idx > -1 ? rel.slice(0, idx) : "";
}

function parsePaths(raw) {
  try {
    const parsed = JSON.parse(raw || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function syncSelectionClasses() {
  for (const [path, row] of __fileRowsByPath.entries()) {
    row.classList.toggle("selected", __selectedFilePaths.has(path));
  }
}

function setSelection(paths) {
  __selectedFilePaths.clear();
  for (const path of paths || []) {
    const rel = normalizePath(path);
    if (rel && __fileRowsByPath.has(rel)) __selectedFilePaths.add(rel);
  }
  syncSelectionClasses();
}

function selectSingle(path) {
  setSelection([path]);
}

function toggleSelection(path) {
  const rel = normalizePath(path);
  if (!rel || !__fileRowsByPath.has(rel)) return;
  if (__selectedFilePaths.has(rel)) __selectedFilePaths.delete(rel);
  else __selectedFilePaths.add(rel);
  syncSelectionClasses();
}

function currentSelection() {
  return Array.from(__selectedFilePaths);
}

function getPasteTargetForSelection(selection) {
  const selected = (selection || []).map((p) => normalizePath(p)).filter(Boolean);
  if (!selected.length) return "";
  const dirs = selected.map((p) => parentDir(p));
  const first = dirs[0];
  return dirs.every((d) => d === first) ? first : "";
}

function isTypingTarget(el) {
  if (!el) return false;
  const tag = (el.tagName || "").toLowerCase();
  return tag === "input" || tag === "textarea" || el.isContentEditable;
}

async function performPaste(targetDir) {
  if (!__fileClipboard.length) return;
  const target = normalizePath(targetDir || "");
  const resp = await fetch("/api/file/paste", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paths: __fileClipboard, target_dir: target }),
  });
  const data = await resp.json();
  if (!data.ok) {
    alert(data.error || "Paste failed");
    return;
  }
  await refreshFileTree();
}

async function performDelete(paths) {
  const selected = (paths || []).map((p) => normalizePath(p)).filter(Boolean);
  if (!selected.length) return;
  const label = selected.length === 1 ? selected[0] : `${selected.length} files`;
  if (!confirm(`Delete ${label}? This cannot be undone.`)) return;

  const resp = await fetch("/api/file/delete-many", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paths: selected }),
  });
  const data = await resp.json();
  if (!data.ok) {
    alert(data.error || "Delete failed");
    return;
  }

  setSelection([]);
  await refreshFileTree();
}

function ensureMarquee() {
  if (__fileMarquee) return __fileMarquee;
  const box = document.createElement("div");
  box.className = "file-tree-marquee";
  box.style.display = "none";
  document.body.appendChild(box);
  __fileMarquee = box;
  return box;
}

function intersects(a, b) {
  return !(a.right < b.left || a.left > b.right || a.bottom < b.top || a.top > b.bottom);
}

function updateMarqueeSelection(rect) {
  const next = new Set(__marqueeState.baseSelection);
  for (const [path, row] of __fileRowsByPath.entries()) {
    const rr = row.getBoundingClientRect();
    if (intersects(rect, rr)) next.add(path);
  }
  setSelection(Array.from(next));
}

function startMarqueeSelection(event) {
  const box = ensureMarquee();
  const baseSelection = (event.metaKey || event.ctrlKey) ? new Set(__selectedFilePaths) : new Set();
  if (!(event.metaKey || event.ctrlKey)) setSelection([]);

  __marqueeState = {
    startX: event.clientX,
    startY: event.clientY,
    baseSelection,
  };

  box.style.display = "block";
  box.style.left = `${event.clientX}px`;
  box.style.top = `${event.clientY}px`;
  box.style.width = "0px";
  box.style.height = "0px";

  const onMove = (moveEvent) => {
    if (!__marqueeState) return;
    const x1 = Math.min(__marqueeState.startX, moveEvent.clientX);
    const y1 = Math.min(__marqueeState.startY, moveEvent.clientY);
    const x2 = Math.max(__marqueeState.startX, moveEvent.clientX);
    const y2 = Math.max(__marqueeState.startY, moveEvent.clientY);

    const rect = { left: x1, top: y1, right: x2, bottom: y2 };
    box.style.left = `${x1}px`;
    box.style.top = `${y1}px`;
    box.style.width = `${x2 - x1}px`;
    box.style.height = `${y2 - y1}px`;
    updateMarqueeSelection(rect);
  };

  const onUp = () => {
    box.style.display = "none";
    __marqueeState = null;
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onUp);
  };

  document.addEventListener("mousemove", onMove);
  document.addEventListener("mouseup", onUp);
}

async function uploadFileToSandbox(file) {
  const formData = new FormData();
  formData.append("file", file);

  const resp = await fetch("/api/file/upload", { method: "POST", body: formData });
  if (!resp.ok) {
    throw new Error(`Upload failed: ${resp.status} ${resp.statusText}`);
  }
  const data = await resp.json();
  if (data.error) {
    throw new Error(data.error);
  }
  return data;
}

async function handleFilePanelDrop(event) {
  if (!event || !event.dataTransfer) return;

  const files = Array.from(event.dataTransfer.files || []);
  if (!files.length) return;

  event.preventDefault();
  event.dataTransfer.dropEffect = "copy";

  for (const file of files) {
    try {
      const result = await uploadFileToSandbox(file);
      if (!result.ok) {
        console.warn("upload file failed", file.name, result);
      }
    } catch (err) {
      console.error("file upload error", file.name, err);
    }
  }

  await refreshFileTree();
}

function initFilePanelDragDrop() {
  const fileTree = $("#file-tree");
  const fileEmpty = $("#file-empty");
  const dropTargets = [fileTree, fileEmpty].filter(Boolean);

  dropTargets.forEach((target) => {
    target.addEventListener("dragover", (event) => {
      if (!event.dataTransfer) return;
      const hasFiles = Array.from(event.dataTransfer.types || []).includes("Files");
      if (!hasFiles) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
    });

    target.addEventListener("drop", handleFilePanelDrop);
  });
}

initFilePanelDragDrop();

function initFileMarqueeSelection() {
  const fileTree = $("#file-tree");
  if (!fileTree || fileTree.dataset.boxSelectBound === "true") return;
  fileTree.dataset.boxSelectBound = "true";

  fileTree.addEventListener("mousedown", (event) => {
    if (event.button !== 0) return;
    const onTreeItem = Boolean(event.target.closest(".tree-item"));
    const shouldStartMarquee = event.shiftKey || !onTreeItem;
    if (!shouldStartMarquee) return;
    event.preventDefault();
    startMarqueeSelection(event);
  });
}

initFileMarqueeSelection();

function initFileKeyboardShortcuts() {
  if (__fileHotkeysBound) return;
  __fileHotkeysBound = true;

  document.addEventListener("keydown", async (event) => {
    if (isTypingTarget(event.target)) return;

    const selection = currentSelection();
    const hasSelection = selection.length > 0;
    const mod = event.ctrlKey || event.metaKey;

    if (!hasSelection && !(mod && event.key.toLowerCase() === "v")) return;

    try {
      if (event.key === "Delete") {
        if (!hasSelection) return;
        event.preventDefault();
        await performDelete(selection);
        return;
      }

      if (mod && event.key.toLowerCase() === "c") {
        if (!hasSelection) return;
        event.preventDefault();
        if (selection.some((p) => isProtectedPath(p))) {
          alert("Copy not allowed for toolbox/instructions files.");
          return;
        }
        __fileClipboard = selection.slice();
        return;
      }

      if (mod && event.key.toLowerCase() === "v") {
        event.preventDefault();
        if (!__fileClipboard.length) return;
        const targetDir = getPasteTargetForSelection(selection);
        await performPaste(targetDir);
      }
    } catch (err) {
      console.error("file keyboard shortcut", err);
      alert(String(err));
    }
  });
}

initFileKeyboardShortcuts();

async function refreshFileTree() {
  try {
    const resp = await fetch("/api/files");
    const data = await resp.json();
    if (data && Array.isArray(data.tree)) renderFiles(data.tree);
  } catch (e) {
    console.error("refreshFileTree", e);
  }
}

function hideContextMenu() {
  if (!__fileContextMenu) return;
  __fileContextMenu.style.display = "none";
}

function updateContextMenuState(menu) {
  const selected = parsePaths(menu.dataset.paths);
  const protectedSelection = selected.some((p) => isProtectedPath(p));
  const targetDir = normalizePath(menu.dataset.pasteTarget || "");
  const canPaste = __fileClipboard.length > 0 && !isProtectedPath(targetDir);

  for (const item of menu.querySelectorAll(".context-menu-item")) {
    item.classList.remove("disabled");
  }

  const openItem = menu.querySelector(".context-menu-item[data-action='open']");
  const copyItem = menu.querySelector(".context-menu-item[data-action='copy']");
  const pasteItem = menu.querySelector(".context-menu-item[data-action='paste']");
  const deleteItem = menu.querySelector(".context-menu-item[data-action='delete']");

  if (openItem && selected.length !== 1) openItem.classList.add("disabled");
  if (copyItem && (selected.length === 0 || protectedSelection)) copyItem.classList.add("disabled");
  if (pasteItem && !canPaste) pasteItem.classList.add("disabled");
  if (deleteItem && (selected.length === 0 || protectedSelection)) deleteItem.classList.add("disabled");
}

function createContextMenu() {
  if (__fileContextMenu) return __fileContextMenu;
  const menu = document.createElement("div");
  menu.id = "file-context-menu";
  menu.className = "context-menu";
  menu.style.display = "none";
  menu.innerHTML = `
    <div class="context-menu-item" data-action="open">Open</div>
    <div class="context-menu-item" data-action="copy">Copy</div>
    <div class="context-menu-item" data-action="paste">Paste</div>
    <div class="context-menu-item" data-action="delete">Delete</div>
  `;
  document.body.appendChild(menu);

  // Menu action handler
  menu.addEventListener("click", async (e) => {
    const action = e.target && e.target.dataset && e.target.dataset.action;
    if (!action) return;
    if (e.target.classList.contains("disabled")) return;

    const selected = parsePaths(menu.dataset.paths);
    const path = selected[0] || menu.dataset.path;
    const isStruct = menu.dataset.isStructure === "true";
    const pasteTarget = normalizePath(menu.dataset.pasteTarget || "");

    hideContextMenu();
    try {
      if (action === "open") {
        if (selected.length !== 1) return;
        if (isStruct) {
          loadStructure(path);
        } else {
          const resp = await fetch(`/api/file-content?path=${encodeURIComponent(path)}`);
          const data = await resp.json();
          if (data && data.content !== undefined) {
            const blob = new Blob([data.content], { type: "text/plain" });
            const url = URL.createObjectURL(blob);
            window.open(url, "_blank");
          } else {
            alert(data.error || "Could not open file.");
          }
        }
      } else if (action === "copy") {
        __fileClipboard = selected.slice();
      } else if (action === "paste") {
        await performPaste(pasteTarget);
      } else if (action === "delete") {
        await performDelete(selected);
      }
    } catch (err) {
      console.error("context action", err);
      alert(String(err));
    }
  });

  // Global handlers
  document.addEventListener("click", (e) => {
    if (!menu.contains(e.target)) hideContextMenu();
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hideContextMenu(); });

  __fileContextMenu = menu;
  return menu;
}

function isStructureItem(item) {
  return Boolean(item && (item.is_structure || isStructureFilename(item.name || item.path || "")));
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
      row.dataset.path = item.path || "";
      row.dataset.type = "file";
      row.style.paddingLeft = `${(level * 14) + 20}px`;
      const icon = fileIcon(item);
      row.innerHTML = `<span class='tree-icon'>${icon}</span><span class='tree-name'>${esc(item.name)}</span>`
        + `<span class='tree-size'>${fmtSize(item.size)}</span>`;
      if (item.path) __fileRowsByPath.set(item.path, row);
      if (isProtectedPath(item.path || "")) row.classList.add("is-protected");

      row.addEventListener("click", (event) => {
        if (!item.path) return;
        if (event.metaKey || event.ctrlKey) toggleSelection(item.path);
        else selectSingle(item.path);
      });

      if (isStructureItem(item)) {
        const canDrag = Boolean(item && item.path);
        if (canDrag) {
          row.classList.add("is-draggable");
          row.draggable = true;
          row.title = "Double-click to open in viewport. Drag to add into layers. Shift+drag to box-select files.";
          row.addEventListener("dblclick", () => loadStructure(item.path));
          row.addEventListener("dragstart", (event) => {
            if (event.shiftKey || __marqueeState) {
              event.preventDefault();
              return;
            }
            event.dataTransfer.effectAllowed = "copy";
            event.dataTransfer.setData("application/x-atomsculptor-structure-path", item.path);
            event.dataTransfer.setData("text/plain", item.path);
          });
          row.style.cursor = "pointer";
        } else {
          row.style.cursor = "default";
        }
      }
      // Right-click context menu for file operations (apply to all files)
      row.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        if (item.path && !__selectedFilePaths.has(item.path)) {
          selectSingle(item.path);
        }
        const menu = createContextMenu();
        menu.dataset.path = item.path;
        menu.dataset.isStructure = String(isStructureItem(item));
        menu.dataset.paths = JSON.stringify(currentSelection());
        menu.dataset.pasteTarget = parentDir(item.path);
        updateContextMenuState(menu);
        // Position and show
        const x = Math.min(window.innerWidth - 160, event.pageX);
        const y = Math.min(window.innerHeight - 160, event.pageY);
        menu.style.left = `${x}px`;
        menu.style.top = `${y}px`;
        menu.style.display = "block";
      });
      container.appendChild(row);
    }
  }
}

export function renderFiles(tree) {
  const container = $("#file-tree");
  const empty = $("#file-empty");
  container.innerHTML = "";
  __fileRowsByPath.clear();
  if (!tree || !tree.length) {
    setSelection([]);
    empty.style.display = "block";
    container.style.display = "none";
    return;
  }
  empty.style.display = "none";
  container.style.display = "block";
  buildTree(tree, container, 0);
  const keep = currentSelection().filter((p) => __fileRowsByPath.has(p));
  setSelection(keep);
}

export { refreshFileTree };
