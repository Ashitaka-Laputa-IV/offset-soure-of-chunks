interface Chunk {
  id: string;
  source: string;
  start: number;
  end: number;
  line_start: number;
  line_end: number;
  heading: string;
  chars: number;
  content: string;
}

const CHUNKS_URL = "../data/chunks/chunks.jsonl";
const PREVIEW_CHARS = 100;

const listEl = must<HTMLDivElement>("#list");
const statsEl = must<HTMLSpanElement>("#stats");
const filterEl = must<HTMLInputElement>("#filter");
const viewTitleEl = must<HTMLSpanElement>("#view-title");
const viewMetaEl = must<HTMLSpanElement>("#view-meta");
const sourceEl = must<HTMLDivElement>("#source");

let chunks: Chunk[] = [];
let query = "";
let activeKey = "";
let viewToken = 0;
let filterTimer: number | undefined;
const fileCache = new Map<string, string[]>();

function must<T extends Element>(selector: string): T {
  const el = document.querySelector<T>(selector);
  if (!el) throw new Error(`页面缺少元素 ${selector}`);
  return el;
}

function span(className: string, text: string): HTMLSpanElement {
  const el = document.createElement("span");
  el.className = className;
  el.textContent = text;
  return el;
}

function preview(text: string): string {
  return text.replace(/\s+/g, " ").trim().slice(0, PREVIEW_CHARS);
}

function shortPath(source: string): string {
  return source.replace("data/langchain-docs/", "");
}

function isMatch(chunk: Chunk, keyword: string): boolean {
  if (!keyword) return true;
  return (
    chunk.content.toLowerCase().includes(keyword) ||
    chunk.source.toLowerCase().includes(keyword) ||
    chunk.heading.toLowerCase().includes(keyword)
  );
}

function renderList(): void {
  const keyword = query;
  const visible: number[] = [];
  const fragment = document.createDocumentFragment();

  for (let index = 0; index < chunks.length; index += 1) {
    const chunk = chunks[index];
    if (!isMatch(chunk, keyword)) continue;
    visible.push(index);

    const item = document.createElement("button");
    item.type = "button";
    item.className = "chunk";
    item.dataset.index = String(index);
    if (chunkKey(chunk) === activeKey) item.classList.add("active");

    const heading = chunk.heading ? ` › ${chunk.heading}` : "";
    const meta = `${shortPath(chunk.source)} · 行 ${chunk.line_start}–${chunk.line_end}`;
    item.append(
      span("idx", `[${visible.length}]`),
      span("text", preview(chunk.content)),
      span("meta", meta + heading),
    );
    fragment.append(item);
  }

  listEl.replaceChildren(fragment);

  const suffix = keyword ? `过滤后 ${visible.length} / ${chunks.length}` : `${chunks.length} chunks`;
  statsEl.textContent = `${suffix} · ${new Set(chunks.map((chunk) => chunk.source)).size} 个文件`;
}

function chunkKey(chunk: Chunk): string {
  return `${chunk.source}#${chunk.start}`;
}

async function loadFile(source: string): Promise<string[]> {
  const cached = fileCache.get(source);
  if (cached) return cached;

  const response = await fetch(`../${source}`);
  if (!response.ok) throw new Error(`读取 ${source} 失败：${response.status}`);
  const lines = (await response.text()).split("\n");
  fileCache.set(source, lines);
  return lines;
}

function renderSource(lines: string[], chunk: Chunk): void {
  const fragment = document.createDocumentFragment();

  for (let index = 0; index < lines.length; index += 1) {
    const lineNumber = index + 1;
    const row = document.createElement("div");
    row.className = "line";

    if (lineNumber >= chunk.line_start && lineNumber <= chunk.line_end) {
      row.classList.add("hit");
      if (lineNumber === chunk.line_start) row.classList.add("hit-start");
    }

    row.append(
      span("ln", String(lineNumber)),
      span("code", lines[index] === "" ? " " : lines[index]),
    );
    fragment.append(row);
  }

  sourceEl.replaceChildren(fragment);
  const first = sourceEl.querySelector(".line.hit-start");
  first?.scrollIntoView({ block: "center" });
}

async function openChunk(chunk: Chunk): Promise<void> {
  const token = ++viewToken;
  activeKey = chunkKey(chunk);
  for (const el of listEl.querySelectorAll(".chunk.active")) el.classList.remove("active");
  listEl.querySelector(`.chunk[data-index="${chunks.indexOf(chunk)}"]`)?.classList.add("active");

  viewTitleEl.textContent = `${shortPath(chunk.source)}${chunk.heading ? ` › ${chunk.heading}` : ""}`;
  viewMetaEl.textContent = `字符 ${chunk.start}–${chunk.end} · 行 ${chunk.line_start}–${chunk.line_end} · ${chunk.chars} 字符`;

  sourceEl.replaceChildren(span("hint", "读取源文件…"));
  try {
    const lines = await loadFile(chunk.source);
    if (token === viewToken) renderSource(lines, chunk);
  } catch (error) {
    if (token === viewToken) sourceEl.replaceChildren(span("hint", String(error)));
  }
}

async function boot(): Promise<void> {
  try {
    const response = await fetch(CHUNKS_URL);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    chunks = (await response.text())
      .split("\n")
      .filter((line) => line.trim() !== "")
      .map((line) => JSON.parse(line) as Chunk);
  } catch (error) {
    statsEl.textContent = `加载 ${CHUNKS_URL} 失败：${String(error)}`;
    return;
  }

  renderList();
  if (chunks.length > 0) void openChunk(chunks[0]);
}

listEl.addEventListener("click", (event) => {
  const target = (event.target as HTMLElement).closest<HTMLButtonElement>("button.chunk");
  if (!target?.dataset.index) return;
  const chunk = chunks[Number(target.dataset.index)];
  if (chunk) void openChunk(chunk);
});

filterEl.addEventListener("input", () => {
  window.clearTimeout(filterTimer);
  filterTimer = window.setTimeout(() => {
    query = filterEl.value.trim().toLowerCase();
    renderList();
  }, 120);
});

void boot();
