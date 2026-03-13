---
name: deploy
description: JRebel License Server 项目发版部署。当用户提到"发版"、"部署"、"上线"、"发布"、"deploy"、"release"、"更新服务"、"部署前端"、"部署后端"时触发。支持后端（Docker 容器零停机部署到 Linux 服务器）和前端（Cloudflare Pages 部署）。
---

# JRebel License Server 发版部署

## 项目架构

- **后端**: Flask (Python) 应用，Docker 容器化，部署在 Linux 服务器上
- **前端**: 纯静态 HTML，部署在 Cloudflare Pages 上
- **域名**: 前端 `idea.156354.xyz`，后端 `ideabackend.156354.xyz`
- **流量入口**: Cloudflare Tunnel (cloudflared) 将流量转发到后端容器

## 发版流程

### 1. 提交代码

```bash
git add . && git commit -m "<commit message>" && git push
```

### 2. 服务器拉取代码

通过 Linux Server MCP 在远程服务器执行：

```bash
git -C /root/jrebel-license-server pull
```

### 3. 后端部署（服务器上执行）

通过 Linux Server MCP 执行，使用 `deploy-smooth.sh` 脚本实现零停机部署：

```bash
bash /root/jrebel-license-server/deploy-smooth.sh deploy
```

脚本会自动完成：构建 Docker 镜像 → 启动新容器（端口交替 58081/58082）→ 健康检查 → 流量切换 → 停止旧容器。

仅后端时可跳过前端：

```bash
FRONTEND_DEPLOY=false bash /root/jrebel-license-server/deploy-smooth.sh deploy
```

其他命令：
- `status` — 查看容器状态
- `logs` — 查看日志
- `rollback` — 回滚到上一个版本
- `stop` — 停止所有容器

### 4. 前端部署（本机执行）

前端部署到 Cloudflare Pages，在本机使用 wrangler 执行：

```bash
cd <project-root>
npx wrangler pages deploy ./frontend --project-name=jrebel-web --branch=main --commit-dirty=true
```

首次使用会触发 OAuth 登录 Cloudflare。

### 5. 验证

- 前端: `curl -I https://idea.156354.xyz/`
- 后端: `curl -I https://ideabackend.156354.xyz/api/status`
- 后台: `curl -I https://idea.156354.xyz/admin`

## 注意事项

- Cloudflare Pages 默认开启 Pretty URLs，会自动将 `/admin` 映射到 `admin.html`，**不要**在 `_redirects` 中配置 `/admin -> /admin.html` 的 rewrite 规则，否则会导致 308 重定向循环
- 后端的 `/admin` 路由会 302 重定向到前端 `https://idea.156354.xyz/admin.html`，这是为了兼容直接访问后端域名的场景
- 服务器环境变量（`SECRET_KEY`、`CF_API_TOKEN`、`CF_ACCOUNT_ID` 等）已在服务器上配置，无需每次传入
- 部署脚本 `deploy-smooth.sh` 在服务器上可能是旧版本（不含 `frontend` 子命令），前端部署优先在本机用 wrangler 执行
