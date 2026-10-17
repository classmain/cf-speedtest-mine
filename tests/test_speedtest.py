#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# test_speedtest.py · 版本号 v1.0 (2026-10-17 14:12 +08:00)
# 改动记录：v1.0 校验 speedtest.py 输出合法：IP 数量/格式、ipTop.json 结构、ipTop.html 解析。
# 本测试【不依赖真实网络】：monkeypatch 掉 latency_probe / download_speed，
# 所以本地、CI 都能稳定跑绿。
# ============================================================================

import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, PROJ)

import speedtest  # noqa: E402


PASS = 0
FAIL = 0


def check(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [OK] " + msg)
    else:
        FAIL += 1
        print("  [FAIL] " + msg)


# ---------- 1. is_valid_ipv4 ----------
print("== is_valid_ipv4 ==")
check(speedtest.is_valid_ipv4("104.18.40.100") is True, "合法 IPv4 返回 True")
check(speedtest.is_valid_ipv4("256.1.1.1") is False, "第 1 段 >255 返回 False")
check(speedtest.is_valid_ipv4("1.2.3") is False, "段数不足返回 False")
check(speedtest.is_valid_ipv4("a.b.c.d") is False, "非数字返回 False")
check(speedtest.is_valid_ipv4("0.0.0.0") is True, "0.0.0.0 合法")


# ---------- 2. run() 不联网，输出结构正确 ----------
print("== run() 输出结构 ==")
# 造一个小的 IP 池
ips = ["104.18.40.100", "104.18.37.247", "172.67.130.82"]
tmp = tempfile.mkdtemp()
pool_path = os.path.join(tmp, "pool.txt")
with io.open(pool_path, "w", encoding="utf-8") as f:
    f.write("# header comment\n")
    for ip in ips:
        f.write(ip + "\n")

# monkeypatch：按顺序返回固定延迟，且全部「连通」
fake_latency = {"104.18.40.100": 0.030, "104.18.37.247": 0.045, "172.67.130.82": 0.060}
fake_dl = {"104.18.40.100": 1.23, "104.18.37.247": 0.98, "172.67.130.82": 0.55}
speedtest.latency_probe = lambda ip, rounds=2, timeout=2.0: fake_latency.get(ip)
speedtest.download_speed = lambda ip, target=2 * 1024 * 1024, timeout=10.0: fake_dl.get(ip, 0.0)

os.environ["IP_POOL"] = pool_path
os.environ["OUT_DIR"] = tmp
os.environ["TOP_N"] = "2"
payload = speedtest.run()

check(payload["version"] == speedtest.VERSION, "ipTop.json 含 version 字段且等于模块 VERSION")
check(payload["count"] == 2, "count == TOP_N(2)")
check(len(payload["top"]) == 2, "top 列表长度 == 2")
check(payload["top"][0]["ip"] == "104.18.40.100", "延迟最低者排在第 1")
check(payload["top"][0]["download_mbps"] == 1.23, "Top 项带 download_mbps")
check(payload["tested_at"] and len(payload["tested_at"]) >= 19, "tested_at 时间戳存在")

# ipTop.html：纯文本逗号列表
with io.open(os.path.join(tmp, "ipTop.html"), encoding="utf-8") as f:
    html_text = f.read().strip()
check(html_text == "104.18.40.100,104.18.37.247", "ipTop.html 为逗号分隔前 2 个 IP")
check(all(speedtest.is_valid_ipv4(x) for x in html_text.split(",")), "ipTop.html 每个 IP 都是合法 IPv4")

# ipTop.json 可被 json 解析且结构完整
with io.open(os.path.join(tmp, "ipTop.json"), encoding="utf-8") as f:
    jp = json.load(f)
for k in ("version", "tested_at", "count", "top"):
    check(k in jp, "ipTop.json 含字段 " + k)

# ---------- 3. 真实文件（仓库内 ip_pool.txt）能读 ----------
print("== 仓库 ip_pool.txt 可读性 ==")
with io.open(os.path.join(PROJ, "ip_pool.txt"), encoding="utf-8") as f:
    real_ips = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
check(len(real_ips) >= 10, "仓库 ip_pool.txt 至少 10 个 IP（实际 %d）" % len(real_ips))
check(all(speedtest.is_valid_ipv4(x) for x in real_ips), "仓库 ip_pool.txt 全部为合法 IPv4")

print("\n== 结果 == PASS=%d FAIL=%d ==" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
