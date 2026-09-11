# 安装与部署

本文适用于已有 NewAPI、Docker Compose 和一个本人拥有的 ChatGLM 会员账号的部署。

## 1. 准备条件

- Docker Engine 24+ 和 Docker Compose v2。
- NewAPI 与 adapter 能加入同一个 Docker network。
- 一个 ChatGLM Web refresh token。
- 不要把 adapter 的 8000 端口发布到公网。

本文默认共享网络名为 `ai-backend`。如果 NewAPI 使用其他网络名，请把后文的 `ai-backend` 替换成实际名称。

## 2. 获取代码

```bash
git clone https://github.com/withgardener/chatglm-adapter.git
cd chatglm-adapter
```

## 3. 创建内部 API Key

这个 Key 只用于 NewAPI 调用 adapter，与 ChatGLM refresh token 完全不同。

```bash
openssl rand -hex 32
```

保存输出结果，后面写入 `.env` 的 `ADAPTER_INTERNAL_API_KEY`。

## 4. 创建配置文件

```bash
cp .env.example .env
```

编辑 `.env`，至少设置：

```dotenv
ADAPTER_INTERNAL_API_KEY=这里填上一步生成的随机值
CHATGLM_SIGN_SECRET=8a1317a7468aa3ad86e997d08f3f31cb
CHATGLM_TIMESTAMP_FORMAT=chatglm_checksum
```

其他 ChatGLM URL 已经按 2026-09-10 当前网页协议写入 `compose.example.yml`，通常不需要改动。

## 5. 写入 refresh token

refresh token 不要写进 `.env`、命令历史、Git 或 Docker image。创建 Docker secret 文件：

```bash
mkdir -p secrets
umask 077
printf '%s' '替换成你自己的 ChatGLM refresh token' > secrets/chatglm_refresh_token
chmod 600 secrets/chatglm_refresh_token
```

如果从已登录浏览器取值，请只读取自己账号的 `chatglm_refresh_token`，复制后立即关闭开发者工具；不要把 cookie、access token 或 HAR 发给别人。

### 5a. 可选：导入完整 Cookie header

如果只用 refresh token 时 refresh 接口返回 400/403（常见于机房 IP 被 WAF 拦截），改为导入自己账号已登录会话的完整 Cookie header。adapter 会从 Cookie 串中读取 `chatglm_refresh_token`，向上游透传整个 Cookie（含 WAF cookie），并把 refresh token rotation 原子写回该文件：

```bash
umask 077
printf '%s' '替换成完整 Cookie header（chatglm_refresh_token=...; chatglm_token=...; ...）' > secrets/chatglm_cookies
chmod 600 secrets/chatglm_cookies
```

cookie 文件必须是 0600 且容器内可写（rotation 会重写它），用 bind mount 而不是只读 Docker secret，并在 `.env` 中设置：

```dotenv
CHATGLM_COOKIES_FILE=/run/secrets/chatglm_cookies
```

设置了 `CHATGLM_COOKIES_FILE` 后 `chatglm_refresh_token` 文件不再需要。device ID 会自动取 token 中的 `device_id` claim，与浏览器保持一致；也可以用 `CHATGLM_DEVICE_ID` 显式指定。

注意：WAF cookie（`acw_tc`、`ssxmod_itna` 等）与导出时的浏览器会话和 IP 绑定且会过期；如果部署机出口 IP 与浏览器差异太大，透传 cookie 也可能不够，需要重新执行 live probe 确认。

## 6. 准备 Docker network

如果 NewAPI 已经使用 `ai-backend`，确认它存在：

```bash
docker network ls
```

如果它还不存在，可以创建：

```bash
docker network create ai-backend
```

如果 NewAPI 使用的是例如 `newapi_default`，不要重复创建 `ai-backend`；修改 `compose.example.yml` 最后的 `networks` 为 NewAPI 实际 network 名。

## 7. 启动 adapter

```bash
docker compose --env-file .env -f compose.example.yml up -d --build
```

检查状态：

```bash
docker compose -f compose.example.yml ps
docker inspect --format '{{json .State.Health}}' chatglm-adapter
```

