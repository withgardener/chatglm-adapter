# chatglm-adapter

一个面向自有 ChatGLM 会员账号的薄型 OpenAI-compatible adapter。

```text
OpenAI client -> NewAPI -> chatglm-adapter -> ChatGLM Web private API
```

项目只实现 ChatGLM Web provider，不实现用户、额度、模型路由或多账号池。生产部署时 adapter 只加入 NewAPI 的内部 Docker network，不发布宿主机端口。

## 当前状态

这是 Phase 0/Phase 1 的可测试实现：

- OpenAI `GET /v1/models` 和 `POST /v1/chat/completions`
- stream / non-stream 编码
- reasoning、联网开关和明确拒绝 tools
- access token 缓存、提前刷新、带当前网页签名的 refresh、401 单次重试
- device ID 持久化、网页时间同步与签名、临时 conversation 生命周期
- SSE raw parser -> normalized events -> OpenAI encoder
- 单账号并发槽、队列超时、客户端取消传播
- 脱敏日志和 HAR 脱敏脚本

当前实现依据 2026-09-10 的脱敏 HAR 摘要、当前公开前端 bundle 以及登录态网页探针冻结了主要 route 和事件结构。access/refresh token 没有从浏览器导出，首次部署仍应执行一次自有账号的 live probe。

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

1. 用当前网页重新执行并脱敏真实 HAR/SSE，确认当前账号仍可用。
2. 执行 `scripts/probe_chatglm.py`，检查 refresh、stream、SSE 和 cleanup。
3. 将 `CHATGLM_REFRESH_TOKEN_FILE` 作为 Docker secret 挂载，禁止放入 image、Git、环境快照或日志。

## NewAPI

为 adapter 创建 OpenAI-compatible 渠道：

```text
Base URL: http://chatglm-adapter:8000
API Key:  <ADAPTER_INTERNAL_API_KEY>
Model:    chatglm-glm-5.3-flash
```

不要把 adapter 端口发布到公网，也不要把 ChatGLM refresh token 放进 NewAPI。
