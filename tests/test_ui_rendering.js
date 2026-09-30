const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

class Element {
  constructor(tagName) {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.listeners = new Map();
    this.classList = { remove() {} };
    this.value = "";
    this._textContent = null;
  }

  get textContent() {
    return this._textContent ?? this.children.map((child) => child.textContent).join("");
  }
  set textContent(value) {
    this._textContent = value;
    this.children = [];
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this._textContent = null; this.children = children; }
  addEventListener(name, callback) { this.listeners.set(name, callback); }
  click() { return this.listeners.get("click")?.(); }
}

function loadUi(options = {}) {
  const elements = new Map();
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, new Element("div"));
      return elements.get(id);
    },
    createElement: (name) => new Element(name),
    createTextNode: (textContent) => ({ nodeType: 3, textContent }),
  };
  const context = vm.createContext({
    document,
    fetch: options.fetch ?? (async () => ({ ok: true, json: async () => [] })),
    ...(options.navigator ? { navigator: options.navigator } : {}),
  });
  const script = fs.readFileSync(path.join(__dirname, "../app/ui/app.js"), "utf8");
  vm.runInContext(`${script}\nglobalThis.testUi = { showSources, renderAnswer, showEvidence, validEvidence };`, context);
  return { ...context.testUi, elements };
}

test("page references open all returned passages from that document and page", () => {
  const { showSources, renderAnswer, elements } = loadUi();
  const pages = showSources([
    { document: "study.v2.pdf", page: 4, section: "Results", text: "First passage" },
    { document: "study.v2.pdf", page: 4, section: "Discussion", text: "Second passage" },
    { document: "other.pdf", page: 4, section: "Results", text: "Other paper" },
  ]);
  renderAnswer("**Result** (study.v2.pdf, page 4); other.pdf, page 4.", pages);

  const cards = elements.get("source-list").children;
  assert.equal(cards.length, 2);
  assert.deepEqual(cards[0].children.slice(1).map((node) => node.textContent), [
    "First passage", "Second passage",
  ]);
  assert.equal(elements.get("source-count").textContent, "3");

  const answer = elements.get("answer-text").children;
  assert.equal(answer.find((node) => node.tagName === "STRONG").textContent, "Result");
  const links = answer.filter((node) => node.tagName === "A");
  assert.deepEqual(links.map((link) => link.href), ["#source-page-1", "#source-page-2"]);
  links[0].click();
  assert.equal(cards[0].open, true);
  assert.notEqual(cards[1].open, true);
});

test("unreturned or partial page references remain plain text", () => {
  const { showSources, renderAnswer, elements } = loadUi();
  const pages = showSources([
    { document: "study.pdf", page: 9, section: "Results", text: "Evidence" },
  ]);
  renderAnswer("study.pdf, page 90; oldstudy.pdf, page 9; study.pdf, page 8; study.pdf, page 9", pages);

  const nodes = elements.get("answer-text").children;
  const links = nodes.filter((node) => node.tagName === "A");
  assert.equal(links.length, 1);
  assert.equal(links[0].textContent, "study.pdf, page 9");
  assert.match(nodes[0].textContent, /study\.pdf, page 90; oldstudy\.pdf, page 9; study\.pdf, page 8/);
});

test("case-distinct filenames link only to their own passages", () => {
  const { showSources, renderAnswer, elements } = loadUi();
  const pages = showSources([
    { document: "Study.pdf", page: 4, section: "Results", text: "Uppercase paper" },
    { document: "study.pdf", page: 4, section: "Results", text: "Lowercase paper" },
  ]);
  renderAnswer("Study.pdf, page 4; study.pdf, page 4; STUDY.pdf, page 4", pages);

  const links = elements.get("answer-text").children.filter((node) => node.tagName === "A");
  assert.deepEqual(links.map((link) => link.href), ["#source-page-1", "#source-page-2"]);
  assert.match(elements.get("answer-text").textContent, /STUDY\.pdf, page 4$/);
});

