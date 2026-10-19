# offset-source-of-chunks

把 markdown 文档切成 chunk，并记录每个 chunk 在源文件中的**字符偏移**。附带一个极简网页，点击 chunk 即可打开源文件并跳到对应位置。

核心是 Python 切分脚本，前端只用于演示。

## 快速开始

```bash
# 1. 准备语料（约 180 个 markdown，5 MB，不入库）
uv run python data/download_docs.py

# 2. 切分并生成带偏移的 chunk 索引（内容不入库）
uv run chunk

# 3. 启动浏览页面
uv run serve          # 打开 http://127.0.0.1:8000/web/
```

`uv run serve --port 9000` 可改端口。页面从 `data/chunks/chunks.jsonl` 读列表，点击 chunk 后直接抓取源 markdown 定位，因此必须通过这个服务器访问（`file://` 打开不行）。

修改前端 TypeScript 后需要重新编译：

```bash
cd web && npm install && npm run build   # 输出 web/dist/main.js
```

## 目录结构

```
src/offset_soure_of_chunks/
  chunker.py     # 切分逻辑 + CLI（uv run chunk）
  server.py      # 静态服务器（uv run serve）
web/
  index.html     # 页面与样式
  src/main.ts    # chunk 列表、过滤、源文件定位
  dist/main.js   # 编译产物
data/
  download_docs.py
  langchain-docs/    # 语料，gitignore
  chunks/chunks.jsonl  # 生成的 chunk，gitignore
```

## 输出格式

`data/chunks/chunks.jsonl`，每行一个 chunk：

```json
{
  "id": "data/langchain-docs/oss/python/langchain/quickstart.md#3",
  "source": "data/langchain-docs/oss/python/langchain/quickstart.md",
  "start": 1543,
  "end": 1939,
  "line_start": 29,
  "line_end": 37,
  "heading": "Quickstart > Build an agent",
  "chars": 396,
  "content": "…"
}
```

- `source`：相对于项目根目录的源文件路径。
- `start` / `end`：在源文件中的字符偏移，左闭右开，按 Unicode 码点计数；`source` 的 `text[start:end]` 就是 `content`。
- `line_start` / `line_end`：上述偏移对应的 1 起始行号（前端用它滚动定位）。
- `heading`：chunk 起始处的标题层级路径，便于按章节阅读。

## 切分策略

不依赖任何第三方库，逐行扫描文档：

1. 识别标题、段落、围栏代码块；**代码块整体保留**，不会从中间切开。
2. 一级/二级标题一定开新 chunk；三级及以下标题只在当前 chunk 已有 `--min-chars`（默认 300）字符时才开新块，避免碎片化。
3. 超过 `--max-chars`（默认 1200）时，在段落边界继续切分；单个超长段落按行切分。
4. 单个代码块本身超过上限时整块作为一个 chunk（宁可超长也不破坏代码），所以 chunk 长度不保证都小于 `--max-chars`。

参数可调：

```bash
uv run chunk --max-chars 1000 --min-chars 200 --docs data/langchain-docs --out data/chunks/chunks.jsonl
```

当前语料（180 个文件）切分结果：约 5700 个 chunk，中位长度约 940 字符。

## 说明

- `data/langchain-docs/` 与 `data/chunks/` 都在 `.gitignore` 中：语料可重新下载，chunk 内容不入库（避免仓库膨胀），仓库只保留脚本与前端。
- 偏移按 Unicode 码点计算；前端用行号定位，因此即使文件含 emoji 等非 BMP 字符也不会错位。
- 文档版权归 LangChain 所有，语料仅供本地学习/测试使用。
