// The chat page. It keeps the conversation in `history` and sends it with every message,
// because the server stores nothing (stateless, D-031).

// Where the API lives. Online, the page is a static site and the API a separate server, so requests
// go to API_URL. Locally (or if the API server serves the page itself) they go to the same server.
const API_URL = "https://shop-assistant-api.onrender.com";
const API_BASE = ["localhost", "127.0.0.1"].includes(location.hostname) || location.origin === API_URL ? "" : API_URL;

const WAKE_SHOW_AFTER = 1500; // ms: only show the wake-up screen if the API doesn't answer quickly
const WAKE_EXPECTED = 60000; // ms: Render's free servers take about a minute to wake up
const WAKE_GIVE_UP = 150000; // ms

const MAX_HISTORY = 40; // the server rejects more (it only reads the last 10 anyway)
const MAX_CHARS = 500;

const messagesEl = document.getElementById("messages");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const sendButton = document.getElementById("send");
const statusEl = document.getElementById("status");
const panel = document.getElementById("panel");
const panelBody = document.getElementById("panel-body");
const wakeEl = document.getElementById("wake");
const wakeText = document.getElementById("wake-text");
const progressBar = document.getElementById("progress-bar");

// Earlier messages, in the shape the API expects: {role, text} or {role: "bot", action, text}.
const history = [];
// One entry per bot reply: {data (the API's response), bubble, ownerAnswer}.
const decisions = [];
let busy = false;
let ready = false; // true once the API has answered its health check

const ACTIONS = {
  answer: {
    label: "Answer",
    explain: "Answered from the knowledge base. Every answer must cite at least one public entry; " +
      "if it can't, the code turns it into a question for the owner instead.",
  },
  ask_owner: {
    label: "Ask owner",
    explain: "The bot doesn't have the answer, or a shop rule says to check first. Instead of guessing, " +
      "it asks the owner and tells the customer it will get back to them.",
  },
  handoff: {
    label: "Hand off",
    explain: "This needs a person (a complaint, a refund, a negotiation or a large order), so the bot " +
      "hands the chat to staff.",
  },
};

// --- Small DOM helper ---------------------------------------------------------------------------

// el("p", {className: "x"}, "text", child) -> <p class="x">text<child></p>.
// Strings become text nodes, so nothing passed in here is ever run as HTML.
function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children.filter((c) => c !== null && c !== undefined && c !== false));
  return node;
}

function scrollToEnd(node) {
  node.scrollIntoView({ behavior: "smooth", block: "end" });
}

// --- Chat messages ------------------------------------------------------------------------------

function addMessage(kind, text) {
  const li = el("li", { className: `message ${kind}` }, el("span", { className: "text", textContent: text }));
  messagesEl.appendChild(li);
  scrollToEnd(li);
  return li;
}

function addNote(text, { error = false, button = null } = {}) {
  const li = el("li", { className: `message note${error ? " error" : ""}` }, text, button && " ", button);
  messagesEl.appendChild(li);
  scrollToEnd(li);
  return li;
}

function addTyping() {
  const li = el("li", { className: "message bot typing", ariaLabel: "The assistant is typing" },
    el("span"), el("span"), el("span"));
  messagesEl.appendChild(li);
  scrollToEnd(li);
  return li;
}

function addBotReply(data) {
  const entry = { data, bubble: null, ownerAnswer: null };
  const why = el("button", { type: "button", className: "why", textContent: "Why this reply?" });
  why.addEventListener("click", () => select(entry, { open: true }));
  entry.bubble = el("li", { className: "message bot" }, el("span", { className: "text", textContent: data.reply }), why);
  messagesEl.appendChild(entry.bubble);
  decisions.push(entry);
  select(entry);

  if (data.action === "ask_owner") {
    const answer = el("button", { type: "button", className: "link-button", textContent: "Answer as the owner" });
    answer.addEventListener("click", () => {
      select(entry, { open: true });
      panelBody.querySelector("textarea")?.focus();
    });
    addNote("The bot asked the owner.", { button: answer });
  } else if (data.action === "handoff") {
    addNote("In the real shop, a staff member would take over this chat now. You can keep chatting to try something else.");
  }
  scrollToEnd(messagesEl.lastElementChild);
}

function addStaffMessage(text) {
  const li = el("li", { className: "message staff" },
    el("span", { className: "sender", textContent: "The Plug team" }),
    el("span", { className: "text", textContent: text }));
  messagesEl.appendChild(li);
  scrollToEnd(li);
}

// --- The decision panel -------------------------------------------------------------------------

function select(entry, { open = false } = {}) {
  decisions.forEach((d) => d.bubble.classList.toggle("selected", d === entry));
  renderPanel(entry);
  if (open) panel.classList.add("open"); // only matters on phones, where the panel is a sheet
}

