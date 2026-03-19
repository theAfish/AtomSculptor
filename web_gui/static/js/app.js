/**
 * app.js – Main entry point.  Wires up every subsystem on DOMContentLoaded.
 *
 * Module map:
 *   state.js      – global state object & constants
 *   utils.js      – pure formatting / DOM helpers
 *   websocket.js  – WebSocket connection & message dispatch
 *   chat.js       – chat panel (messages, processing, send)
 *   todo.js       – task-flow DAG (Cytoscape) & aggregator hint
 *   filesystem.js – workspace file-tree rendering
 *   viewer.js     – Three.js scene, camera, rendering loop
 *   structure.js  – structure data (load / save / detect)
 *   editor.js     – edit modes (select, drag, rotate, box, add, delete)
 */

import { S } from "./state.js";
import { $ } from "./utils.js";
import { connect } from "./websocket.js";
import { wireChat } from "./chat.js";
import { initGraph } from "./todo.js";
import { initViewer } from "./viewer.js";
import { setupCanvasEvents, setMode, wireToolbar, wireKeyboardShortcuts } from "./editor.js";

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
