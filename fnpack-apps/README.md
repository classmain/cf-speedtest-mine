# 飞牛 fnOS 原生应用 · CF优选IP测速（cf-speedtest）

## 这是什么
把 `cf-speedtest-mine` 的测速逻辑打包成**飞牛 fnOS 原生应用（.fpk）**。
装进飞牛应用中心后：应用卡片可「启动 / 停止」，后台常驻 runner 每隔 N 小时
在你飞牛（大陆网络）上测一次 CF 优选 IP，通过 GitHub REST API 推回仓库，
GitHub Pages 自动重建，网页实时显示「大陆 → CF」最优 IP。

## 目录结构（fnpack 约定）
```
fnpack-apps/cf-speedtest/
├── manifest              # 应用元信息（appname/version/platform...）
├── ICON.PNG              # 64x64 图标（make_icons.py 生成）
├── ICON_256.PNG          # 256x256 图标（make_icons.py 生成）
├── app/
│   ├── runner.py         # 常驻进程：定时测速 + REST 推送 GitHub
│   ├── speedtest.py      # 测速核心（读 ip_pool.txt，写 ipTop.html/json）
│   └── ip_pool.txt       # CF IP 池（可改）
├── cmd/
│   └── main              # 生命周期：start / stop / status
├── config/
│   ├── privilege         # 运行用户（专用包用户，最小权限）
│   └── resource          # {}（native 后台应用不声明系统资源）
└── wizard/
    ├── install           # 安装向导：填 repo / token / 间隔
    └── config            # 应用设置：可改 repo / token / 间隔
```

## 构建 .fpk（在你电脑上，不是飞牛上）
1. 装飞牛官方工具 **fnpack**（官网 / 应用开发者群提供）。
2. 进入本目录的**父级**（`fnpack-apps/`，因为 fnpack 认的是 `cf-speedtest/` 这个应用目录）：
   ```bash
   cd fnpack-apps
   fnpack build cf-speedtest     # 或 fnpack build --app cf-speedtest
   ```
3. 产出 `cf-speedtest.fpk`。

> 若 fnpack 需要完整工程目录，把 `cf-speedtest/` 直接喂给 `fnpack build` 即可。
> JSON 文件务必**保持无注释、无尾逗号**（fnpack 对 JSON 零容忍）。

## 安装到飞牛
- 应用中心 → **手动安装** → 拖入 `cf-speedtest.fpk`。
- 安装向导会要你填：
  - `GitHub 仓库`（默认 `classmain/cf-speedtest-mine`）
  - `GitHub Token`（fine-grained，勾 **Contents: Read and write**）
  - `测速间隔（小时）`（默认 1）
- 装完点「启动」，应用中心卡片显示运行中；停止即 kill。

## 工作原理（数据流）
```
飞牛 runner.py（每 N 小时）
   → 跑 speedtest.py（大陆网络实测）
   → GitHub REST Contents API 覆盖 ipTop.html / ipTop.json
   → 仓库 main 更新 → GitHub Pages 自动重建
   → https://classmain.github.io/cf-speedtest-mine/ 显示最新大陆优选 IP
```

## 安全
- token 只写在飞牛本地 `config.json`（chmod 600），**绝不进 git 仓库**。
- 应用以专用包用户（`cf_speedtest_user`）运行，非 root。

## 版本
`VERSION` 文件统一 `1.3.0`；`runner.py` 在 `status.json` 的 `version` 字段对外暴露。
