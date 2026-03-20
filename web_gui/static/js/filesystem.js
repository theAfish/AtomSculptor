/**
 * filesystem.js – Workspace file-tree rendering.
 */

import { $, esc, fmtSize } from "./utils.js";
import { loadStructure, isStructureFilename } from "./structure.js";

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