function renderPanel(entry) {
  const { data } = entry;
  const action = ACTIONS[data.action];
  const parts = [
    el("p", {}, el("span", { className: `badge badge-${data.action}`, textContent: action.label })),
    el("p", { textContent: action.explain }),
  ];

  if (data.action === "ask_owner") parts.push(ownerSection(entry));

  parts.push(el("h3", { textContent: "Knowledge used" }));
  if (data.sources.length) {
    for (const source of data.sources) {
      parts.push(el("details", { className: "source" },
        el("summary", { textContent: source.id }),
        el("pre", { textContent: source.text })));
    }
  } else {
    parts.push(el("p", { className: "muted", textContent: "No public knowledge-base entries." }));
  }
  if (data.internal_rules_used) {
    const n = data.internal_rules_used;
    parts.push(el("p", { className: "muted", textContent:
      `Also followed ${n} internal rule${n > 1 ? "s" : ""}: the shop's private policies, which guide ` +
      "the bot but never appear in replies. They're hidden in this demo." }));
  }

  panelBody.replaceChildren(...parts);
}

// "Play the owner": the visitor answers the bot's question, and the answer appears in the chat as a
// message from the team. It joins the history as a staff turn, so the bot knows it from then on.
function ownerSection(entry) {
  const section = el("section", { className: "owner" },
    el("h3", { textContent: "Question sent to the owner" }),
    el("blockquote", { textContent: entry.data.question_for_owner }));

  if (entry.ownerAnswer) {
    section.append(
      el("p", {}, el("strong", { textContent: "You answered as the owner: " }), entry.ownerAnswer),
      learningNote());
    return section;
  }

  const textarea = el("textarea", { rows: 3, maxLength: MAX_CHARS, placeholder: "Type the owner's answer…" });
  const submit = el("button", { type: "submit", textContent: "Send as the owner" });
  const ownerForm = el("form", { className: "owner-form" },
    el("label", { textContent: "Play the owner: how would you answer?" }), textarea, submit);
  ownerForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = textarea.value.trim();
    if (!text) return;
    entry.ownerAnswer = text;
    addStaffMessage(text);
    history.push({ role: "staff", text });
    renderPanel(entry);
  });
  section.append(
    el("p", { className: "muted", textContent:
      "In the real product the owner gets this on their phone, and their answer is sent to the customer." }),
    ownerForm);
  return section;
}

function learningNote() {
  return el("p", { className: "muted", textContent:
    "Your answer went to the customer. In the real product, the owner can also save it to the " +
    "knowledge base, so the bot never has to ask the same thing twice. (Nothing is saved in this demo.)" });
}

document.getElementById("panel-close").addEventListener("click", () => panel.classList.remove("open"));

// --- Talking to the API -------------------------------------------------------------------------

function setStatus(state, text) {
  statusEl.className = `status status-${state}`;
  statusEl.textContent = text;
}

function setBusy(value) {
  busy = value;
  const off = busy || !ready;
  input.disabled = off;
  sendButton.disabled = off;
  document.querySelectorAll(".chip").forEach((chip) => (chip.disabled = off));
  if (!off) input.focus();
}

async function send(text) {
  text = text.trim();
  if (!text || busy || !ready) return;

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
      // 429 (limits) and 503 carry a friendly message from the server; anything else gets a generic one.
      const detail = typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.";
      addNote(detail, { error: true });
      return; // the failed message isn't added to the history, so a retry starts clean
    }

    history.push({ role: "customer", text }, { role: "bot", action: data.action, text: data.reply });
    addBotReply(data);
    setStatus("ready", "Online");
  } catch {
    typing.remove();
    addNote("Couldn't reach the assistant. Check your connection and try again.", { error: true });
  } finally {
    setBusy(false);
  }
}

// The free API server sleeps when nobody visits, and the first request wakes it up (about a minute).
// Until it answers, ask again every few seconds. While it's waking, Render may answer with its own
// loading page or not at all; anything other than our {"ok": true} counts as "not yet".
async function apiIsUp() {
  try {
    const response = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(15000) });
    return response.ok && (await response.json()).ok === true;
  } catch {
    return false;
  }
}

async function waitForApi() {
  const start = Date.now();
  setBusy(false); // applies `ready = false`: input disabled
  const showWake = setTimeout(() => {
    wakeEl.hidden = false;
    setStatus("waiting", "Waking up…");
    // The bar fills over the expected wake-up time; it's an estimate, not real progress.
    progressBar.style.transitionDuration = `${WAKE_EXPECTED / 1000}s`;
    requestAnimationFrame(() => (progressBar.style.width = "95%"));
  }, WAKE_SHOW_AFTER);

  while (!(await apiIsUp())) {
    if (Date.now() - start > WAKE_GIVE_UP) {
      clearTimeout(showWake);
      setStatus("down", "Unavailable");
      wakeText.textContent = "The assistant is taking longer than usual to wake up. Please try refreshing the page.";
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }

  clearTimeout(showWake);
  ready = true;
  setStatus("ready", "Online");
  progressBar.style.transitionDuration = "0.3s";
  progressBar.style.width = "100%";
  setTimeout(() => (wakeEl.hidden = true), 400);
  setBusy(false);
}

// --- Wiring -------------------------------------------------------------------------------------

form.addEventListener("submit", (event) => {
  event.preventDefault(); // stop the browser from reloading the page
  send(input.value);
});

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => send(chip.textContent));
});

waitForApi();
