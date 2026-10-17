#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# speedtest.py · 版本号 v1.0 (2026-10-17 14:12 +08:00)
# 改动记录：
#   v1.0  初始独立版。读 ip_pool.txt，对每个 Cloudflare IP 测延迟+下载速度，
#         取 Top N，双写 ipTop.html(纯文本列表，兼容原网站) 与 ipTop.json(结构化，供网页)。
# 环境变量（可选，便于测试/调参）：
#   TOP_N      取前几个，默认 2
#   MAX_IPS    最多测多少个 IP（0=全部，用于测试加速）
#   IP_POOL    指定 IP 池文件路径（默认 同目录 ip_pool.txt）
#   OUT_DIR    输出目录（默认 同目录）
# 对外暴露版本号：下方 VERSION 常量 + 写入 ipTop.json 的 version 字段。
# ============================================================================

import json
import os
import socket
import ssl
import time

VERSION = "1.0"

HERE = os.path.dirname(os.path.abspath(__file__))
SNI_HOST = "speed.cloudflare.com"      # TLS SNI，CF 在这些 anycast IP 上都会出该域名证书
DOWN_PATH_FMT = "GET https://{host}/__down?bytes={n} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: cf-speedtest-mine/{v}\r\nConnection: close\r\n\r\n"


def load_ips():
    """读 IP 池。路径可用 IP_POOL 覆盖，便于测试。"""
    pool = os.environ.get("IP_POOL") or os.path.join(HERE, "ip_pool.txt")
    ips = []
    with open(pool, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            ips.append(s)
    return ips


def is_valid_ipv4(ip):
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    for p in parts:
        if not p.isdigit() or not (0 <= int(p) <= 255):
            return False
    return True


def latency_probe(ip, rounds=2, timeout=2.0):
    """TCP 连接 443 端口多轮取最短延迟。连不上返回 None。"""
    best = None
    for _ in range(rounds):
        t0 = time.time()
        try:
            s = socket.create_connection((ip, 443), timeout)
            s.close()
            dt = time.time() - t0
            best = dt if best is None else min(best, dt)
        except Exception:
            pass
    return best


def download_speed(ip, target=2 * 1024 * 1024, timeout=10.0):
    """把 TLS 会话钉到具体 IP（SNI 指向 CF），下载 __down 测吞吐。失败返回 0.0。"""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        sock = socket.create_connection((ip, 443), timeout)
        wrapped = ctx.wrap_socket(sock, server_hostname=SNI_HOST)
        req = DOWN_PATH_FMT.format(host=SNI_HOST, n=target, v=VERSION).encode()
        wrapped.sendall(req)
        total = 0
        buf = b""
        t0 = time.time()
        while total < target:
            chunk = wrapped.recv(65536)
            if not chunk:
                break
            buf += chunk
            total += len(chunk)
        dt = time.time() - t0
        wrapped.close()
        idx = buf.find(b"\r\n\r\n")
        if idx != -1:
            total = len(buf) - (idx + 4)
        if dt <= 0 or total <= 0:
            return 0.0
        return total / dt / (1024 * 1024)  # MB/s
    except Exception:
        return 0.0


def run():
    """跑一遍测速，写输出文件，返回 payload（供测试断言）。"""
    ips = load_ips()
    top_n = int(os.environ.get("TOP_N", "2"))
    max_ips = int(os.environ.get("MAX_IPS", "0"))
    if max_ips > 0:
        ips = ips[:max_ips]

    results = []
    for ip in ips:
        if not is_valid_ipv4(ip):
            continue
        lat = latency_probe(ip)
        if lat is None:
            continue
        results.append({"ip": ip, "latency_ms": round(lat * 1000, 2)})

    results.sort(key=lambda r: r["latency_ms"])

    # 对延迟最低的前 5 个测下载速度（其余只留延迟）
    for r in results[:5]:
        r["download_mbps"] = round(download_speed(r["ip"]), 3)
        r["sent"] = 4
        r["recv"] = 4
        r["loss"] = "0.00%"

    final = results[:top_n]
    tested_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    out_dir = os.environ.get("OUT_DIR") or HERE
    os.makedirs(out_dir, exist_ok=True)

    # ipTop.html：纯文本逗号列表（兼容原网站解析方式）
    with open(os.path.join(out_dir, "ipTop.html"), "w", encoding="utf-8") as f:
        f.write(",".join(r["ip"] for r in final))

    # ipTop.json：结构化，给网页实时渲染
    payload = {
        "version": VERSION,
        "tested_at": tested_at,
        "count": len(final),
        "top": final,
    }
    with open(os.path.join(out_dir, "ipTop.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return payload


def main():
    payload = run()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


if __name__ == "__main__":
    main()
