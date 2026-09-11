# ChatGLM Web protocol evidence

本文件是生产协议冻结前的证据账本。`A` 只能来自当前网页 HAR/实测；`B` 至少需要两个独立实现交叉验证；`C` 只能作为研究参考；`D` 不得成为不可替换的 magic constant。

| 字段/接口 | 等级 | 当前证据 | 验证方式 | 最后验证 |
|---|---:|---|---|---|
| stream URL `/chatglm/backend-api/assistant/stream` | A | 2026-09-10 Firefox HAR + current frontend bundle | 网页实测与 bundle route 一致 | 2026-09-10 |
| response MIME `text/event-stream` | A | 2026-09-10 Firefox HAR 摘要 | response headers | 2026-09-10 |
| `selected_model=glm-5.3-flash` | A | 2026-09-10 Firefox HAR 摘要 | request body | 2026-09-10 |
| `selected_model=glm-5.3` | C（待 live probe） | 当前网页选择器及用户指定模型名；未完成滑动验证后的真实提交 | 需用登录态提交并检查 request body | 待验证 |
| GLM-5.3 网页可用性 | A | 2026-09-11 登录态网页实测 | 快速、深度、极致均返回预期短答案 | 2026-09-11 |
| GLM-Flash 网页可用性 | A | 2026-09-11 登录态网页实测 + 2026-09-10 HAR | 快速、深度、极致均返回预期短答案 | 2026-09-11 |
| `Authorization: Bearer <access JWT>` | A | 2026-09-10 Firefox HAR + current frontend bundle | request headers and auth helper | 2026-09-10 |
| `X-Timestamp`, `X-Nonce`, `X-Sign` 存在 | A | 2026-09-10 Firefox HAR + current frontend bundle | request headers and signer helper | 2026-09-10 |
| `MD5(timestamp-nonce-secret)` sign formula | B | HAR field set + current frontend bundle | formula cross-checked with reference implementation | 2026-09-10 |
| timestamp sync endpoint and checksum transform | A | current frontend bundle module `14957` and signer helper | route and JavaScript transform inspected | 2026-09-10 |
| refresh endpoint/body/response schema | A | current frontend bundle | POST `{}` with refresh bearer; reads `data.result.*` | 2026-09-10 |
| refresh 是否需要完整 WAF Cookie | C | 2026-09-11 机房 IP 仅 refresh token 返回 400；怀疑 WAF（`acw_tc`/`ssxmod_itna`）或 device 绑定 | 需用完整 Cookie 导入后 live probe 对比 | 待验证 |
| 完整 Cookie 导入后 refresh/stream 可用性 | A | 2026-09-11 live probe：PASS auth/sign/stream，完整 Cookie + token device_id + Firefox UA | `scripts/probe_chatglm.py --cookies-file` | 2026-09-11 |
| 内容帧顶层恒带 `tool_calls: []` | A | 2026-09-11 live probe：13 个正文帧被误判为 ToolEvent，正文为空 | parts 优先归一化，tool/search 判定要求 truthy 值 | 2026-09-11 |
| init/processing 生命周期帧（`parts: []`、`last_error: {}`） | A | 2026-09-11 live probe shape | 显式识别并忽略；`last_error` 非空时报 Error | 2026-09-11 |
| conversation allocation | A | current frontend stream builder | starts with empty `conversation_id`; stream response supplies id | 2026-09-10 |
| conversation delete endpoint/method | A | current frontend bundle module `89971` | POST `/mainchat-api/conversation/delete` | 2026-09-10 |
| SSE top-level schema | A | current frontend stream consumer | JSON frames with `status`, `conversation_id`, `parts`, `last_error` | 2026-09-10 |
| SSE part mapping | B | current frontend part parser + logged-in UI probe | `think` -> reasoning, text-like parts -> content | 2026-09-10 |
| reasoning effort mapping | A | 当前网页 bundle `46071` + 登录态网页三档实测：fast=`""`, standard=`thinking`, deep=`deep_thinking` | UI 快速/深度/极致均成功 | 2026-09-11 |
| GLM-5.3 极致 selected model id | D | 未捕获真实提交 | 不能加入 `/v1/models` | 待验证 |

## 规则

- 代码中的所有 C/D 假设必须来自配置、可替换 provider 或显式 TODO。
- 未知 SSE event 必须产生 `Unknown` 事件并计数，不能静默丢弃。
- 原始 HAR 不得提交；只提交 `sanitize_har.py` 生成的 fixture。
- 当前 bundle 证据只冻结 route、字段名和状态结构；每次生产升级仍需执行 live probe。
- 未从浏览器读取或提交 access/refresh token；凭据继续只允许通过 Docker secret 注入。
