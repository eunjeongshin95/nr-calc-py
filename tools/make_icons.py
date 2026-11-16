"""앱 아이콘(PNG) 생성 스크립트. 표준 라이브러리만 사용 (Pillow 불필요).

실행: python tools/make_icons.py  → icons/icon-192.png, icon-512.png, apple-touch-icon.png
디자인: 파란 배경 + 흰색 막대 4개(신호 세기/데이터율). 막대는 가운데 60% 안에 두어
       maskable 아이콘(OS가 원·둥근 사각형으로 잘라냄)에서도 잘리지 않게 한다.
"""

import struct
import zlib
from pathlib import Path

BG = (31, 111, 235)       # #1f6feb (style.css의 --accent)
FG = (255, 255, 255)
SS = 4                    # 슈퍼샘플링 배율 (가장자리 부드럽게)


def _inside_bar(x: float, y: float) -> bool:
    """0~1 좌표에서 (x, y)가 막대 안인지. 막대 위쪽 모서리는 둥글게."""
    left, right, bottom = 0.22, 0.78, 0.76
    heights = (0.20, 0.32, 0.44, 0.56)       # 막대 높이 (왼쪽 → 오른쪽 증가)
    gap = 0.04
    width = (right - left - gap * 3) / 4
    radius = width * 0.35
    for i, h in enumerate(heights):
        x0 = left + i * (width + gap)
        x1 = x0 + width
        top = bottom - h
        if not (x0 <= x <= x1 and top <= y <= bottom):
            continue
        # 위쪽 두 모서리 둥글게
        if y < top + radius:
            cx = x0 + radius if x < x0 + radius else (x1 - radius if x > x1 - radius else None)
            if cx is not None and (x - cx) ** 2 + (y - (top + radius)) ** 2 > radius ** 2:
                return False
        return True
    return False


def make_png(size: int) -> bytes:
    rows = []
    n = size * SS
    for py in range(size):
        row = bytearray([0])  # PNG 필터 타입 0
        for px in range(size):
            hits = 0
            for sy in range(SS):
                for sx in range(SS):
                    if _inside_bar((px * SS + sx + 0.5) / n, (py * SS + sy + 0.5) / n):
                        hits += 1
            a = hits / (SS * SS)
            row += bytes(round(b * (1 - a) + f * a) for b, f in zip(BG, FG)) + b"\xff"
        rows.append(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8bit RGBA
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "icons"
    out.mkdir(exist_ok=True)
    for name, size in (("icon-192.png", 192), ("icon-512.png", 512), ("apple-touch-icon.png", 180)):
        (out / name).write_bytes(make_png(size))
        print(f"{name}: {size}x{size}")
