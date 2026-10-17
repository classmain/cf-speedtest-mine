#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# runner.py · 版本号 v1.3.0 (2026-10-17 18:40 +08:00)
# 飞牛 fnOS 原生应用「CF优选IP测速」的常驻进程（REST 版，无 git 依赖）。
#
# 机制：
#   1) 读配置 JSON（cmd/main 从 TRIM_PKGETC 传入）：repo / token / interval_hours
#   2) 每小时：跑 speedtest.py（同目录）→ 生成 ipTop.html / ipTop.json
#   3) 通过 GitHub REST Contents API 把这两个文件推回仓库 main 分支
#      （只有内容有变化才推，避免无谓 commit）
#   4) 写 status.json / runner.log 供 cmd/main 的 status 命令与排查
#
# 凭证：token 只存在于飞牛本地配置文件，**绝不写进任何仓库 / git config**。
# 依赖：仅 Python3 标准库（urllib / json / ssl）。飞牛无需装 git。
#
# 对外暴露版本：下方 VERSION 常量 + status.json 的 version 字段。
#
# 用法（由 cmd/main 调用）：
#   python3 runner.py --config <config.json> --data <dir> [--once]
#     --once  跑一轮就退出（供 start 前的自检 / 手动）；缺省则常驻循环。
# ============================================================================

import base64
import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.error

VERSION = "1.3.0"
_HERE = os.path.dirname(os.path.abspath(__file__))
_stop = False


def _term(signum, frame):
    global _stop
    _stop = True


def parse_cli(argv):
    cfg = data = None
    once = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--config" and i + 1 < len(argv):
            cfg, i = argv[i + 1], i + 2
        elif a == "--data" and i + 1 < len(argv):
            data, i = argv[i + 1], i + 2
        elif a == "--once":
            once, i = True, i + 1
        else:
            i += 1
    return cfg, data, once


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        c = json.load(f)
    repo = (c.get("repo") or "classmain/cf-speedtest-mine").strip()
    token = (c.get("token") or "").strip()
    try:
        interval_h = int(float(c.get("interval_hours", 1)))
    except (ValueError, TypeError):
        interval_h = 1
    interval_h = max(1, min(24, interval_h))
    if not repo or "/" not in repo or not token:
        print("[runner] config 缺少 repo 或 token: " + path, file=sys.stderr)
        sys.exit(2)
    return repo, token, interval_h


def measure_once(repo, token, data_dir):
    """跑 speedtest.py，REST 推两个数据文件。返回 status dict。"""
    import subprocess
    t0 = time.time()
    proc = subprocess.run([sys.executable, os.path.join(_HERE, "speedtest.py")],
                          cwd=_HERE, capture_output=True, text=True, timeout=900,
                          env=dict(os.environ, OUT_DIR=data_dir))
    if proc.returncode != 0:
        return {"ok": False, "stage": "speedtest", "detail": proc.stderr[-500:] or "rc=%s" % proc.returncode}

    html_path = os.path.join(data_dir, "ipTop.html")
    json_path = os.path.join(data_dir, "ipTop.json")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    with open(json_path, "r", encoding="utf-8") as f:
        jsobj = json.load(f)
    js = json.dumps(jsobj, ensure_ascii=False, indent=2)

    top_ips = [t.get("ip") for t in jsobj.get("top", [])]
    tested_at = jsobj.get("tested_at")

    # 推 HTML
    html_status, html_detail = push_file(repo, token, "ipTop.html", html)
    json_status, json_detail = push_file(repo, token, "ipTop.json", js)

    ok = html_status and json_status
    status = {
        "version": VERSION,
        "last_run": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ok": ok,
        "detail": {"ipTop.html": html_detail, "ipTop.json": json_detail},
        "top_ip": top_ips,
        "tested_at": tested_at,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    with open(os.path.join(data_dir, "status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    with open(os.path.join(data_dir, "runner.log"), "a", encoding="utf-8") as f:
        f.write(json.dumps(status, ensure_ascii=False) + "\n")
    print("[runner]", json.dumps(status, ensure_ascii=False), flush=True)
    return status


def push_file(repo, token, rel_path, content):
    """用 REST Contents API 覆盖/新建 repo 里某文件。返回 (是否已更新, 说明)。"""
    owner, name = repo.split("/", 1)
    base = "https://api.github.com"
    sha = None
    # 先取现有文件 sha
    req = urllib.request.Request("%s/repos/%s/contents/%s?ref=main" % (base, repo, rel_path))
    req.add_header("Authorization", "token " + token)
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            sha = json.loads(r.read())["sha"]
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return False, "GET %s failed: HTTP %s %s" % (rel_path, e.code, e.read()[:120])
        sha = None  # 不存在 → create
    except Exception as ex:
        return False, "GET %s error: %s" % (rel_path, ex)

    # GitHub Contents API 要求 content 为 base64 字符串（编码后传原文 utf-8）
    body = {"message": "auto: update %s (v%s)" % (rel_path, VERSION),
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
            st = r.status
            return st in (200, 201), "HTTP %s" % st
    except urllib.error.HTTPError as e:
        # 常见：409 "would create a commit with no changes"（内容没变）
        msg = e.read().decode()[:200]
        if "no changes" in msg.lower() or e.code == 409:
            return True, "unchanged (skip)"
        return False, "HTTP %s %s" % (e.code, msg)
    except Exception as ex:
        return False, "PUT %s error: %s" % (rel_path, ex)


def main():
    import signal
    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)

    cfg_path, data_dir, once = parse_cli(sys.argv[1:])
    if not cfg_path or not data_dir:
        print("usage: runner.py --config <json> --data <dir> [--once]", file=sys.stderr)
        sys.exit(2)
    os.makedirs(data_dir, exist_ok=True)
    repo, token, interval_h = load_config(cfg_path)

    print("[runner] v%s start repo=%s interval=%sh once=%s" % (VERSION, repo, interval_h, once), flush=True)
    measure_once(repo, token, data_dir)

    if once:
        return

    wait_s = interval_h * 3600
    while not _stop:
        slept = 0
        while not _stop and slept < wait_s:
            time.sleep(1)
            slept += 1
        if _stop:
            break
        measure_once(repo, token, data_dir)
    print("[runner] stopped", flush=True)


if __name__ == "__main__":
    main()
