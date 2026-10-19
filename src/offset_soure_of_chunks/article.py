"""把 article.md 渲染为带引用跳转的 HTML。

正文中的 [n] 会在构建时解析成具体 chunk，并生成指向源文件偏移的链接；
被引用的 chunk 单独输出到 references 列表，供页面在文末折叠展示。
"""

from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
from datetime import datetime, timezone
from urllib.parse import urlencode

import markdown

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_ARTICLE = PROJECT_ROOT / "data" / "article" / "article.md"
DEFAULT_CITATIONS = PROJECT_ROOT / "data" / "article" / "citations.json"
DEFAULT_CHUNKS = PROJECT_ROOT / "data" / "chunks" / "chunks.jsonl"
DEFAULT_OUT = PROJECT_ROOT / "data" / "article" / "article.json"

CITE_RE = re.compile(r"\[(\d+)\]")
INLINE_CODE_RE = re.compile(r"(`[^`]*`)")
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def load_chunks(path: pathlib.Path) -> dict[str, list[dict]]:
    by_source: dict[str, list[dict]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        chunk = json.loads(line)
        by_source.setdefault(chunk["source"], []).append(chunk)
    return by_source


def resolve_citations(
    citations: dict[str, dict], by_source: dict[str, list[dict]]
) -> dict[int, dict]:
    """把 (source, quote) 解析为唯一 chunk，失败时汇总报错。"""
    resolved: dict[int, dict] = {}
    problems: list[str] = []

    for key, target in citations.items():
        number = int(key)
        source = target["source"]
        quote = target["quote"]
        candidates = [chunk for chunk in by_source.get(source, []) if quote in chunk["content"]]
        if not candidates:
            problems.append(f"引用 [{number}] 在 {source} 中找不到片段：{quote!r}")
        elif len(candidates) > 1:
            problems.append(f"引用 [{number}] 命中 {len(candidates)} 个 chunk，请把 quote 写得更具体")
        else:
            resolved[number] = candidates[0]

    if problems:
        raise SystemExit("\n".join(problems))
    return resolved


def build_href(chunk: dict) -> str:
    params = {
        "source": chunk["source"],
        "start": chunk["start"],
        "end": chunk["end"],
        "line_start": chunk["line_start"],
        "line_end": chunk["line_end"],
    }
    return "source.html?" + urlencode(params)


def anchor(number: int, chunk: dict) -> str:
    href = html.escape(build_href(chunk), quote=True)
    return (
        f'<a class="cite" data-ref="{number}" href="{href}" '
        f'target="_blank" rel="noopener">[{number}]</a>'
    )


def replace_citation(match: re.Match[str], resolved: dict[int, dict]) -> str:
    number = int(match.group(1))
    chunk = resolved.get(number)
    if chunk is None:
        raise SystemExit(f"正文引用了未定义的编号 [{number}]")
    return anchor(number, chunk)


def replace_line(line: str, resolved: dict[int, dict]) -> str:
    """只替换行内代码之外的 [n]，避免破坏示例代码。"""
    parts = INLINE_CODE_RE.split(line)
    for index in range(0, len(parts), 2):
        parts[index] = CITE_RE.sub(lambda match: replace_citation(match, resolved), parts[index])
    return "".join(parts)


def linkify(text: str, resolved: dict[int, dict]) -> str:
    output: list[str] = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            output.append(line)
            continue
        output.append(line if in_fence else replace_line(line, resolved))
    return "".join(output)


def build(article: pathlib.Path, citations: pathlib.Path, chunks: pathlib.Path, out: pathlib.Path) -> None:
    text = article.read_text(encoding="utf-8")
    citation_map = json.loads(citations.read_text(encoding="utf-8"))
    resolved = resolve_citations(citation_map, load_chunks(chunks))

    title_match = TITLE_RE.search(text)
    title = title_match.group(1).strip() if title_match else article.stem

    body = markdown.markdown(
        linkify(text, resolved),
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )

    references = []
    for number in sorted(resolved):
        chunk = resolved[number]
        references.append(
            {
                "n": number,
                "id": chunk["id"],
                "source": chunk["source"],
                "start": chunk["start"],
                "end": chunk["end"],
                "line_start": chunk["line_start"],
                "line_end": chunk["line_end"],
                "heading": chunk["heading"],
                "chars": chunk["chars"],
                "content": chunk["content"],
                "href": build_href(chunk),
            }
        )

    payload = {
        "title": title,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "html": body,
        "references": references,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(references)} 条引用 -> {out}")

    unused = sorted(set(resolved) - set(_used_numbers(text)))
    if unused:
        print("未被正文使用的引用：" + ", ".join(f"[{n}]" for n in unused))


def _used_numbers(text: str) -> set[int]:
    numbers: set[int] = set()
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for part in INLINE_CODE_RE.split(line)[::2]:
            numbers.update(int(match.group(1)) for match in CITE_RE.finditer(part))
    return numbers


def cli() -> None:
    parser = argparse.ArgumentParser(description="渲染带引用跳转的文章页面数据。")
    parser.add_argument("--article", type=pathlib.Path, default=DEFAULT_ARTICLE)
    parser.add_argument("--citations", type=pathlib.Path, default=DEFAULT_CITATIONS)
    parser.add_argument("--chunks", type=pathlib.Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    build(args.article, args.citations, args.chunks, args.out)


if __name__ == "__main__":
    cli()
