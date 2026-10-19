const fileCache = new Map();
export function must(selector) {
    const el = document.querySelector(selector);
    if (!el)
        throw new Error(`页面缺少元素 ${selector}`);
    return el;
}
export function span(className, text) {
    const el = document.createElement("span");
    el.className = className;
    el.textContent = text;
    return el;
}
export function shortPath(source) {
    return source.replace("data/langchain-docs/", "");
}
export async function loadSource(source) {
    const cached = fileCache.get(source);
    if (cached)
        return cached;
    const response = await fetch(`../${source}`);
    if (!response.ok)
        throw new Error(`读取 ${source} 失败：${response.status}`);
    const lines = (await response.text()).split("\n");
    fileCache.set(source, lines);
    return lines;
}
export function renderSource(container, lines, range) {
    const fragment = document.createDocumentFragment();
    for (let index = 0; index < lines.length; index += 1) {
        const lineNumber = index + 1;
        const row = document.createElement("div");
        row.className = "line";
        if (lineNumber >= range.line_start && lineNumber <= range.line_end) {
            row.classList.add("hit");
            if (lineNumber === range.line_start)
                row.classList.add("hit-start");
        }
        row.append(span("ln", String(lineNumber)), span("code", lines[index] === "" ? " " : lines[index]));
        fragment.append(row);
    }
    container.replaceChildren(fragment);
    container.querySelector(".line.hit-start")?.scrollIntoView({ block: "center" });
}
