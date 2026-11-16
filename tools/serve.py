"""개발용 로컬 웹 서버. 저장소 루트를 http://localhost:8000 으로 연다.

`python -m http.server`를 쓰지 않는 이유:
  Windows에서는 Python이 파일 형식(MIME)을 레지스트리에서 읽어 .js를 text/plain으로 보내는 경우가 있다.
  그러면 브라우저가 service worker(sw.js)와 Pyodide 모듈(pyodide.asm.js) 실행을 거부한다.
  이 서버는 웹 앱에 필요한 형식을 직접 지정한다. (GitHub Pages는 원래 올바른 형식을 보낸다)

실행: python tools/serve.py [포트]   (기본 8000, 끄기: Ctrl+C)
"""

import http.server
import sys
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".webmanifest": "application/manifest+json",
    ".wasm": "application/wasm",
    ".zip": "application/zip",
    ".png": "image/png",
    ".py": "text/plain; charset=utf-8",
    ".md": "text/plain; charset=utf-8",
}


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, **MIME}

    def send_head(self):
        # "바뀐 것 없음(304)" 응답을 쓰지 않고 항상 파일과 올바른 형식을 새로 보낸다.
        # (304면 브라우저가 예전 사본을 예전 형식 그대로 다시 쓸 수 있음)
        del self.headers["If-Modified-Since"]
        return super().send_head()

    def end_headers(self):
        # 개발 중에는 브라우저 HTTP 캐시를 쓰지 않게 해서 수정 내용이 바로 보이게 한다
        # (오프라인용 캐시는 service worker가 따로 관리)
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = partial(Handler, directory=str(ROOT))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"http://localhost:{port} 에서 실행 중 (끄기: Ctrl+C)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
