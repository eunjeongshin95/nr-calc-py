// Service worker: 앱 파일을 브라우저 캐시에 저장해 오프라인에서도 동작하게 한다.
//
// 비유: 브라우저와 서버 사이에 놓인 프록시(버퍼). 모든 요청이 여기를 지나간다.
//  - 앱 파일(html/css/js/py): 네트워크 우선 → 실패하면 캐시. 온라인이면 수정 내용이 바로 반영된다.
//  - Pyodide 파일(vendor/): 캐시 우선. 크고 바뀌지 않는 파일이라 매번 받지 않는다.
// 캐시할 파일 목록이나 vendor/ 버전을 바꾸면 CACHE 이름의 숫자를 올린다 (예전 캐시 자동 삭제).
"use strict";

const CACHE = "nr-calc-v1";

const APP_FILES = [
  "./",
  "index.html",
  "style.css",
  "app.js",
  "nr_calc.py",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/apple-touch-icon.png",
];

const VENDOR_FILES = [
  "vendor/pyodide/pyodide.js",
  "vendor/pyodide/pyodide.asm.js",
  "vendor/pyodide/pyodide.asm.wasm",
  "vendor/pyodide/python_stdlib.zip",
  "vendor/pyodide/pyodide-lock.json",
];

const NETWORK_TIMEOUT_MS = 4000;

// 설치: 필요한 파일을 모두 캐시에 미리 넣는다 (하나라도 실패하면 설치 실패 → 다음 방문 때 재시도)
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll([...APP_FILES, ...VENDOR_FILES]))
      .then(() => self.skipWaiting())
  );
});

// 활성화: 이름이 다른 예전 캐시 삭제
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function fetchWithTimeout(request) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("timeout")), NETWORK_TIMEOUT_MS);
    fetch(request).then(
      (resp) => { clearTimeout(timer); resolve(resp); },
      (err) => { clearTimeout(timer); reject(err); }
    );
  });
}

async function networkFirst(request) {
  const cache = await caches.open(CACHE);
  try {
    const resp = await fetchWithTimeout(request);
    if (resp.ok) cache.put(request, resp.clone());  // 최신본으로 캐시 갱신
    return resp;
  } catch {
    const hit = await cache.match(request, { ignoreSearch: true });
    if (hit) return hit;
    if (request.mode === "navigate") {
      const index = await cache.match("./");
      if (index) return index;
    }
    throw new Error(`오프라인이고 캐시에도 없음: ${request.url}`);
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(request);
  if (hit) return hit;
  const resp = await fetch(request);
  if (resp.ok) cache.put(request, resp.clone());
  return resp;
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin) return;  // 같은 사이트 GET만 처리
  event.respondWith(url.pathname.includes("/vendor/") ? cacheFirst(req) : networkFirst(req));
});
