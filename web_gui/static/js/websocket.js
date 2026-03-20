/**
 * websocket.js – WebSocket connection, message routing, and dispatch.
 *
 * All incoming server messages are routed through handleMsg() to the
 * appropriate rendering module (chat, todo, filesystem, structure).
 */

import { S } from "./state.js";
import { $ } from "./utils.js";
import {
  appendUser, appendAgent, appendToolCall, appendToolResult,
  appendError, setProcessing,
} from "./chat.js";
import { updateTodo, updateAggregatorHint } from "./todo.js";
import { renderFiles } from "./filesystem.js";
import { tryAutoLoadFromResult } from "./structure.js";

let reconnectTimer = null;

function handleMsg(m) {
  switch (m.type) {
    case "user_message": appendUser(m.text); break;
    case "agent_message": appendAgent(m.author, m.text); break;
    case "tool_call": appendToolCall(m.author, m.tool, m.args); break;
    case "tool_result":
      appendToolResult(m.author, m.tool, m.result);
      tryAutoLoadFromResult(m.result);
      break;
    case "todo_flow_update": updateTodo(m.data); break;
    case "files_update": renderFiles(m.data); break;
    case "aggregator_status": updateAggregatorHint(m.data); break;
    case "done": setProcessing(false); break;
    case "error": appendError(m.text, m.traceback); setProcessing(false); break;
    default: break;
  }
}

export function connect() {
  if (S.ws && S.ws.readyState <= 1) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  S.ws = new WebSocket(`${proto}://${location.host}/ws`);

  S.ws.onopen = () => {
    S.connected = true;
    $("#ws-dot").classList.add("ok");
    $("#ws-label").textContent = "Connected";
  };

  S.ws.onclose = () => {
    S.connected = false;
    $("#ws-dot").classList.remove("ok");
    $("#ws-label").textContent = "Disconnected";
    if (S.processing) {
      setProcessing(false);
      appendError("Connection lost — the server stopped responding. Your request was not completed.");
    }
    if (!reconnectTimer) {
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connect();
      }, 2000);
    }
  };

  S.ws.onerror = () => {
    if (S.processing) {
      setProcessing(false);
      appendError("WebSocket error — connection to the server failed.");
    }
  };

  S.ws.onmessage = (e) => {
    try {
      handleMsg(JSON.parse(e.data));
    } catch (err) {
      console.error("ws msg error", err);
    }
  };
}

export function wsSend(obj) {
  if (S.ws && S.ws.readyState === 1) S.ws.send(JSON.stringify(obj));
}
