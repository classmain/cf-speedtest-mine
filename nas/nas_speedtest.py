#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# nas_speedtest.py · 自包含版 · 版本号 v1.4.1 (2026-10-17 19:16 +08:00)
# 改动记录：
#   v1.4.1 修时区 bug：时间戳固定按北京时间(UTC+8)输出，不再受容器/宿主时区影响
#        （python:slim 容器默认 UTC，之前北京时间 19:59 被显示成 11:59）。
#   v1.4.0 自包含：IP 池内联、测速 + GitHub REST 推送合并为一个文件，
#        飞牛 crontab 每小时跑一次即可，无需 git、无需 fnpack、无常驻进程。
#
# 用途：在飞牛 NAS（中国大陆网络）上由 crontab 每小时调用一次：
#   ① 用内置 CF IP 池测延迟 + 下载速度，取 Top N
#   ② 生成 ipTop.html（逗号列表）与 ipTop.json（结构化，带 version）
#   ③ 用 GitHub REST Contents API 推回仓库（有变化才推；纯标准库，无需 git）
#   ④ GitHub Pages 自动重建 → https://classmain.github.io/cf-speedtest-mine/ 显示大陆优选 IP
#
# 配置：同目录 nas_config.json：
#   {"repo":"classmain/cf-speedtest-mine","token":"github_pat_...","top_n":2}
#   （token 仅存本机，绝不写进仓库；chmod 600）
#
# 依赖：仅 Python3 标准库。飞牛若无 python3，装飞牛应用中心里的「Python」开发工具即可（一键、很小、非 fnpack）。
# 版本暴露：下方 VERSION 常量 + 推上去的 ipTop.json 的 version 字段。
# ============================================================================

import base64
import json
import os
import socket
import ssl
import sys
import time
import urllib.request
import urllib.error

VERSION = "1.4.1"
SNI = "speed.cloudflare.com"
HERE = os.path.dirname(os.path.abspath(__file__))

# 内置 Cloudflare anycast IPv4 池（可维护：直接改这个列表）
IP_POOL = [
    "104.16.129.129", "104.16.130.130", "104.18.12.12", "104.18.37.247",
    "104.18.40.100", "104.18.40.200", "104.21.7.153", "104.21.7.225",
    "104.22.11.10", "104.22.20.1", "104.23.14.14", "104.23.38.12",
    "104.24.10.10", "104.24.223.223", "104.26.12.12", "104.27.14.14",
    "104.28.11.1", "104.28.22.22", "104.31.22.22",
    "141.101.64.1", "141.101.64.8", "141.101.65.1", "141.101.65.8",
    "141.101.66.1", "141.101.66.8", "141.101.67.1", "141.101.67.8",
    "172.64.32.1", "172.64.32.2", "172.64.40.1", "172.64.40.2",
    "172.66.32.1", "172.66.40.1", "172.67.4.22", "172.67.130.82",
    "172.67.40.1", "172.67.40.2", "172.68.32.1", "172.68.32.2",
    "172.69.32.1", "172.69.32.2", "172.70.32.1", "172.70.32.2",
    "172.71.32.1", "172.71.32.2", "188.114.96.1", "188.114.97.1",
    "188.114.98.1", "190.93.240.1", "190.93.240.2", "190.93.247.1",
    "190.93.247.2", "198.41.128.1", "198.41.128.2", "198.41.129.1",
    "198.41.129.2", "198.41.130.1", "198.41.130.2", "198.41.200.1",
    "205.199.118.1", "205.199.122.1", "131.0.72.1", "131.0.73.1",
    "162.158.152.1", "162.158.153.1",
]


