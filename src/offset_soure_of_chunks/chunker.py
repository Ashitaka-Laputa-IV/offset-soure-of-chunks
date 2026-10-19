"""按 markdown 结构切分文档，并为每个 chunk 记录源文件与字符偏移。

切分策略（不依赖任何第三方库）:

1. 逐行扫描，把文档拆成块: 标题、段落、围栏代码块。代码块整体保留，绝不从中间切开。
2. 以标题为骨架分块: 一级/二级标题一定开新块；三级及以下标题只在当前块
   已经有足够内容（>= min_chars）时才开新块，避免碎片化。
3. 内容超过 max_chars 时，在段落边界继续切分；单个超长段落退化为按行切分。
4. 每个 chunk 记录在源文件中的起止字符偏移（左闭右开），以及对应的行号。
"""

from __future__ import annotations

import argparse
import bisect
import json
import pathlib
import re
from dataclasses import dataclass

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_DOCS_DIR = PROJECT_ROOT / "data" / "langchain-docs"
DEFAULT_OUT_FILE = PROJECT_ROOT / "data" / "chunks" / "chunks.jsonl"

MAX_CHARS = 1200
MIN_CHARS = 300

HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})")
FENCE_CLOSE_RE = re.compile(r"^(`{3,}|~{3,})[ \t]*$")


@dataclass
class Block:
    """文档中的一个结构块。offset 左闭右开，均相对于整个文件。"""

    kind: str  # heading | text | fence
    start: int
    end: int
    level: int = 0
    title: str = ""


@dataclass
class Chunk:
    start: int
    end: int
    heading: str
    content: str


def iter_lines(text: str):
    """产出 (行起始偏移, 含换行符的行内容)。"""
    offset = 0
    for line in text.splitlines(keepends=True):
        yield offset, line
        offset += len(line)


def parse_blocks(text: str) -> list[Block]:
    """把文档拆成标题 / 段落 / 代码块，保留精确偏移。"""
    blocks: list[Block] = []
    lines = list(iter_lines(text))

    para_start: int | None = None
    para_end = 0
    index = 0

    def flush_paragraph() -> None:
        nonlocal para_start, para_end
        if para_start is not None:
            blocks.append(Block("text", para_start, para_end))
            para_start = None

    while index < len(lines):
        offset, line = lines[index]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            index += 1
            continue

        fence = FENCE_OPEN_RE.match(stripped)
        if fence:
            flush_paragraph()
            marker = fence.group(1)[0]
            start = offset
            end = offset + len(line)
            index += 1
            while index < len(lines):
                inner_offset, inner_line = lines[index]
                inner_stripped = inner_line.strip()
                end = inner_offset + len(inner_line)
                index += 1
                close = FENCE_CLOSE_RE.match(inner_stripped)
                if close and close.group(1)[0] == marker and len(close.group(1)) >= len(fence.group(1)):
                    break
            blocks.append(Block("fence", start, end))
            continue

        heading = HEADING_RE.match(line)
        if heading:
            flush_paragraph()
            blocks.append(
                Block(
                    "heading",
                    offset,
                    offset + len(line),
                    level=len(heading.group(1)),
                    title=heading.group(2).strip(),
                )
            )
            index += 1
            continue

        if para_start is None:
            para_start = offset
        para_end = offset + len(line)
        index += 1

    flush_paragraph()
    return blocks


def split_block_by_lines(block: Block, text: str, max_chars: int) -> list[Block]:
    """超长段落按行切分（不切代码块）。"""
    body = text[block.start : block.end]
    pieces: list[Block] = []
    start: int | None = None
    end = 0

    for offset, line in iter_lines(body):
        absolute = block.start + offset
        if start is None:
            start = absolute
        if end and absolute + len(line) - start > max_chars:
            pieces.append(Block("text", start, end))
            start = absolute
        end = absolute + len(line)

    if start is not None and end > start:
        pieces.append(Block("text", start, end))
    return pieces


def trim_chunk(text: str, start: int, end: int) -> tuple[int, int]:
    """去掉 chunk 尾部的空白字符，返回调整后的偏移。"""
    snippet = text[start:end]
    end = start + len(snippet.rstrip())
    return start, end


