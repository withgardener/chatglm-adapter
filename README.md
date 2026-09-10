# chatglm-adapter

一个面向自有 ChatGLM 会员账号的薄型 OpenAI-compatible adapter。

```text
OpenAI client -> NewAPI -> chatglm-adapter -> ChatGLM Web private API
```

项目只实现 ChatGLM Web provider，不实现用户、额度、模型路由或多账号池。生产部署时 adapter 只加入 NewAPI 的内部 Docker network，不发布宿主机端口。

## 当前状态

这是 Phase 0/Phase 1 的可测试骨架：

- OpenAI `GET /v1/models` 和 `POST /v1/chat/completions`
- stream / non-stream 编码
- reasoning、联网开关和明确拒绝 tools
- access token 缓存、提前刷新、401 单次重试
- device ID 持久化、签名模块、临时 conversation 生命周期
- SSE raw parser -> normalized events -> OpenAI encoder
- 单账号并发槽、队列超时、客户端取消传播
- 脱敏日志和 HAR 脱敏脚本

当前没有随工作区提供原始 HAR，且 refresh/conversation endpoint 尚未从当前网页抓包确认。因此这些 URL 不是默认猜测值，必须在部署前通过当前 HAR 填入配置，并更新 `docs/protocol-evidence.md`。

## 开发

```powershell
cd chatglm-adapter
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[test]"
pytest
uvicorn chatglm_adapter.main:app --reload
```

本地调用时需要发送：

```text
Authorization: Bearer <ADAPTER_INTERNAL_API_KEY>
```

健康检查 `/health` 和 `/ready` 不要求 API key；模型列表和 chat completions 要求 API key。

## 生产前必须完成

1. 用当前网页抓取并脱敏真实 HAR/SSE。
2. 确认 refresh、create conversation、delete conversation 的 URL 和 response schema。
3. 用真实 `timestamp + nonce + sign` fixture 验证 signer，确认 timestamp transform。
4. 补齐 `tests/fixtures/sse/`，执行 `scripts/probe_chatglm.py`（待抓包后接入）。
5. 将 `CHATGLM_REFRESH_TOKEN_FILE` 作为 Docker secret 挂载，禁止放入 image、Git、环境快照或日志。

## NewAPI

为 adapter 创建 OpenAI-compatible 渠道：

```text
Base URL: http://chatglm-adapter:8000
API Key:  <ADAPTER_INTERNAL_API_KEY>
Model:    chatglm-glm-5.3-flash
```

不要把 adapter 端口发布到公网，也不要把 ChatGLM refresh token 放进 NewAPI。

