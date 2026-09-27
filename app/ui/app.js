const form = document.getElementById("query-form");
const documentSelect = document.getElementById("document");
const libraryStatus = document.getElementById("library-status");
const questionInput = document.getElementById("question");
const modeSelect = document.getElementById("answer-mode");
const askButton = document.getElementById("ask-button");
const requestStatus = document.getElementById("request-status");
const requestError = document.getElementById("request-error");
const answerPanel = document.getElementById("answer-panel");
const answerText = document.getElementById("answer-text");
const sourcesPanel = document.getElementById("sources-panel");
const sourceCount = document.getElementById("source-count");
const sourceList = document.getElementById("source-list");

let hasDocuments = false;
let isSubmitting = false;

function updateSubmitState() {
  askButton.disabled = !hasDocuments || isSubmitting || !questionInput.value.trim();
}

function escapeRegex(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function appendLinkedText(nodes, text, sourcePages, references) {
  if (!references) {
    nodes.push(document.createTextNode(text));
    return;
  }

  let position = 0;
  for (const match of text.matchAll(references)) {
    // A filename may be a suffix of another word; only link a complete reference.
    if (match.index > 0 && /[\w.-]/.test(text[match.index - 1])) continue;
    nodes.push(document.createTextNode(text.slice(position, match.index)));
    const page = sourcePages.get(match[0].toLowerCase());
    const link = document.createElement("a");
    link.href = `#${page.id}`;
    link.textContent = match[0];
    link.addEventListener("click", () => { page.open = true; });
    nodes.push(link);
    position = match.index + match[0].length;
  }
  nodes.push(document.createTextNode(text.slice(position)));
}

function renderAnswer(answer, sourcePages) {
  const nodes = [];
  const labels = [...sourcePages.keys()].sort((left, right) => right.length - left.length);
  const references = labels.length
    ? new RegExp(`(${labels.map(escapeRegex).join("|")})(?![\\w])`, "gi")
    : null;
  const emphasis = /(\*\*|\*)([^\s*](?:[^*\n]*[^\s*])?)\1/g;
  let position = 0;
  for (const match of answer.matchAll(emphasis)) {
    appendLinkedText(nodes, answer.slice(position, match.index), sourcePages, references);
    const element = document.createElement(match[1] === "**" ? "strong" : "em");
    const content = [];
    appendLinkedText(content, match[2], sourcePages, references);
    element.append(...content);
    nodes.push(element);
    position = match.index + match[0].length;
  }
  appendLinkedText(nodes, answer.slice(position), sourcePages, references);
  answerText.replaceChildren(...nodes);
}

async function loadDocuments() {
  try {
    const response = await fetch("/documents");
    if (!response.ok) throw new Error("document request failed");
    const filenames = await response.json();
    if (!Array.isArray(filenames) || !filenames.every((name) => typeof name === "string")) {
      throw new Error("invalid document response");
    }

    for (const filename of filenames) {
      const option = document.createElement("option");
      option.value = filename;
      option.textContent = filename;
      documentSelect.append(option);
    }
    hasDocuments = filenames.length > 0;
    documentSelect.disabled = !hasDocuments;
    libraryStatus.textContent = hasDocuments
      ? `${filenames.length} indexed ${filenames.length === 1 ? "paper" : "papers"} available.`
      : "No PDFs are indexed yet. Index a PDF, then reload this page.";
  } catch {
    libraryStatus.textContent = "Could not load the paper list. Check the database and reload this page.";
  } finally {
    updateSubmitState();
  }
}

function showSources(sources) {
  sourceList.replaceChildren();
  const groups = new Map();
  const sourcePages = new Map();
  for (const source of sources) {
    const key = JSON.stringify([source.document, source.page]);
    let group = groups.get(key);
    if (!group) {
      const item = document.createElement("details");
      item.className = "source-item";
      item.id = `source-page-${groups.size + 1}`;
      const label = document.createElement("summary");
      label.textContent = `${source.document} · page ${source.page}`;
      item.append(label);
      sourceList.append(item);
      group = { item, sections: new Set(), label };
      groups.set(key, group);
      sourcePages.set(`${source.document}, page ${source.page}`.toLowerCase(), item);
    }
    group.sections.add(source.section || "unknown");
    const excerpt = document.createElement("p");
    excerpt.className = "source-excerpt";
    excerpt.textContent = source.text;
    group.item.append(excerpt);
  }
  for (const [key, group] of groups) {
    const [filename, page] = JSON.parse(key);
    group.label.textContent = `${filename} · page ${page} · ${[...group.sections].join(", ")}`;
  }
  sourceCount.textContent = String(sources.length);
  sourcesPanel.hidden = sources.length === 0;
  return sourcePages;
}

async function submitQuestion(event) {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!hasDocuments || isSubmitting || !question) return;

  isSubmitting = true;
  updateSubmitState();
  requestError.hidden = true;
  answerPanel.hidden = true;
  sourcesPanel.hidden = true;
  sourceList.replaceChildren();
  requestStatus.classList.remove("is-idle");
  let scope = "relevant";
  if (documentSelect.value === "__each__") scope = "each";
  if (documentSelect.value === "__each_query__") scope = "each_query";
  const eachPaper = scope !== "relevant";
  requestStatus.textContent = eachPaper
    ? "Searching each indexed paper separately. This can take several minutes…"
    : "Searching and preparing an answer. Verified mode may take several minutes…";

  try {
    const response = await fetch("/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        answer_mode: modeSelect.value,
        scope,
        document: eachPaper ? null : documentSelect.value || null,
      }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    if (typeof result.answer !== "string" || !Array.isArray(result.sources)) {
      throw new Error("invalid answer response");
    }

    const sourcePages = showSources(result.sources);
    renderAnswer(result.answer, sourcePages);
    answerPanel.hidden = false;
    requestStatus.textContent = "Answer ready.";
  } catch (error) {
    requestStatus.textContent = "The request did not complete.";
    requestError.textContent = error instanceof TypeError
      ? "Could not connect to the API. Check that the server is running."
      : "The query failed. Check the API logs and local services, then try again.";
    requestError.hidden = false;
  } finally {
    isSubmitting = false;
    updateSubmitState();
  }
}

questionInput.addEventListener("input", updateSubmitState);
form.addEventListener("submit", submitQuestion);
loadDocuments();
