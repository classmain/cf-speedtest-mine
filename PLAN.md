# CF 优选 IP 独立部署 · 实施计划

版本：PLAN v1.0（2026-10-17 11:58 +08:00）
作者：WorkBuddy / 待 classmain 确认

> 目标：复刻 `ip.164746.xyz`（ZhiXuanWang/cf-speed-dns）的功能，但**彻底不依赖作者**，
> 数据源、网页、DNS 自动优化全部自建，部署到 classmain 自己的 Cloudflare 账号。

---

## 一、原系统拆解（已坐实的证据）

| 文件 | 字节 | 作用 |
|---|---|---|
| `index.html` | 3499 | GitHub Pages 静态展示页，测速表数据是**写死的快照** |
| `ipTop.html` | 28 | 纯文本优选 IP 池，当前 `104.18.40.100,104.18.37.247`，**给脚本消费** |
| `dnscf.py` | 6121 | 读作者 `ip.164746.xyz/ipTop.html` → 调 CF API 改 A 记录 → 可 PushPlus 推送 |
| `dnspod.py` | 10635 | 同上但走腾讯 DNSPod（CF 用户用不到，**不迁移**） |
| `.github/workflows/dns_cf.yml` | 752 | 每 6h（`0 */6 * * *`）跑 dnscf.py |
| `.github/workflows/sync.yml` | 1185 | fork 仓库**每天 force 拉上游**——独立版必须**彻底移除** |
| `CNAME` | 13 | `ip.164746.xyz`（作者域名） |

**dnscf.py 4 步逻辑**：
1. `GET https://ip.164746.xyz/ipTop.html`（硬编码作者地址 → 独立版要改掉）
2. 读 CF 里 `CF_DNS_NAME` 的 A 记录（只读 A 类型，避免 400）
3. 逐条更新成优选 IP（相同则 skip）
4. 可选 PushPlus 微信推送

**要配的 4 个 secret**：`CF_API_TOKEN`、`CF_ZONE_ID`、`CF_DNS_NAME`、（可选 `PUSHPLUS_TOKEN`）。

---

## 二、与作者方案的差异（本方案做了什么改动）

| 维度 | 作者方案 | 本方案（独立版） |
|---|---|---|
| 数据源 | 硬编码 `ip.164746.xyz/ipTop.html`（国内精选池） | **自建** `speedtest.py` 测 CF IP 池 → 写自己仓库 `ipTop.html` |
| 网页 | 静态快照（不联动） | **实时** 拉自己仓库 `ipTop.json`（你换 IP，网页跟着变） |
| 上游同步 | `sync.yml` 每天拉作者上游 | **移除**，完全独立 |
| fork 风险 | 改动会被上游冲掉 | **不 fork，新建独立仓库** |

**已知代价（需你接受）**：自建测速的 runner 在 GitHub Actions（**海外**），
测出的是「海外 → CF」延迟，可能不如作者的「国内 → CF」精选池那么针对国内用户。
这是"彻底不依赖作者"的固有代价。

---

## 三、新仓库结构 `cf-speed-dns-mine`

```
cf-speed-dns-mine/
├── VERSION                 # 版本号文件（对外暴露：cat VERSION / 页面 fetch 也可读）
├── README.md               # 使用说明 + 配置清单
├── requirements.txt        # requests
├── ip_pool.txt             # CF 候选 IP 池（30~50 个已知 anycast IP，测速对象）
├── speedtest.py            # 测速：连接 ip_pool.txt 每个 IP 的 443 端口，测延迟+下载速度，取 Top N
├── dnscf.py                # 读【本地仓库】ipTop.html → 调 CF API 改 A 记录（去掉硬编码作者地址）
├── index.html              # 展示页：JS 实时 fetch 本仓库 ipTop.json 渲染测速表
├── ipTop.html              # 生成产物（纯文本 IP 列表，兼容 dnscf.py 解析）
├── ipTop.json              # 生成产物（结构化：ip/延迟/丢包/下载/测速时间，给网页用）
├── .github/workflows/cf.yml  # 单 workflow：generate + dns 串联，每 6h + 手动触发
└── tests/
    ├── test_speedtest.py   # 校验 speedtest 输出格式（IP 数量/合法性/json 结构）
    └── test_dnscf.py       # mock CF API，校验 dnscf 逻辑（更新/跳过/数量上限）
```

---

## 四、模块实现细节

