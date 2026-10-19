"""极简静态服务器：以项目根目录为根，方便前端同时访问 chunk 索引和源文件。

用法:
    uv run serve            # http://127.0.0.1:8000/web/
    uv run serve --port 9000
"""

from __future__ import annotations

import argparse
import functools
import http.server
import pathlib
import socketserver

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/web/")
            self.end_headers()
            return
        super().do_GET()

    def end_headers(self) -> None:
        # 本地演示，避免改完 chunker 后浏览器还用旧缓存
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve(port: int = 8000) -> None:
    handler = functools.partial(Handler, directory=str(PROJECT_ROOT))
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), handler) as server:
        server.daemon_threads = True
        print(f"http://127.0.0.1:{port}/web/")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 chunk 浏览页面的本地服务器。")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    serve(args.port)


if __name__ == "__main__":
    main()
