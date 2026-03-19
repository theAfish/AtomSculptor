/**
 * chat.js – Chat panel rendering, message dispatch, and processing indicators.
 */

import { S } from "./state.js";
import { $, esc, renderMd, jsonPretty } from "./utils.js";
import { wsSend } from "./websocket.js";
import { updateTodo } from "./todo.js";
import { updateAggregatorHint } from "./todo.js";
import { renderFiles } from "./filesystem.js";
import { loadStructure, isStructureFilename } from "./structure.js";

const chatEl = () => $("#chat-messages");
const scrollEl = () => $("#chat-scroll");

function scrollBottom() {
  requestAnimationFrame(() => {
    const el = scrollEl();
    if (el) el.scrollTop = el.scrollHeight;
  });
}

export function appendUser(text) {
  const d = document.createElement("div");
  d.className = "msg msg-user";
  d.textContent = text;
  chatEl().appendChild(d);
  scrollBottom();
}

export function appendAgent(author, text) {
  removeProcessing();
  const d = document.createElement("div");
  d.className = "msg msg-agent";

  const badge = document.createElement("span");
  badge.className = `author-badge ${author}`;
  badge.textContent = author;

  const body = document.createElement("div");
  body.className = "msg-text";
  body.innerHTML = renderMd(text);

  d.appendChild(badge);
  d.appendChild(body);
  chatEl().appendChild(d);
  scrollBottom();
}

function makeToolCard(cls, icon, name, sub, body) {
  const card = document.createElement("div");
  card.className = `tool-card ${cls}`;

  const hdr = document.createElement("div");
  hdr.className = "tool-card-hdr";
  hdr.innerHTML = `<span class='tool-icon'>${icon}</span><span class='tool-name'>${esc(name)}</span>`
    + `<span class='tool-author'>${esc(sub)}</span><span class='toggle'>▶</span>`;

  const bd = document.createElement("div");
  bd.className = "tool-card-body";
  bd.textContent = body;

  hdr.onclick = () => {
    bd.classList.toggle("show");
    hdr.querySelector(".toggle").classList.toggle("open");
  };

  card.appendChild(hdr);
  card.appendChild(bd);
  return card;
}

export function appendToolCall(author, tool, args) {
  removeProcessing();
  const card = makeToolCard("call", "TOOL", tool, author, jsonPretty(args));
  chatEl().appendChild(card);
  addProcessing();
  scrollBottom();
}

export function appendToolResult(_author, tool, result) {
  removeProcessing();
  const card = makeToolCard("result", "OK", tool, "result", jsonPretty(result));
  chatEl().appendChild(card);
  scrollBottom();
  autoLoadStructure(result);
}

export function appendError(text, tb) {
  removeProcessing();
  const d = document.createElement("div");
  d.className = "msg-error";
  d.innerHTML = `<strong>Error:</strong> ${esc(text)}`;

  if (tb) {
    const pre = document.createElement("pre");
    pre.style.cssText = "font-size:10px;margin-top:6px;max-height:120px;overflow:auto;color:#e0a0a0";
    pre.textContent = tb;
    d.appendChild(pre);
  }

  chatEl().appendChild(d);
  scrollBottom();
}

export function addProcessing() {
  removeProcessing();
  const d = document.createElement("div");
  d.className = "processing";
  d.id = "proc-indicator";
  d.innerHTML = "<div class='spinner'></div> Processing...";
  chatEl().appendChild(d);
  scrollBottom();
}

export function removeProcessing() {
  const el = $("#proc-indicator");
  if (el) el.remove();
}

export function setProcessing(v) {
  S.processing = v;
  $("#chat-input").disabled = v;
  $("#send-btn").disabled = v;
  if (!v) removeProcessing();
}

function autoLoadStructure(result) {
  if (!result || typeof result !== "object") return;
  for (const key of Object.keys(result)) {
    const val = result[key];
    if (typeof val !== "string") continue;
    if (isStructureFilename(val)) {
      loadStructure(val);
      return;
    }
  }
}

export function handleMsg(m) {
  switch (m.type) {
    case "user_message": appendUser(m.text); break;
    case "agent_message": appendAgent(m.author, m.text); break;
    case "tool_call": appendToolCall(m.author, m.tool, m.args); break;
    case "tool_result": appendToolResult(m.author, m.tool, m.result); break;
    case "todo_flow_update": updateTodo(m.data); break;
    case "files_update": renderFiles(m.data); break;
    case "aggregator_status": updateAggregatorHint(m.data); break;
    case "done": setProcessing(false); break;
    case "error": appendError(m.text, m.traceback); setProcessing(false); break;
    default:
      break;
  }
}

export function sendChat() {
  const input = $("#chat-input");
  const text = input.value.trim();
  if (!text || S.processing) return;
  wsSend({ type: "chat", message: text });
  input.value = "";
  input.style.height = "auto";
  setProcessing(true);
  addProcessing();
}

export function wireChat() {
  $("#chat-input").addEventListener("input", function onInput() {
    this.style.height = "auto";
    this.style.height = `${Math.min(this.scrollHeight, 120)}px`;
  });

  $("#chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendChat();
    }
  });

  $("#send-btn").addEventListener("click", sendChat);
  $("#btn-clear-chat").addEventListener("click", () => { chatEl().innerHTML = ""; });
  $("#btn-refresh-todo").addEventListener("click", () => wsSend({ type: "refresh_todo" }));
  $("#btn-refresh-files").addEventListener("click", () => wsSend({ type: "refresh_files" }));
}