test("a page reference inside bold text remains bold and clickable", () => {
  const { showSources, renderAnswer, elements } = loadUi();
  const pages = showSources([
    { document: "study.pdf", page: 9, section: "Results", text: "Evidence" },
  ]);
  renderAnswer("See **study.pdf, page 9** for context.", pages);

  const bold = elements.get("answer-text").children.find((node) => node.tagName === "STRONG");
  assert.equal(bold.children.find((node) => node.tagName === "A").href, "#source-page-1");
});

test("source and answer text are inserted as text, never interpreted as markup", () => {
  const { showSources, renderAnswer, elements } = loadUi();
  const pages = showSources([
    { document: "study.pdf", page: 1, section: "Results", text: "<img src=x>" },
  ]);
  renderAnswer("<script>alert(1)</script> study.pdf, page 1", pages);

  assert.equal(elements.get("source-list").children[0].children[1].textContent, "<img src=x>");
  assert.equal(elements.get("answer-text").children[0].textContent, "<script>alert(1)</script> ");
  assert.equal(elements.get("answer-text").children.some((node) => node.tagName === "SCRIPT"), false);
});

test("copy includes rendered emphasis, line breaks and citations without HTML or source excerpts", async () => {
  const copied = [];
  const { showSources, renderAnswer, elements } = loadUi({
    navigator: { clipboard: { writeText: async (text) => { copied.push(text); } } },
  });
  const button = elements.get("copy-answer-button");
  assert.equal(button.disabled, true);
  const pages = showSources([
    { document: "study.pdf", page: 4, section: "Results", text: "Source excerpt" },
  ]);
  renderAnswer("**Result**: *improved*.\nSee study.pdf, page 4. <img src=x>", pages);
  const copying = button.click();
  assert.equal(button.disabled, true);
  await copying;
  assert.deepEqual(copied, ["Result: improved.\nSee study.pdf, page 4. <img src=x>"]);
  assert.equal(elements.get("copy-status").textContent, "Answer copied.");
  assert.equal(button.disabled, false);
  const link = elements.get("answer-text").children.find((node) => node.tagName === "A");
  link.click();
  assert.equal(elements.get("source-list").children[0].open, true);
});

test("clipboard rejection preserves the answer and allows a retry", async () => {
  let attempts = 0;
  const { renderAnswer, elements } = loadUi({
    navigator: { clipboard: { writeText: async () => {
      attempts += 1;
      if (attempts === 1) throw new Error("permission denied");
    } } },
  });
  renderAnswer("**Keep this answer**", new Map());
  const button = elements.get("copy-answer-button");
  await button.click();
  assert.match(elements.get("copy-status").textContent, /Could not copy/);
  assert.equal(elements.get("answer-text").textContent, "Keep this answer");
  assert.equal(button.disabled, false);
  await button.click();
  assert.equal(elements.get("copy-status").textContent, "Answer copied.");
});

test("unavailable clipboard APIs report a manual-copy fallback", async () => {
  for (const navigator of [undefined, {}, { clipboard: {} }]) {
    const { renderAnswer, elements } = loadUi({ navigator });
    renderAnswer("Answer", new Map());
    await elements.get("copy-answer-button").click();
    assert.match(elements.get("copy-status").textContent, /copy it manually/);
    assert.equal(elements.get("answer-text").textContent, "Answer");
    assert.equal(elements.get("copy-answer-button").disabled, false);
  }
});

test("a new question clears copy feedback and ignores an old copy completion", async () => {
  let finishCopy;
  let finishQuery;
  const { elements, renderAnswer } = loadUi({
    navigator: { clipboard: { writeText: () => new Promise((resolve) => { finishCopy = resolve; }) } },
    fetch: async (url) => {
      if (url === "/documents") return { ok: true, json: async () => ["study.pdf"] };
      return new Promise((resolve) => { finishQuery = resolve; });
    },
  });
  await new Promise(setImmediate);
  renderAnswer("Old answer", new Map());
  elements.get("copy-status").textContent = "Previous copy feedback";
  const copying = elements.get("copy-answer-button").click();
  elements.get("question").value = "Next question";
  const submitting = elements.get("query-form").listeners.get("submit")({ preventDefault() {} });
  assert.equal(elements.get("copy-status").textContent, "");
  assert.equal(elements.get("copy-answer-button").disabled, true);
  assert.equal(elements.get("answer-panel").hidden, true);
  finishCopy();
  await copying;
  assert.equal(elements.get("copy-status").textContent, "");
  assert.equal(elements.get("copy-answer-button").disabled, true);
  finishQuery({ ok: true, json: async () => ({ answer: "New answer", sources: [] }) });
  await submitting;
  assert.equal(elements.get("answer-text").textContent, "New answer");
  assert.equal(elements.get("copy-status").textContent, "");
  assert.equal(elements.get("copy-answer-button").disabled, false);
});

