let card = null;
const notesById = {};
let trashArmed = false;
let asking = false;

async function load() {
  const r = await fetch("/api/card");
  card = await r.json();
  draw();
}

function draw() {
  trashArmed = false;
  const el = document.getElementById("root");
  const st = document.getElementById("stats");
  st.textContent = (card.labeled ?? 0) + " labeled · " + (card.trashed ?? 0) + " trash · " + (card.left ?? 0) + " left";
  if (card.error) {
    el.innerHTML = '<p class="err"></p>';
    el.querySelector(".err").textContent = card.error;
    return;
  }
  if (card.done) {
    el.innerHTML = '<div class="empty"><h1>Queue is empty.</h1><p>Labeled this session: '
      + (card.labeled ?? 0) + "</p></div>";
    return;
  }
  const rec = card.recording;
  el.innerHTML = [
    '<div class="desk">',
    '<section class="pane tape">',
    '<div class="tape-top">',
    '<p class="meta"></p>',
    "<h1></h1>",
    '<div class="chips" id="chips"></div>',
    '<p class="blurb" id="blurb"></p>',
    "</div>",
    '<pre class="transcript" id="transcript" hidden tabindex="0"></pre>',
    '<div class="tape-foot">',
    '<p class="guess" id="guess"></p>',
    '<textarea class="note" id="note" placeholder="Who was there, where, what this actually is…"></textarea>',
    '<div class="folders" id="folders"></div>',
    '<div class="more">',
    '<button class="skip" id="skip">Skip <kbd>S</kbd></button>',
    '<button class="deep" id="deep">Full transcript <kbd>D</kbd></button>',
    '<button class="trash" id="trash">Trash <kbd>T</kbd></button>',
    "</div></div></section>",
    '<section class="pane harness">',
    '<div class="harness-head"><h2>Filing harness</h2><span class="model"></span><span class="cannot">cannot file</span></div>',
    '<div class="chatlog" id="chatlog"></div>',
    '<div class="starters" id="starters"></div>',
    '<form class="chatform" id="chatform"><input id="chatq" autocomplete="off" placeholder="Who, where, when — it cannot file"/>',
    '<button type="submit" id="send">Send</button></form>',
    "</section></div>",
  ].join("");
  el.querySelector(".meta").textContent = rec.when + " · " + rec.mins + " min";
  el.querySelector("h1").textContent = rec.title;
  el.querySelector(".harness-head .model").textContent = card.chat_model || "DeepSeek";
  fillChips();
  fillBlurb();
  fillTranscript();
  fillGuess();
  fillFolders();
  const note = el.querySelector("#note");
  note.value = notesById[rec.id] || "";
  note.addEventListener("input", () => { notesById[rec.id] = note.value; });
  renderLog(card.chat || []);
  fillStarters();
  el.querySelector("#chatform").onsubmit = (ev) => { ev.preventDefault(); ask(); };
  el.querySelector("#skip").onclick = () => skip();
  el.querySelector("#deep").onclick = () => deepen();
  el.querySelector("#trash").onclick = () => trashClick(el.querySelector("#trash"));
}

function fillChips() {
  const rec = card.recording;
  const chips = document.getElementById("chips");
  const seen = new Set();
  const labels = [...(rec.places || []), ...(rec.speakers || [])];
  labels.forEach((p) => {
    const key = String(p).toLowerCase();
    if (!key || seen.has(key) || seen.size >= 8) return;
    seen.add(key);
    const s = document.createElement("span");
    s.className = "chip";
    s.textContent = p;
    chips.appendChild(s);
  });
}

