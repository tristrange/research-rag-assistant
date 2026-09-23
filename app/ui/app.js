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

function renderAnswer(answer) {
  const nodes = [];
  const bold = /\*\*([^\n]+?)\*\*/g;
  let position = 0;

  for (const match of answer.matchAll(bold)) {
    nodes.push(document.createTextNode(answer.slice(position, match.index)));
    const strong = document.createElement("strong");
    strong.textContent = match[1];
    nodes.push(strong);
    position = match.index + match[0].length;
  }
  nodes.push(document.createTextNode(answer.slice(position)));
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
  for (const source of sources) {
    const item = document.createElement("details");
    item.className = "source-item";
    const label = document.createElement("summary");
    label.textContent = `${source.document} · page ${source.page} · ${source.section || "unknown"}`;
    const excerpt = document.createElement("p");
    excerpt.className = "source-excerpt";
    excerpt.textContent = source.text;
    item.append(label, excerpt);
    sourceList.append(item);
  }
  sourceCount.textContent = String(sources.length);
  sourcesPanel.hidden = sources.length === 0;
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
  requestStatus.textContent = "Searching and preparing an answer. Verified mode may take several minutes…";

  try {
    const response = await fetch("/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        answer_mode: modeSelect.value,
        document: documentSelect.value || null,
      }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    if (typeof result.answer !== "string" || !Array.isArray(result.sources)) {
      throw new Error("invalid answer response");
    }

    renderAnswer(result.answer);
    answerPanel.hidden = false;
    showSources(result.sources);
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
