#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# make_icons.py · v1.3.0 (2026-10-17 18:55 +08:00)
# 生成 FPK 所需的 ICON.PNG(64x64) 与 ICON_256.PNG(256x256)。
# 纯标准库（zlib/struct），画一个深蓝底 + 白色 "CF" 字样的简易图标。
import os, struct, zlib

HERE = os.path.dirname(os.path.abspath(__file__))


def make_png(size, path):
    # 背景深蓝 #1E3A8A，中央白色粗体 "CF"
    bg = (30, 58, 138)
    fg = (255, 255, 255)
    # 简易 5x7 点阵字（C 和 F）
    font = {
        "C": ["01110","10001","10000","10000","10000","10001","01110"],
        "F": ["11111","10000","10000","11110","10000","10000","10000"],
    }
    W = H = size
    px = [[bg] * W for _ in range(H)]
    # 字号比例
    cell = max(2, W // 18)
    text = "CF"
    total_w = (len(font["C"]) ) * cell * len(text) - cell
    ox = (W - total_w) // 2
    oy = (H - 7 * cell) // 2
    for ti, ch in enumerate(text):
        g = font[ch]
        for row in range(7):
            for col in range(5):
                if g[row][col] == "1":
                    x0 = ox + ti * 5 * cell + col * cell
                    y0 = oy + row * cell
                    for dy in range(cell):
                        for dx in range(cell):
                            xx, yy = x0 + dx, y0 + dy
                            if 0 <= xx < W and 0 <= yy < H:
                                px[yy][xx] = fg
    # 组 raw PNG rows（每行加 filter byte 0）
    raw = bytearray()
    for row in px:
        raw.append(0)
        for (r, g, b) in row:
            raw.append(r); raw.append(g); raw.append(b)

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    print("wrote", path, len(png), "bytes")


if __name__ == "__main__":
    make_png(64, os.path.join(HERE, "ICON.PNG"))
    make_png(256, os.path.join(HERE, "ICON_256.PNG"))
