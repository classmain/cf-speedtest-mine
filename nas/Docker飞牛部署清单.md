# 飞牛 Docker 部署清单（cf-sdtest，v1.4.0）

> 目标：用飞牛**自带的 Docker** 跑「CF 优选 IP 测速」，每小时自动推回 GitHub，
> 让 `https://classmain.github.io/cf-speedtest-mine/` 显示大陆最优 IP。
> 不用装 fnpack、不 build 镜像、不推 registry——只挂载 3 个文件跑官方 python 镜像。

## 前提
- 飞牛装过 **Docker**（飞牛应用中心里那个，多数飞牛自带；没有就装一次）。
- 一个能写 `classmain/cf-speedtest-mine` 的 GitHub token（fine-grained，勾 **Contents: Read and write**）。
- 飞牛能拉 `python:3.12-slim` 镜像（大陆可能要配 Docker 镜像加速源，见排错）。

## 三个文件放同一目录
在飞牛上找个目录，比如 `~/cf-sdtest/`，放这 3 个文件：
| 文件 | 来源 |
|---|---|
| `nas_speedtest.py` | 从 GitHub `cf-speed-dns-mine` 仓库 `nas/nas_speedtest.py` 下载 |
| `nas_config.json` | 自己建（内容见下） |
| `docker-compose.yml` | 从 GitHub 仓库 `nas/docker-compose.yml` 下载 |

## 步骤

### ① 建配置文件
```bash
mkdir -p ~/cf-sdtest && cd ~/cf-sdtest
# 把下面内容存成 nas_config.json（把 token 换成你的 github_pat_...）：
cat > nas_config.json <<'EOF'
{
  "repo": "classmain/cf-speedtest-mine",
  "token": "这里换成你的token",
  "top_n": 2
}
EOF
chmod 600 nas_config.json
```

### ② 拉镜像（可选，提前拉好省得首次启动卡）
```bash
docker pull python:3.12-slim
```

### ③ 启动
```bash
docker compose up -d
docker compose logs -f        # 看第一次测速输出，出现 "ok HTTP 200" 即成功
```

### ④ 之后
- 容器每小时自动跑一次（改频率：编辑 compose 里 `INTERVAL_SEC`，再 `docker compose up -d` 重建）。
- 看日志：`docker logs -f cf-sdtest`
- 停：`docker compose down`；启：`docker compose up -d`
- 飞牛 Docker 图形界面里也能看到 `cf-sdtest` 这个容器。

## 排错
| 现象 | 原因 | 处理 |
|---|---|---|
| `pull ... timeout` | 拉不动官方镜像 | 给 Docker 配**镜像加速源**（飞牛 Docker 设置里），或用国内源 `docker.mirrors.ustc.edu.cn/python:3.12-slim` |
| `HTTP 403` | token 没 Contents 写权 | 换带 Contents:RW 的 token |
| `no such file ... nas_speedtest.py` | 挂载路径不对 | 确认 3 文件在 compose 所在目录的**同级**（compose 里用的是 `./` 相对路径） |
| 测速一直 `0.00` | 飞牛出不去 443 或某段 IP 被墙 | 正常，Top 会挑能通的那几个 |

## 内存说明
平时容器只 `sh + sleep`（几 MB）；每轮测速时 python 峰值 ~40MB，跑完回落。整体系列低于常驻 Python 进程。