test("a replacement answer ignores an old copy rejection and resets success feedback", async () => {
  let rejectCopy;
  let firstCopy = true;
  const { renderAnswer, elements } = loadUi({
    navigator: { clipboard: { writeText: () => {
      if (!firstCopy) return Promise.resolve();
      firstCopy = false;
      return new Promise((resolve, reject) => { rejectCopy = reject; });
    } } },
  });
  renderAnswer("Old answer", new Map());
  const copying = elements.get("copy-answer-button").click();
  renderAnswer("New answer", new Map());
  rejectCopy(new Error("permission denied"));
  await copying;
  assert.equal(elements.get("copy-status").textContent, "");
  assert.equal(elements.get("copy-answer-button").disabled, false);
  await elements.get("copy-answer-button").click();
  assert.equal(elements.get("copy-status").textContent, "Answer copied.");
  renderAnswer("", new Map());
  assert.equal(elements.get("copy-status").textContent, "");
  assert.equal(elements.get("copy-answer-button").disabled, true);
});

test("claim evidence shows exact excerpts and attribution separately from all retrieved text", () => {
  const { showSources, showEvidence, elements } = loadUi();
  const sources = [
    { document: "a.pdf", page: 2, section: "results", text: "Selected excerpt plus other context." },
    { document: "a.pdf", page: 2, section: "discussion", text: "Second chunk on the same page." },
    { document: "b.pdf", page: 2, section: "references", text: "<img src=x> Cited study." },
  ];
  const pages = showSources(sources);
  showEvidence([
    { text: "First finding", attribution: "this_document_authors", citations: [{ source_index: 1, quote: "Second chunk" }] },
    { text: "<script>Claim</script>", attribution: "external_publication", citations: [{ source_index: 2, quote: "<img src=x>" }] },
  ], sources, pages);
  const cards = elements.get("evidence-list").children;
  assert.equal(elements.get("evidence-panel").hidden, false);
  assert.equal(cards[0].children[0].textContent, "This paper's authorsFirst finding");
  assert.equal(cards[0].children[2].textContent, "Second chunk");
  assert.equal(cards[1].children[0].textContent, "Cited literature<script>Claim</script>");
  assert.equal(cards[1].children[2].textContent, "<img src=x>");
  assert.equal(cards[1].children[2].tagName, "BLOCKQUOTE");
  const link = cards[1].children[1].children[0];
  assert.equal(link.href, "#source-page-2");
  link.click();
  assert.equal(elements.get("source-list").children[1].open, true);
  assert.equal(elements.get("source-count").textContent, "3");
  showEvidence([], sources, pages);
  assert.equal(elements.get("evidence-panel").hidden, true);
  assert.equal(elements.get("evidence-list").children.length, 0);
});

test("evidence payloads reject invalid source indexes and unknown attribution", () => {
  const { validEvidence } = loadUi();
  const sources = [{ document: "study.pdf", page: 2, text: "Evidence" }];
  const claim = { text: "Finding", attribution: "this_document_authors", citations: [{ source_index: 0, quote: "Evidence" }] };
  assert.equal(validEvidence([claim], sources), true);
  for (const source_index of [-1, 1, 0.5, "0", null]) {
    assert.equal(validEvidence([{ ...claim, citations: [{ source_index, quote: "Evidence" }] }], sources), false);
  }
  assert.equal(validEvidence([{ ...claim, attribution: "verified fact" }], sources), false);
  assert.equal(validEvidence([{ ...claim, citations: [] }], sources), false);
  assert.equal(validEvidence(null, sources), false);
});