function fillBlurb() {
  const blurb = document.getElementById("blurb");
  const rec = card.recording || {};
  let preview = card.deep_text || card.body_preview || "";
  const title = rec.title || "";
  if (title && preview.replace(/\s+/g, " ").toLowerCase().startsWith(title.replace(/\s+/g, " ").toLowerCase())) {
    preview = preview.slice(title.length).replace(/^[\s:–—-]+/, "");
  }
  preview = preview.replace(/^#+\s*core synopsis\s*/i, "");
  if (preview) {
    blurb.textContent = preview;
  } else blurb.remove();
}

function fillTranscript() {
  const el = document.getElementById("transcript");
  const deep = document.getElementById("deep");
  const tape = document.querySelector(".tape");
  const text = card.transcript || "";
  if (!el) return;
  if (text) {
    el.hidden = false;
    if (tape) tape.classList.add("reading");
    el.textContent = text;
    const n = card.utterances;
    const chars = card.transcript_chars || text.length;
    el.setAttribute(
      "data-label",
      (n ? n + " utterances · " : "") + chars.toLocaleString() + " chars",
    );
    if (deep) deep.textContent = "Transcript";
  } else {
    el.hidden = true;
    el.textContent = "";
    if (tape) tape.classList.remove("reading");
    if (card.deep && deep) deep.textContent = "No transcript yet";
  }
}

function liftGuess() {
  return (card.guess && card.guess.folders && card.guess.folders[0]) || null;
}

function fillGuess() {
  const g = document.getElementById("guess");
  if (!g) return;
  const lift = liftGuess();
  const harness = card.harness_guess || null;
  g.replaceChildren();
  if (lift && harness && lift.folder_id !== harness.folder_id) {
    g.append("lift leans ");
    const a = document.createElement("b");
    a.textContent = lift.name || "?";
    g.append(a, " — harness leans ");
    const b = document.createElement("b");
    b.textContent = harness.name || "?";
    g.append(b);
    return;
  }
  const one = harness || lift;
  if (one) {
    const why = ((lift && lift.why) || []).slice(0, 4).map((w) => w.term).join(", ");
    g.append(harness ? "harness leans " : "model leans ");
    const b = document.createElement("b");
    b.textContent = one.name || "?";
    g.append(b);
    if (why && !harness) g.append(" — " + why);
    return;
  }
  g.textContent = "no guess — you pick";
}

function fillFolders() {
  const box = document.getElementById("folders");
  if (!box) return;
  box.replaceChildren();
  const lift = liftGuess();
  const harness = card.harness_guess || null;
  (card.folders || []).forEach((f, i) => {
    const b = document.createElement("button");
    const isYes = lift && f.id === lift.folder_id;
    const isHarness = harness && f.id === harness.folder_id;
    b.className = (isYes ? "yes" : "") + (isHarness ? " harness-pick" : "");
    b.style.borderLeftColor = f.color || "#888";
    b.textContent = (isYes ? "Yes — " : "") + f.name + (isHarness && !isYes ? " · harness" : "");
    const k = document.createElement("kbd");
    k.textContent = isYes ? "Y" : String(i + 1);
    b.appendChild(k);
    b.onclick = () => label(f.id);
    box.appendChild(b);
  });
}

function renderLog(messages) {
  const log = document.getElementById("chatlog");
  if (!log) return;
  log.replaceChildren();
  if (!messages.length) {
    const q = document.createElement("p");
    q.className = "quiet";
    q.textContent = "Talk through who / where / when. This log cannot file.";
    log.appendChild(q);
  }
  messages.forEach((m) => appendMessage(log, m));
  log.scrollTop = log.scrollHeight;
}

function appendMessage(log, m) {
  const quiet = log.querySelector(".quiet");
  if (quiet) quiet.remove();
  const w = document.createElement("div");
  w.className = "who";
  w.textContent = m.role === "user" ? "You" : "Harness";
  log.appendChild(w);
  if (m.thinking) {
    const d = document.createElement("details");
    d.className = "think";
    d.open = true;
    const s = document.createElement("summary");
    s.textContent = "thinking";
    const p = document.createElement("div");
    p.textContent = m.thinking;
    d.appendChild(s);
    d.appendChild(p);
    log.appendChild(d);
  }
  if (m.text) {
    const t = document.createElement("div");
    t.className = "chatrow";
    t.textContent = m.text;
    log.appendChild(t);
  }
}

function fillStarters() {
  const box = document.getElementById("starters");
  ["Which folder?", "Who is this with?", "Is the clock title a lie?"].forEach((label) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.onclick = () => ask(label);
    box.appendChild(b);
  });
}

function noteText() {
  const t = document.getElementById("note");
  const v = t ? t.value : (card && card.recording ? notesById[card.recording.id] : "") || "";
  if (card && card.recording) notesById[card.recording.id] = v;
  return v.trim();
}

