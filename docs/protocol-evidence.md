# ChatGLM Web protocol evidence

本文件是生产协议冻结前的证据账本。`A` 只能来自当前网页 HAR/实测；`B` 至少需要两个独立实现交叉验证；`C` 只能作为研究参考；`D` 不得成为不可替换的 magic constant。

| 字段/接口 | 等级 | 当前证据 | 验证方式 | 最后验证 |
|---|---:|---|---|---|
| stream URL `/chatglm/backend-api/assistant/stream` | A（方案提供） | 2026-09-10 Firefox HAR 摘要 | 真实网页请求 | 2026-09-10 |
| response MIME `text/event-stream` | A（方案提供） | 2026-09-10 Firefox HAR 摘要 | response headers | 2026-09-10 |
| `selected_model=glm-5.3-flash` | A（方案提供） | 2026-09-10 Firefox HAR 摘要 | request body | 2026-09-10 |
| `Authorization: Bearer <access JWT>` | A（方案提供） | 2026-09-10 Firefox HAR 摘要 | request headers | 2026-09-10 |
| `X-Timestamp`, `X-Nonce`, `X-Sign` 存在 | A（方案提供） | 2026-09-10 Firefox HAR 摘要 | request headers | 2026-09-10 |
| `MD5(timestamp-nonce-secret)` sign formula | B（待 fixture） | 方案中的 HelloGML 交叉线索 | 必须与真实 HAR fixture 完全一致 | 待验证 |
| timestamp transform | D | 尚无原始 HAR/网页 JS fixture | 需要三方交叉验证 | 待验证 |
| refresh endpoint/response schema | D | 当前工作区无 HAR | 需要当前网页抓包 | 待验证 |
| conversation create/delete endpoint | D | 当前工作区无 HAR | 需要当前网页抓包 | 待验证 |
| SSE event schema | D | 当前工作区无 response body | 普通、thinking、search、stop、error、long fixtures | 待验证 |
| GLM-5.3 极致 selected model id | D | 未捕获真实提交 | 不能加入 `/v1/models` | 待验证 |

## 规则

- 代码中的所有 C/D 假设必须来自配置、可替换 provider 或显式 TODO。
- 未知 SSE event 必须产生 `Unknown` 事件并计数，不能静默丢弃。
- 原始 HAR 不得提交；只提交 `sanitize_har.py` 生成的 fixture。

