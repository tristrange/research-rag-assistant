const form = document.getElementById("query-form");
const documentSelect = document.getElementById("document");
const libraryStatus = document.getElementById("library-status");
const questionInput = document.getElementById("question");
const askButton = document.getElementById("ask-button");
const requestStatus = document.getElementById("request-status");
const requestError = document.getElementById("request-error");
const answerPanel = document.getElementById("answer-panel");
const answerText = document.getElementById("answer-text");
const copyAnswerButton = document.getElementById("copy-answer-button");
const copyStatus = document.getElementById("copy-status");
const sourcesPanel = document.getElementById("sources-panel");
const sourceCount = document.getElementById("source-count");
const sourceList = document.getElementById("source-list");
const evidencePanel = document.getElementById("evidence-panel");
const evidenceList = document.getElementById("evidence-list");

let hasDocuments = false;
let isSubmitting = false;
let copyRevision = 0;

function resetCopyState() {
  copyRevision += 1;
  copyStatus.textContent = "";
  copyAnswerButton.disabled = !answerText.textContent.trim();
}

async function copyAnswer() {
  if (copyAnswerButton.disabled) return;
  const revision = copyRevision;
  copyStatus.textContent = "";
  copyAnswerButton.disabled = true;
  try {
    if (typeof navigator === "undefined" || typeof navigator.clipboard?.writeText !== "function") {
      throw new Error("clipboard unavailable");
    }
    await navigator.clipboard.writeText(answerText.textContent);
    if (revision === copyRevision) copyStatus.textContent = "Answer copied.";
  } catch {
    if (revision === copyRevision) {
      copyStatus.textContent = "Could not copy. Select the answer and copy it manually.";
    }
  } finally {
    // A previous copy may finish after a new question or answer has arrived.
    if (revision === copyRevision) copyAnswerButton.disabled = false;
  }
}

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
    const page = sourcePages.get(match[0]);
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
    ? new RegExp(`(${labels.map(escapeRegex).join("|")})(?![\\w])`, "g")
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
  resetCopyState();
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
      sourcePages.set(`${source.document}, page ${source.page}`, item);
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

function showEvidence(claims, sources, sourcePages) {
  evidenceList.replaceChildren();
  const labels = {
    this_document_authors: "This paper's authors",
    external_publication: "Cited literature",
    non_study_context: "Context",
  };
  for (const claim of claims) {
    const item = document.createElement("details");
    item.className = "source-item";
    const heading = document.createElement("summary");
    const attribution = document.createElement("span");
    attribution.className = "claim-attribution";
    attribution.textContent = labels[claim.attribution];
    heading.append(attribution, document.createTextNode(claim.text));
    item.append(heading);
    for (const citation of claim.citations) {
      const source = sources[citation.source_index];
      const location = document.createElement("p");
      location.className = "evidence-location";
      const link = document.createElement("a");
      const label = `${source.document}, page ${source.page}`;
      const page = sourcePages.get(label);
      link.textContent = `${label} · ${source.section || "unknown"}`;
      link.href = `#${page.id}`;
      link.addEventListener("click", () => { page.open = true; });
      location.append(link);
      const quote = document.createElement("blockquote");
      quote.className = "evidence-quote";
      quote.textContent = citation.quote;
      item.append(location, quote);
    }
    evidenceList.append(item);
  }
  evidencePanel.hidden = claims.length === 0;
}

function validEvidence(claims, sources) {
  return Array.isArray(claims) && claims.every((claim) =>
    claim && typeof claim.text === "string" &&
    ["this_document_authors", "external_publication", "non_study_context"].includes(claim.attribution) &&
    Array.isArray(claim.citations) && claim.citations.length > 0 &&
    claim.citations.every((citation) => citation &&
      Number.isInteger(citation.source_index) && citation.source_index >= 0 &&
      citation.source_index < sources.length && typeof citation.quote === "string"));
}

async function submitQuestion(event) {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!hasDocuments || isSubmitting || !question) return;

  isSubmitting = true;
  updateSubmitState();
  requestError.hidden = true;
  answerPanel.hidden = true;
  answerText.replaceChildren();
  resetCopyState();
  sourcesPanel.hidden = true;
  sourceList.replaceChildren();
  evidencePanel.hidden = true;
  evidenceList.replaceChildren();
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
        answer_mode: "verified",
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
    const claims = result.claim_evidence ?? [];
    if (!validEvidence(claims, result.sources)) throw new Error("invalid evidence response");
    showEvidence(claims, result.sources, sourcePages);
    renderAnswer(result.answer, sourcePages);
    answerPanel.hidden = false;
    requestStatus.textContent = "Answer ready.";
  } catch (error) {
    requestStatus.textContent = "The request did not complete.";
    if (error instanceof TypeError) {
      requestError.textContent = "Could not connect to the API. Check that the server is running.";
    } else if (error instanceof Error && error.message === "HTTP 429") {
      requestError.textContent = "Another question is still running. Wait for it to finish, then try again.";
    } else {
      requestError.textContent = "The query failed. Check the API logs and local services, then try again.";
    }
    requestError.hidden = false;
  } finally {
    isSubmitting = false;
    updateSubmitState();
  }
}

questionInput.addEventListener("input", updateSubmitState);
form.addEventListener("submit", submitQuestion);
copyAnswerButton.addEventListener("click", copyAnswer);
resetCopyState();
loadDocuments();
