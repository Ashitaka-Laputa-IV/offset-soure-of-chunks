import { must, shortPath, span } from "./source-view.js";

interface Reference {
  n: number;
  id: string;
  source: string;
  start: number;
  end: number;
  line_start: number;
  line_end: number;
  heading: string;
  chars: number;
  content: string;
  href: string;
}

interface Article {
  title: string;
  generated_at: string;
  html: string;
  references: Reference[];
}

const ARTICLE_URL = "../data/article/article.json";

function renderReferences(references: Reference[]): void {
  const container = must<HTMLDivElement>("#references");
  const fragment = document.createDocumentFragment();

  for (const reference of references) {
    const details = document.createElement("details");
    details.className = "ref";
    details.id = `ref-${reference.n}`;

    const summary = document.createElement("summary");
    const heading = reference.heading ? ` · ${reference.heading}` : "";
    const source = `${shortPath(reference.source)} · 行 ${reference.line_start}–${reference.line_end}${heading}`;
    summary.append(span("ref-n", `[${reference.n}]`), span("ref-src", source));

    const body = document.createElement("div");
    body.className = "ref-body";

    const jump = document.createElement("a");
    jump.className = "jump";
    jump.href = reference.href;
    jump.target = "_blank";
    jump.rel = "noopener";
    jump.textContent = "在原文件中定位 ↗";

    const content = document.createElement("pre");
    content.textContent = reference.content;

    body.append(jump, content);
    details.append(summary, body);
    fragment.append(details);
  }

  container.replaceChildren(fragment);
}

function openFromHash(): void {
  const match = location.hash.match(/^#ref-(\d+)$/);
  if (!match) return;
  const target = document.getElementById(`ref-${match[1]}`);
  if (target instanceof HTMLDetailsElement) {
    target.open = true;
    target.scrollIntoView({ block: "center" });
  }
}

function setAll(open: boolean): void {
  for (const el of document.querySelectorAll<HTMLDetailsElement>("details.ref")) {
    el.open = open;
  }
}

async function boot(): Promise<void> {
  const statsEl = must<HTMLSpanElement>("#stats");
  const articleEl = must<HTMLElement>("#article");

  try {
    const response = await fetch(ARTICLE_URL);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    const article = (await response.json()) as Article;

    document.title = article.title;
    articleEl.innerHTML = article.html;
    statsEl.textContent = `${article.references.length} 条引用 · 生成于 ${article.generated_at.replace("T", " ").slice(0, 19)} UTC`;
    renderReferences(article.references);
    openFromHash();
  } catch (error) {
    statsEl.textContent = "加载文章失败";
    articleEl.replaceChildren(
      span("hint", `读取 ${ARTICLE_URL} 失败：${String(error)}。请先运行 uv run chunk 与 uv run article。`),
    );
  }
}

must<HTMLButtonElement>("#expand-all").addEventListener("click", () => setAll(true));
must<HTMLButtonElement>("#collapse-all").addEventListener("click", () => setAll(false));

void boot();
