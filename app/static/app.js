// The chat page. It keeps the conversation in `history` and sends it with every message,
// because the server stores nothing (stateless, D-031).

// Where the API lives. Empty means "the same server as this page". If the page is ever hosted
// separately (e.g. GitHub Pages), set this to the API's address.
const API_BASE = "";

const MAX_HISTORY = 40; // the server rejects more (it only reads the last 10 anyway)

const messagesEl = document.getElementById("messages");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const sendButton = document.getElementById("send");
const statusEl = document.getElementById("status");

// Earlier messages, in the shape the API expects: {role, text} or {role: "bot", action, text}.
const history = [];
let busy = false;

// --- Showing messages ---------------------------------------------------------------------------

function addMessage(kind, text) {
  const li = document.createElement("li");
  li.className = `message ${kind}`;
  li.textContent = text; // textContent, never innerHTML: replies are shown as text, never run as code
  messagesEl.appendChild(li);
  li.scrollIntoView({ behavior: "smooth", block: "end" });
  return li;
}

function addTyping() {
  const li = addMessage("bot typing", "");
  li.setAttribute("aria-label", "The assistant is typing");
  li.innerHTML = "<span></span><span></span><span></span>"; // fixed markup, no user text
  return li;
}

function setStatus(state, text) {
  statusEl.className = `status status-${state}`;
  statusEl.textContent = text;
}

function setBusy(value) {
  busy = value;
  input.disabled = value;
  sendButton.disabled = value;
  document.querySelectorAll(".chip").forEach((chip) => (chip.disabled = value));
  if (!value) input.focus();
}

// --- Talking to the API -------------------------------------------------------------------------

async function send(text) {
  text = text.trim();
  if (!text || busy) return;

  addMessage("customer", text);
  input.value = "";
  setBusy(true);
  const typing = addTyping();

  try {
    const response = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: history.slice(-MAX_HISTORY) }),
    });
    const data = await response.json();
    typing.remove();

    if (!response.ok) {
      // 503 carries a friendly message from the server; anything else gets a generic one.
      const detail = typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.";
      addMessage("note error", detail);
      return; // the failed message isn't added to the history, so a retry starts clean
    }

    addMessage("bot", data.reply);
    history.push({ role: "customer", text }, { role: "bot", action: data.action, text: data.reply });
    setStatus("ready", "Online");
  } catch {
    typing.remove();
    addMessage("note error", "Couldn't reach the assistant. Check your connection and try again.");
  } finally {
    setBusy(false);
  }
}

// Free hosting sleeps when nobody visits; the first request wakes it up, which can take a while.
async function checkHealth() {
  const slow = setTimeout(() => setStatus("waiting", "Waking up… (up to a minute)"), 3000);
  try {
    const response = await fetch(`${API_BASE}/api/health`);
    setStatus(response.ok ? "ready" : "down", response.ok ? "Online" : "Unavailable");
  } catch {
    setStatus("down", "Unavailable");
  } finally {
    clearTimeout(slow);
  }
}

// --- Wiring -------------------------------------------------------------------------------------

form.addEventListener("submit", (event) => {
  event.preventDefault(); // stop the browser from reloading the page
  send(input.value);
});

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => send(chip.textContent));
});

checkHealth();
input.focus();
