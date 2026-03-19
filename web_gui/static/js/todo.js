/**
 * todo.js – Task-flow DAG (Cytoscape) and aggregator status indicator.
 */

import { S, STATUS_COLOR } from "./state.js";
import { $, esc, truncate } from "./utils.js";

export function initGraph() {
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

export function updateTodo(data) {
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

export function updateAggregatorHint(status) {
  S.aggregatorStatus = status || null;

  const el = $("#aggregator-hint");
  if (!el) return;

  if (!status) {
    el.textContent = "Memory idle";
    el.className = "header-pill idle";
    el.title = "Background note aggregation status";
    return;
  }

  if (status.running) {
    const countText = Number.isFinite(status.note_count) ? ` (${status.note_count} notes)` : "";
    el.textContent = `Memory aggregating${countText}`;
    el.className = "header-pill running";
    el.title = status.message || "Aggregating notes into instructions";
    return;
  }

  if (status.last_error) {
    el.textContent = "Memory aggregation failed";
    el.className = "header-pill error";
    el.title = status.last_error;
    return;
  }

  el.textContent = "Memory idle";
  el.className = "header-pill idle";
  el.title = status.message || "Background note aggregation status";
}
