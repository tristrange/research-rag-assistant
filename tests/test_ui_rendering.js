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
  replaceChildren(...children) { this.children = children; }
  addEventListener(name, callback) { this.listeners.set(name, callback); }
  click() { this.listeners.get("click")?.(); }
}

function loadUi() {
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
    fetch: async () => ({ ok: true, json: async () => [] }),
  });
  const script = fs.readFileSync(path.join(__dirname, "../app/ui/app.js"), "utf8");
  vm.runInContext(`${script}\nglobalThis.testUi = { showSources, renderAnswer };`, context);
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