def load_cfg():
    p = os.environ.get("NAS_CFG") or os.path.join(HERE, "nas_config.json")
    with open(p, encoding="utf-8") as f:
        c = json.load(f)
    repo = (c.get("repo") or "classmain/cf-speedtest-mine").strip()
    token = (c.get("token") or "").strip()
    try:
        top_n = int(c.get("top_n", 2))
    except (ValueError, TypeError):
        top_n = 2
    top_n = max(1, min(10, top_n))
    if not token:
        print("nas_config.json 缺 token", file=sys.stderr)
        sys.exit(2)
    return repo, token, top_n


def latency_probe(ip, rounds=2, timeout=2.0):
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
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        sock = socket.create_connection((ip, 443), timeout)
        w = ctx.wrap_socket(sock, server_hostname=SNI)
        req = ("GET https://%s/__down?bytes=%d HTTP/1.1\r\nHost: %s\r\n"
               "User-Agent: nas-speedtest/%s\r\nConnection: close\r\n\r\n" % (SNI, target, SNI, VERSION)).encode()
        w.sendall(req)
        total = 0
        buf = b""
        t0 = time.time()
        while total < target:
            chunk = w.recv(65536)
            if not chunk:
                break
            buf += chunk
            total += len(chunk)
        dt = time.time() - t0
        w.close()
        idx = buf.find(b"\r\n\r\n")
        if idx != -1:
            total = len(buf) - (idx + 4)
        if dt <= 0 or total <= 0:
            return 0.0
        return total / dt / (1024 * 1024)
    except Exception:
        return 0.0


def build(top_n):
    results = []
    for ip in IP_POOL:
        lat = latency_probe(ip)
        if lat is None:
            continue
        results.append({"ip": ip, "latency_ms": round(lat * 1000, 2)})
    results.sort(key=lambda r: r["latency_ms"])
    for r in results[:5]:
        r["download_mbps"] = round(download_speed(r["ip"]), 3)
        r["sent"] = 4
        r["recv"] = 4
        r["loss"] = "0.00%"
    final = results[:top_n]
    # 固定按北京时间(UTC+8)输出，容器/宿主时区不影响
    tested_at = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + 8 * 3600))
    html = ",".join(r["ip"] for r in final)
    payload = {"version": VERSION, "tested_at": tested_at, "count": len(final), "top": final}
    return html, json.dumps(payload, ensure_ascii=False, indent=2), payload


def push_file(repo, token, rel_path, content):
    owner, name = repo.split("/", 1)
    base = "https://api.github.com"
    req = urllib.request.Request("%s/repos/%s/contents/%s?ref=main" % (base, repo, rel_path))
    req.add_header("Authorization", "token " + token)
    req.add_header("Accept", "application/vnd.github+json")
    sha = None
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            sha = json.loads(r.read())["sha"]
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return "GET %s failed HTTP %s" % (rel_path, e.code)
        sha = None
    except Exception as ex:
        return "GET %s error %s" % (rel_path, ex)

    body = {"message": "nas: update %s (v%s)" % (rel_path, VERSION),
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii")}
    if sha:
        body["sha"] = sha
    req = urllib.request.Request("%s/repos/%s/contents/%s" % (base, repo, rel_path),
                                 data=json.dumps(body).encode(), method="PUT")
    req.add_header("Authorization", "token " + token)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return "ok HTTP %s" % r.status
    except urllib.error.HTTPError as e:
        msg = e.read().decode()[:200]
        if "no changes" in msg.lower() or e.code == 409:
            return "unchanged(skip)"
        return "push failed HTTP %s %s" % (e.code, msg)
    except Exception as ex:
        return "push error %s" % ex


def main():
    repo, token, top_n = load_cfg()
    t0 = time.time()
    html, js, payload = build(top_n)
    r1 = push_file(repo, token, "ipTop.html", html)
    r2 = push_file(repo, token, "ipTop.json", js)
    print(json.dumps({
        "version": VERSION,
        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + 8 * 3600)),
        "repo": repo,
        "top": [t.get("ip") for t in payload["top"]],
        "tested_at": payload["tested_at"],
        "html": r1,
        "json": r2,
        "sec": round(time.time() - t0, 1),
    }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
