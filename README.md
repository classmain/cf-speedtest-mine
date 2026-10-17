# cf-speedtest-mine

自建的「CF 优选 IP」自动测速 + 展示页，机制复刻 `ip.164746.xyz`，**彻底不依赖原作者**：
不引用作者的 IP 池、不改任何 Cloudflare 账号、不配任何密钥。

## 它能做什么
- 每隔 6 小时（GitHub 定时）自动测一批 Cloudflare 优选 IP，挑出**延迟最低的前 2 个**。
- 网页 `index.html` 实时读取测速结果，显示「IP + 延迟 + 下载速度 + 测速时间」，样式与原网站一致。

## 文件说明
| 文件 | 作用 |
|---|---|
| `speedtest.py` | 测速脚本：读 `ip_pool.txt` → 测延迟/下载 → 取 Top2 → 写 `ipTop.html`（纯文本）与 `ipTop.json`（结构化） |
| `ip_pool.txt` | 要测的 Cloudflare IP 清单（一行一个，可增量维护） |
| `index.html` | 展示网页：`fetch ./ipTop.json` 实时渲染表格 |
| `.github/workflows/cf.yml` | 每 6h + 手动 + push 时自动跑测速并回写数据 |
| `ipTop.html` / `ipTop.json` | 数据产物（自动生成，已纳入仓库，被 workflow 更新） |
| `VERSION` | 当前版本号（`1.0`） |

## 本地跑一次
```bash
python speedtest.py
# 会生成/更新 ipTop.html 与 ipTop.json，并打印结果
```

## 跑测试
```bash
python tests/test_speedtest.py
```

## 部署到 GitHub Pages
1. 建 GitHub 仓库（本目录下内容）并 `git push`。
2. 仓库 Settings → Pages → 选 `main` / 根目录。
3. 几分钟后即可访问 `https://<你>.github.io/<仓库名>/`。
4. 定时任务由 `cf.yml` 自动接管，无需你的电脑在线。

## 自定义
- 想测哪些 IP → 改 `ip_pool.txt`。
- 想取前几个 → 默认前 2；`speedtest.py` 支持环境变量 `TOP_N` 覆盖。

> 注意：定时测速在 GitHub Actions 海外 runner 上执行，测的是「海外 → Cloudflare」延迟，
> 结果里的「具体哪两个 IP、延迟多少」不一定与原网站一致（测量起点不同）。样式与机制一致。
