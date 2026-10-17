#!/bin/bash
# ============================================================================
# nas_setup.sh · 版本号 v1.1 (2026-10-17 17:05 +08:00)
# 改动记录：
#   v1.1 有变化才 commit+push（避免每小时空 commit 触发 Pages 无谓重建）；
#        crontab 条目幂等（重跑先清旧再写）；token 只放本地环境变量、不写死进仓库。
#   v1.0 初版。
#
# 用途：在飞牛 NAS（国内网络）上每小时跑一次大陆侧 CF 测速，把结果推回仓库，
#       GitHub Pages 自动重建 → 网页显示「大陆 → CF」最优 IP。
#
# 使用（SSH 进飞牛后）：
#   export GITHUB_TOKEN="github_pat_你的token"
#   cd 你想放代码的目录      # 如 cd ~
#   bash nas_setup.sh
#
# ⚠️ 前置：必须先把仓库的 .github/workflows/cf.yml 删掉（否则海外定时会和 NAS 打架）。
# ============================================================================

set -e
REPO="classmain/cf-speedtest-mine"
TOKEN="$GITHUB_TOKEN"

if [ -z "$TOKEN" ]; then
    echo "请先:  export GITHUB_TOKEN=\"github_pat_xxx\""; exit 1
fi

WORKDIR="$(pwd)/cf-speedtest-mine"

echo "=== ① clone 仓库 ==="
if [ -d "$WORKDIR/.git" ]; then
    cd "$WORKDIR" && git pull
else
    git clone "https://classmain:${TOKEN}@github.com/classmain/${REPO}.git" "$WORKDIR"
    cd "$WORKDIR"
    git remote set-url origin "https://github.com/classmain/${REPO}.git"
fi
echo "仓库路径: $(pwd)"

echo "=== ② 确认 python3 / git ==="
command -v python3 &>/dev/null || { echo "装 python3..."; apt-get update -qq && apt-get install -y -qq python3; }
command -v git &>/dev/null      || { echo "装 git...";   apt-get install -y -qq git; }
echo "python3: $(python3 --version 2>&1)"

echo "=== ③ 手动跑一次验证 ==="
python3 speedtest.py

echo "=== ④ 写入 crontab（每小时第 5 分钟，有变化才推） ==="
# 定时任务体：测速 → 仅当 ipTop 变化才 commit+push
CRON_LINE="5 * * * * cd ${WORKDIR} && GITHUB_TOKEN=${TOKEN} python3 speedtest.py && if ! git diff --quiet ipTop.html ipTop.json 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then git add ipTop.html ipTop.json; git commit -m 'mainland speedtest $(date +\%F)' ; fi && git push --quiet https://classmain:${TOKEN}@github.com/classmain/${REPO}.git main"

crontab -l 2>/dev/null | grep -v "cf-speedtest-mine" > /tmp/cron_new.txt || true
echo "$CRON_LINE" >> /tmp/cron_new.txt
crontab /tmp/cron_new.txt
rm -f /tmp/cron_new.txt

echo "=== 当前 crontab ==="
crontab -l | grep "cf-speedtest-mine"
echo ""
echo "=== 完成 ==="
echo "之后每小时第 5 分钟自动在大陆测速并推回，网页即更新成大陆数据。"
echo "手动触发: cd ${WORKDIR} && python3 speedtest.py && git add ipTop.html ipTop.json && git commit -m manual && git push"
echo ""
echo "提醒: crontab 里含 token（在 ${WORKDIR} 本机），NAS 断电/token 过期(如 30 天)会静默停推，需重跑本脚本换新 token。"
