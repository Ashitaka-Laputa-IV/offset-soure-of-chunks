import { loadSource, must, renderSource, shortPath, span } from "./source-view.js";
const params = new URLSearchParams(location.search);
const source = params.get("source") ?? "";
const start = params.get("start") ?? "?";
const end = params.get("end") ?? "?";
const lineStart = Number(params.get("line_start") ?? 0);
const lineEnd = Number(params.get("line_end") ?? lineStart);
const titleEl = must("#view-title");
const metaEl = must("#view-meta");
const sourceEl = must("#source");
async function boot() {
    if (!source) {
        titleEl.textContent = "缺少 source 参数";
        sourceEl.replaceChildren(span("hint", "请从文章引用或 chunk 列表进入本页。"));
        return;
    }
    titleEl.textContent = shortPath(source);
    metaEl.textContent = `字符 ${start}–${end} · 行 ${lineStart}–${lineEnd}`;
    document.title = `${shortPath(source)} · 源文件定位`;
    try {
        const lines = await loadSource(source);
        renderSource(sourceEl, lines, { line_start: lineStart, line_end: lineEnd });
    }
    catch (error) {
        sourceEl.replaceChildren(span("hint", String(error)));
    }
}
void boot();