async function ask(preset) {
  const q = document.getElementById("chatq");
  const text = (preset || (q && q.value) || "").trim();
  if (!text || asking || !card || !card.recording) return;
  asking = true;
  if (q) q.value = "";
  const send = document.getElementById("send");
  if (send) send.disabled = true;
  const log = document.getElementById("chatlog");
  appendMessage(log, { role: "user", text });
  const think = document.createElement("details");
  think.className = "think";
  think.open = true;
  const sum = document.createElement("summary");
  sum.textContent = "thinking";
  const thinkBody = document.createElement("div");
  think.appendChild(sum);
  think.appendChild(thinkBody);
  const who = document.createElement("div");
  who.className = "who";
  who.textContent = "Harness";
  log.appendChild(who);
  log.appendChild(think);
  const row = document.createElement("div");
  row.className = "chatrow";
  log.appendChild(row);
  log.scrollTop = log.scrollHeight;
  let thinking = "";
  let reply = "";
  try {
    const r = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recording_id: card.recording.id,
        message: text,
        notes: noteText(),
      }),
    });
    if (!r.ok || !r.body) {
      row.textContent = "Harness HTTP " + r.status;
      return;
    }
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() || "";
      for (const part of parts) {
        const line = part.split("\n").find((l) => l.startsWith("data:"));
        if (!line) continue;
        let ev;
        try { ev = JSON.parse(line.slice(5).trim()); } catch { continue; }
        if (ev.type === "thinking" && ev.delta) {
          thinking += ev.delta;
          thinkBody.textContent = thinking;
        } else if (ev.type === "text" && ev.delta) {
          reply += ev.delta;
          row.textContent = reply;
        } else if (ev.type === "error") {
          reply = ev.text || "Harness failed.";
          row.textContent = reply;
        } else if (ev.type === "done") {
          reply = ev.text || reply;
          thinking = ev.thinking || thinking;
          row.textContent = reply;
          thinkBody.textContent = thinking;
          if (!thinking) think.remove();
          if (ev.suggestion) card.harness_guess = ev.suggestion;
          fillGuess();
          fillFolders();
        }
        log.scrollTop = log.scrollHeight;
      }
    }
  } catch (err) {
    row.textContent = "Harness failed: " + err;
  } finally {
    asking = false;
    if (send) send.disabled = false;
    if (q) q.focus();
  }
}

function trashClick(btn) {
  if (!trashArmed) {
    trashArmed = true;
    btn.classList.add("armed");
    btn.textContent = "Trash for real?";
    const k = document.createElement("kbd");
    k.textContent = "T";
    btn.appendChild(k);
    return;
  }
  trashArmed = false;
  trash();
}

async function label(folderId) {
  document.querySelectorAll("button").forEach((b) => b.disabled = true);
  const r = await fetch("/api/label", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recording_id: card.recording.id, folder_id: folderId, notes: noteText() }),
  });
  card = await r.json();
  draw();
}

async function skip() {
  trashArmed = false;
  const r = await fetch("/api/skip", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recording_id: card.recording && card.recording.id, notes: noteText() }),
  });
  card = await r.json();
  draw();
}

async function deepen() {
  const deep = document.getElementById("deep");
  if (deep) {
    deep.disabled = true;
    deep.textContent = "Loading transcript…";
  }
  const r = await fetch("/api/deepen", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recording_id: card.recording.id, notes: noteText() }),
  });
  card = await r.json();
  draw();
  const el = document.getElementById("transcript");
  if (el && !el.hidden) el.focus();
}

async function trash() {
  document.querySelectorAll("button").forEach((b) => b.disabled = true);
  const r = await fetch("/api/trash", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recording_id: card.recording.id, notes: noteText() }),
  });
  card = await r.json();
  draw();
}

document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || !card || !card.recording) return;
  if (e.key === "s" || e.key === "S") { skip(); return; }
  if (e.key === "d" || e.key === "D") { deepen(); return; }
  if (e.key === "t" || e.key === "T") {
    const btn = document.getElementById("trash");
    if (btn) trashClick(btn);
    return;
  }
  if ((e.key === "y" || e.key === "Y") && liftGuess()) {
    label(liftGuess().folder_id);
    return;
  }
  const n = parseInt(e.key, 10);
  if (n >= 1 && card.folders && card.folders[n - 1]) label(card.folders[n - 1].id);
});

load();