健康检查只表示配置加载和进程正常，不会在响应中返回 token、UID、device ID 或 conversation ID。

查看日志时只看错误类别和状态，不要开启会记录请求内容的自定义调试日志：

```bash
docker compose -f compose.example.yml logs --tail=100 chatglm-adapter
```

## 8. 在 NewAPI 中添加渠道

在 NewAPI 新建 OpenAI-compatible 渠道：

```text
名称：ChatGLM Web
类型：OpenAI
Base URL：http://chatglm-adapter:8000
API Key：.env 中的 ADAPTER_INTERNAL_API_KEY
模型：chatglm-glm-5.3-flash
```

建议直接对外使用 `chatglm-glm-5.3-flash`，不要改成 `glm-5.3-flash`，避免与其他 GLM provider 冲突。

保存后使用 NewAPI 的渠道测试功能发送一条短消息。第一次请求会：

1. 使用 refresh token 获取 access token；
2. 同步 ChatGLM 网页时间并生成签名；
3. 创建一次临时 Web conversation；
4. 转换 SSE 为 OpenAI stream；
5. best-effort 清理 conversation。

## 9. 命令行验证

adapter 未发布宿主机端口时，推荐使用 NewAPI 渠道测试。若需要从同一 Docker network 验证，可临时运行一个 curl 容器：

```bash
docker run --rm --network ai-backend curlimages/curl:8.10.1 \
  -fsS http://chatglm-adapter:8000/health
```

验证模型列表：

```bash
docker run --rm --network ai-backend curlimages/curl:8.10.1 \
  -fsS http://chatglm-adapter:8000/v1/models \
  -H "Authorization: Bearer ${ADAPTER_INTERNAL_API_KEY}"
```

生产环境不要添加：

```yaml
ports:
  - "8000:8000"
```

## 10. 更新 refresh token

如果 ChatGLM 网页要求重新登录：

```bash
umask 077
printf '%s' '新的 refresh token' > secrets/chatglm_refresh_token.new
chmod 600 secrets/chatglm_refresh_token.new
mv secrets/chatglm_refresh_token.new secrets/chatglm_refresh_token
docker compose -f compose.example.yml up -d
```

adapter 运行时发生 refresh token rotation 时会对 secret 文件进行临时文件写入、权限设置和原子替换。

## 11. 常见问题

### `/health` 正常，但 NewAPI 渠道失败

检查：

- NewAPI 与 adapter 是否在同一个 Docker network；
- Base URL 是否为 `http://chatglm-adapter:8000`；
- API Key 是否与 `ADAPTER_INTERNAL_API_KEY` 完全一致；
- 模型名是否为 `chatglm-glm-5.3-flash`。

### 401 或 refresh rejected

不要把 access token 写入配置。确认 secret 文件中是当前账号的 refresh token，并检查账号是否在 ChatGLM 网页端要求重新登录。

refresh 返回 400/403 且 token 确认有效时，通常是 WAF 拦截了非浏览器特征请求（机房 IP、`python-httpx` UA 或缺少 WAF cookie）。确认 `CHATGLM_USER_AGENT` 未被改成非浏览器值；仍失败则按第 5a 节导入完整 Cookie header。

### 签名失败

确认：

- `CHATGLM_SIGN_SECRET` 没有被改动；
- `CHATGLM_TIMESTAMP_FORMAT=chatglm_checksum`；
- 容器能够访问 `https://chatglm.cn`；
- 宿主机时间没有严重漂移。

### 并发繁忙

单会员账号默认 `UPSTREAM_MAX_CONCURRENCY=1`。这是有意的安全默认值，不要先通过放大并发解决问题。

### 想升级版本

先备份 `secrets/chatglm_refresh_token`，再使用具体 Git tag 或 immutable image。不要使用 `latest`，升级前执行：

```bash
docker compose -f compose.example.yml build --no-cache
docker compose -f compose.example.yml up -d
```

回滚时使用上一个已验证的 Git commit/tag，不要修改 refresh token 文件内容。