def split_text(text: str, max_chars: int = MAX_CHARS, min_chars: int = MIN_CHARS) -> list[Chunk]:
    """将一份文档切分为若干 chunk。"""
    blocks = parse_blocks(text)
    chunks: list[Chunk] = []

    current: list[Block] = []
    current_heading = ""
    heading_stack: list[tuple[int, str]] = []

    def add(block: Block) -> None:
        nonlocal current_heading
        if not current:
            current_heading = " > ".join(title for _, title in heading_stack)
        current.append(block)

    def current_len() -> int:
        if not current:
            return 0
        return current[-1].end - current[0].start

    def flush() -> None:
        nonlocal current, current_heading
        if not current:
            return
        start, end = trim_chunk(text, current[0].start, current[-1].end)
        if end > start:
            chunks.append(Chunk(start, end, current_heading, text[start:end]))
        current = []
        current_heading = ""

    for block in blocks:
        if block.kind == "heading":
            must_split = block.level <= 2 or current_len() >= min_chars
            if must_split:
                flush()
            while heading_stack and heading_stack[-1][0] >= block.level:
                heading_stack.pop()
            heading_stack.append((block.level, block.title))
            add(block)
            continue

        block_len = block.end - block.start
        if current and current_len() >= min_chars and current_len() + block_len > max_chars:
            flush()

        if block_len > max_chars and block.kind == "text":
            pieces = split_block_by_lines(block, text, max_chars)
            for position, piece in enumerate(pieces):
                if current and current_len() + (piece.end - piece.start) > max_chars:
                    flush()
                add(piece)
                if position < len(pieces) - 1:
                    flush()
            continue

        add(block)

    flush()
    return chunks


def line_starts(text: str) -> list[int]:
    return [offset for offset, _ in iter_lines(text)]


def line_number(starts: list[int], offset: int) -> int:
    """字符偏移 -> 1 起始的行号。"""
    return bisect.bisect_right(starts, offset)


def build(docs_dir: pathlib.Path, out_file: pathlib.Path, max_chars: int, min_chars: int) -> tuple[int, int]:
    files = sorted(docs_dir.rglob("*.md"))
    if not files:
        raise SystemExit(f"没有在 {docs_dir} 找到 markdown 文件，先运行 data/download_docs.py")

    out_file.parent.mkdir(parents=True, exist_ok=True)
    total_chunks = 0
    total_chars = 0

    with out_file.open("w", encoding="utf-8") as handle:
        for path in files:
            text = path.read_text(encoding="utf-8")
            source = path.relative_to(PROJECT_ROOT).as_posix()
            starts = line_starts(text)

            for index, chunk in enumerate(split_text(text, max_chars, min_chars), start=1):
                record = {
                    "id": f"{source}#{index}",
                    "source": source,
                    "start": chunk.start,
                    "end": chunk.end,
                    "line_start": line_number(starts, chunk.start),
                    "line_end": line_number(starts, chunk.end - 1),
                    "heading": chunk.heading,
                    "chars": chunk.end - chunk.start,
                    "content": chunk.content,
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_chunks += 1
                total_chars += record["chars"]

    return total_chunks, total_chars


def cli() -> None:
    parser = argparse.ArgumentParser(description="按 markdown 结构切分文档，生成带字符偏移的 chunk。")
    parser.add_argument("--docs", type=pathlib.Path, default=DEFAULT_DOCS_DIR, help="语料目录")
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT_FILE, help="输出 jsonl 路径")
    parser.add_argument("--max-chars", type=int, default=MAX_CHARS, help="单个 chunk 的目标上限")
    parser.add_argument("--min-chars", type=int, default=MIN_CHARS, help="低于该长度时不再按小标题切分")
    args = parser.parse_args()

    chunks, chars = build(args.docs, args.out, args.max_chars, args.min_chars)
    print(f"{chunks} 个 chunk，平均 {chars // max(chunks, 1)} 字符 -> {args.out}")


if __name__ == "__main__":
    cli()
