/**
 * filesystem.js – Workspace file-tree rendering.
 */

import { $, esc, fmtSize } from "./utils.js";
import { loadStructure, isStructureFilename } from "./structure.js";

// Context menu singleton
let __fileContextMenu = null;

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

function createContextMenu() {
  if (__fileContextMenu) return __fileContextMenu;
  const menu = document.createElement("div");
  menu.id = "file-context-menu";
  menu.className = "context-menu";
  menu.style.display = "none";
  menu.innerHTML = `
    <div class="context-menu-item" data-action="open">Open</div>
    <div class="context-menu-item" data-action="duplicate">Duplicate</div>
    <div class="context-menu-item" data-action="rename">Rename</div>
    <div class="context-menu-item" data-action="delete">Delete</div>
  `;
  document.body.appendChild(menu);

  // Menu action handler
  menu.addEventListener("click", async (e) => {
    const action = e.target && e.target.dataset && e.target.dataset.action;
    if (!action) return;
    const path = menu.dataset.path;
    const isStruct = menu.dataset.isStructure === "true";
    hideContextMenu();
    try {
      if (action === "open") {
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
      } else if (action === "delete") {
        if (!confirm(`Delete ${path}? This cannot be undone.`)) return;
        const resp = await fetch("/api/file/delete", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path }) });
        const data = await resp.json();
        if (!data.ok) alert(data.error || "Delete failed");
        else refreshFileTree();
      } else if (action === "rename") {
        const newName = prompt("New name:", path.split("/").pop());
        if (!newName) return;
        const resp = await fetch("/api/file/rename", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path, new_name: newName }) });
        const data = await resp.json();
        if (!data.ok) alert(data.error || "Rename failed");
        else refreshFileTree();
      } else if (action === "duplicate") {
        const resp = await fetch("/api/file/duplicate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path }) });
        const data = await resp.json();
        if (!data.ok) alert(data.error || "Duplicate failed");
        else refreshFileTree();
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
      row.style.paddingLeft = `${(level * 14) + 20}px`;
      const icon = fileIcon(item);
      row.innerHTML = `<span class='tree-icon'>${icon}</span><span class='tree-name'>${esc(item.name)}</span>`
        + `<span class='tree-size'>${fmtSize(item.size)}</span>`;
      if (isStructureItem(item)) {
        row.style.cursor = "default";
        row.classList.add("is-draggable");
        row.draggable = true;
        row.title = "Double-click to open in viewport. Drag to add into layers.";
        row.addEventListener("dblclick", () => loadStructure(item.path));
        row.addEventListener("dragstart", (event) => {
          event.dataTransfer.effectAllowed = "copy";
          event.dataTransfer.setData("application/x-atomsculptor-structure-path", item.path);
          event.dataTransfer.setData("text/plain", item.path);
        });
      }
      // Right-click context menu for file operations (apply to all files)
      row.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        const menu = createContextMenu();
        menu.dataset.path = item.path;
        menu.dataset.isStructure = String(isStructureItem(item));
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
  if (!tree || !tree.length) {
    empty.style.display = "block";
    container.style.display = "none";
    return;
  }
  empty.style.display = "none";
  container.style.display = "block";
  buildTree(tree, container, 0);
}