### 模块 A：独立数据源 `speedtest.py`
1. 读 `ip_pool.txt`（每行一个 CF IP，文件头带 `# v1.0` 版本声明）。
2. 对每个 IP：TCP 连接 `443`，多轮取最小/平均延迟；再对选中的 Top 5 测下载速度。
3. 排序取 **Top N（默认 2，可配 `TOP_N` 环境变量）**。
4. 双写：
   - `ipTop.html`：纯文本逗号列表（如 `104.18.40.100,104.18.37.247`）——兼容 dnscf.py。
   - `ipTop.json`：`[{"ip","sent","recv","loss","latency","dl_speed","tested_at"}]`——给网页。
5. **只有当优选 IP 变化时才 commit 推送**（避免每 6h 刷无意义 commit）。

### 模块 B：DNS 自动优化 `dnscf.py`
1. **读本地仓库 `ipTop.html`**（通过 `actions/checkout` 已在 runner 上），不再抓作者地址。
   路径可用环境变量 `IP_TOP_FILE` 覆盖，默认 `./ipTop.html`。
2. 读 CF A 记录（`CF_DNS_NAME`），逐条更新；相同 skip；IP 多于记录数则只更新前 N 条。
3. 可选 PushPlus 推送。
4. **坑**：CF 里 `CF_DNS_NAME` 需**预建 2 条 A 记录**（对应 2 个 IP）；建少则第 2 个写不进去。

### 模块 C：展示网页 `index.html`
1. 保留作者的表格样式（IP/已发送/已接收/丢包/延迟/下载/测速时间 + 复制按钮 + GitHub star 按钮）。
2. `DOMContentLoaded` 时 `fetch('/ipTop.json')`（部署到 Cloudflare Pages 后同域，CORS 无障碍）渲染表格。
3. **不引用作者任何资源**（star 按钮改成 classmain 自己仓库，或去掉）。

### Workflow `.github/workflows/cf.yml`
- 触发：`cron: 0 */6 * * *` + `workflow_dispatch`（手动）。
- 串联：
  1. checkout + setup-python
  2. 跑 `speedtest.py` → 若 `ipTop` 变化则 commit & push
  3. 重新读 `ipTop.html` → 跑 `dnscf.py`（带 `CF_API_TOKEN` 等 secrets）
- 顺序保证 DNS 永远用**最新**测速结果。

### 版本声明（遵守你的规矩）
- 每个 `.py` / `.html` / `.txt` 文件**头部加版本注释**：`# v1.0 (2026-10-17 12:00 +08:00) 初始独立版`。
- 统一版本号集中在 `VERSION` 文件（`1.0`），供外部读取；改动时 `speedtest.py` 在写 `ipTop.json` 时把 `version` 字段带进去，网页可展示。

---

## 五、你需要提供的 3 个值

| # | 项 | 说明 | 示例 |
|---|---|---|---|
| 1 | **DNS 目标域名 `CF_DNS_NAME`** | 你要让**哪个域名**解析到最优 CF IP | `cf.yourdomain.com` |
| 2 | **网页域名** | 展示页部署到 CF Pages 用的域名 | `speedtest.yourdomain.com`（或直接用 Pages 默认子域） |
| 3 | **CF 凭证** | `CF_API_TOKEN`（需 `Zone:DNS:Edit`）+ `CF_ZONE_ID` | 后面存进 GitHub Secrets，我先不碰 |

> 没有 1，模块 B 无从下手；没有 3，DNS 写不进去。2 没有也能先用 Pages 默认子域。

---

## 六、测试清单（改完必须全绿才交付）

| 测试 | 校验点 |
|---|---|
| `test_speedtest.py` | 输出 IP 数量 ≤ TOP_N；IP 是合法 IPv4；`ipTop.json` 结构完整（含 version 字段） |
| `test_dnscf.py` | mock CF API：IP 相同→skip；IP 不同→PUT；IP 多于记录数→只更新前 N；缺 secret→报错不崩 |
| 手工验证 | `workflow_dispatch` 手动触发一次 → 看 CF 控制台 A 记录确实变了 → 网页 fetch 出非空数据 |

## 七、风险 / 注意事项
1. **海外测速偏差**（已告知，接受）。
2. **CF 免费 cron 上限**：6h 一次，远没到 3000 runs/月，无压力。
3. **预建 A 记录数量坑**：建 2 条。
4. **测速连通性**：Actions runner（海外）能连 CF 443，没问题。
5. **IP 池质量**：`ip_pool.txt` 给的 IP 决定测速上限，后续可增量维护。

---
## 交付节奏
1. 你补 3 个值 + 回复"确认"。
2. 我建 `cf-speed-dns-mine/` 全部文件（带版本声明 + 测试）。
3. 本地跑 `tests/` 全绿。
4. 给你 GitHub Secrets 配置清单 + CF 预建记录清单（可粘贴操作）。
5. 你推仓 + 配 secret，手动触发验收。
