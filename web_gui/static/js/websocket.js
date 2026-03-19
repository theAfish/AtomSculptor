/**
 * websocket.js – WebSocket connection management and message dispatch.
 */

import { S } from "./state.js";
import { $ } from "./utils.js";
import { handleMsg, setProcessing, appendError } from "./chat.js";

let reconnectTimer = null;

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