test("query submission clears previous evidence and displays the new API selections", async () => {
  let finishQuery;
  const { showSources, showEvidence, elements } = loadUi({
    fetch: async (url) => url === "/documents"
      ? { ok: true, json: async () => ["study.pdf"] }
      : new Promise((resolve) => { finishQuery = resolve; }),
  });
  await new Promise(setImmediate);
  const sources = [{ document: "study.pdf", page: 2, section: "results", text: "First. Second." }];
  const old = [{ text: "Old", attribution: "this_document_authors", citations: [{ source_index: 0, quote: "First." }] }];
  showEvidence(old, sources, showSources(sources));
  elements.get("question").value = "Next question";
  const submitting = elements.get("query-form").listeners.get("submit")({ preventDefault() {} });
  assert.equal(elements.get("evidence-panel").hidden, true);
  assert.equal(elements.get("evidence-list").children.length, 0);
  const claims = [{ ...old[0], text: "New", citations: [{ source_index: 0, quote: "Second." }] }];
  finishQuery({ ok: true, json: async () => ({ answer: "New", sources, claim_evidence: claims }) });
  await submitting;
  assert.equal(elements.get("evidence-panel").hidden, false);
  assert.equal(elements.get("evidence-list").children[0].children[2].textContent, "Second.");
  assert.equal(elements.get("answer-text").textContent, "New");
});

test("service errors show API guidance as text and allow a successful retry", async () => {
  const message = "Ollama could not complete the request. <img src=x>";
  let attempts = 0;
  const { elements } = loadUi({
    fetch: async (url) => {
      if (url === "/documents") return { ok: true, json: async () => ["study.pdf"] };
      attempts += 1;
      if (attempts === 1) return { ok: false, status: 503, json: async () => ({ detail: { code: "model_unavailable", message } }) };
      return { ok: true, json: async () => ({ answer: "Recovered", sources: [] }) };
    },
  });
  await new Promise(setImmediate);
  elements.get("question").value = "Question";
  const submit = elements.get("query-form").listeners.get("submit");
  await submit({ preventDefault() {} });
  assert.equal(elements.get("request-error").hidden, false);
  assert.equal(elements.get("request-error").textContent, message);
  assert.equal(elements.get("request-error").children.length, 0);
  assert.equal(elements.get("request-status").textContent, "The request did not complete.");
  assert.equal(elements.get("answer-panel").hidden, true);
  assert.equal(elements.get("evidence-panel").hidden, true);
  assert.equal(elements.get("ask-button").disabled, false);
  await submit({ preventDefault() {} });
  assert.equal(elements.get("request-error").hidden, true);
  assert.equal(elements.get("answer-text").textContent, "Recovered");
  assert.equal(elements.get("ask-button").disabled, false);
});

test("paper-list failures show service guidance and keep querying disabled", async () => {
  const { elements } = loadUi({
    fetch: async () => ({ ok: false, status: 503, json: async () => ({
      detail: { code: "database_error", message: "Check PostgreSQL and initialize the database." },
    }) }),
  });
  await new Promise(setImmediate);
  assert.match(elements.get("library-status").textContent, /Check PostgreSQL/);
  assert.match(elements.get("library-status").textContent, /Reload this page/);
  assert.equal(elements.get("ask-button").disabled, true);
});

test("busy, legacy and non-JSON API errors have useful fallbacks", async () => {
  const responses = [
    { ok: false, status: 429, json: async () => ({ detail: "Busy" }) },
    { ok: false, status: 500, json: async () => { throw new SyntaxError("private upstream body"); } },
    { ok: false, status: 500, json: async () => ({ detail: "private upstream body" }) },
    { ok: false, status: 500, json: async () => ({ detail: { code: "bad", message: 123 } }) },
  ];
  for (const response of responses) {
    const { elements } = loadUi({
      fetch: async (url) => url === "/documents"
        ? { ok: true, json: async () => ["study.pdf"] }
        : response,
    });
    await new Promise(setImmediate);
    elements.get("question").value = "Question";
    await elements.get("query-form").listeners.get("submit")({ preventDefault() {} });
    const error = elements.get("request-error").textContent;
    assert.match(error, response.status === 429 ? /Another question is still running/ : /API request failed/);
    assert.doesNotMatch(error, /private upstream/);
    assert.equal(elements.get("ask-button").disabled, false);
  }
});
