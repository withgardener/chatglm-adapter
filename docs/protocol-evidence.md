# ChatGLM Web protocol evidence

本文件是生产协议冻结前的证据账本。`A` 只能来自当前网页 HAR/实测；`B` 至少需要两个独立实现交叉验证；`C` 只能作为研究参考；`D` 不得成为不可替换的 magic constant。

| 字段/接口 | 等级 | 当前证据 | 验证方式 | 最后验证 |
|---|---:|---|---|---|
| stream URL `/chatglm/backend-api/assistant/stream` | A | 2026-09-10 Firefox HAR + current frontend bundle | 网页实测与 bundle route 一致 | 2026-09-10 |
| response MIME `text/event-stream` | A | 2026-09-10 Firefox HAR 摘要 | response headers | 2026-09-10 |
| `selected_model=glm-5.3-flash` | A | 2026-09-10 Firefox HAR 摘要 | request body | 2026-09-10 |
| `Authorization: Bearer <access JWT>` | A | 2026-09-10 Firefox HAR + current frontend bundle | request headers and auth helper | 2026-09-10 |
| `X-Timestamp`, `X-Nonce`, `X-Sign` 存在 | A | 2026-09-10 Firefox HAR + current frontend bundle | request headers and signer helper | 2026-09-10 |
| `MD5(timestamp-nonce-secret)` sign formula | B | HAR field set + current frontend bundle | formula cross-checked with reference implementation | 2026-09-10 |
| timestamp sync endpoint and checksum transform | A | current frontend bundle module `14957` and signer helper | route and JavaScript transform inspected | 2026-09-10 |
| refresh endpoint/body/response schema | A | current frontend bundle | POST `{}` with refresh bearer; reads `data.result.*` | 2026-09-10 |
| conversation allocation | A | current frontend stream builder | starts with empty `conversation_id`; stream response supplies id | 2026-09-10 |
| conversation delete endpoint/method | A | current frontend bundle module `89971` | POST `/mainchat-api/conversation/delete` | 2026-09-10 |
| SSE top-level schema | A | current frontend stream consumer | JSON frames with `status`, `conversation_id`, `parts`, `last_error` | 2026-09-10 |
| SSE part mapping | B | current frontend part parser + logged-in UI probe | `think` -> reasoning, text-like parts -> content | 2026-09-10 |
| GLM-5.3 极致 selected model id | D | 未捕获真实提交 | 不能加入 `/v1/models` | 待验证 |

## 规则

- 代码中的所有 C/D 假设必须来自配置、可替换 provider 或显式 TODO。
- 未知 SSE event 必须产生 `Unknown` 事件并计数，不能静默丢弃。
- 原始 HAR 不得提交；只提交 `sanitize_har.py` 生成的 fixture。
- 当前 bundle 证据只冻结 route、字段名和状态结构；每次生产升级仍需执行 live probe。
- 未从浏览器读取或提交 access/refresh token；凭据继续只允许通过 Docker secret 注入。
