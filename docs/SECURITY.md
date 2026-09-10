# Security notes

- `CHATGLM_REFRESH_TOKEN_FILE` 是唯一支持的 ChatGLM refresh token 来源；文件应由 Docker secret 或 0600 文件提供。
- adapter API key 与 ChatGLM access token 完全分离。
- access token 只在内存缓存，不写日志。
- device ID 可持久化在 `/data/device-id`，但不进入日志或 health response。
- 请求日志只记录 request id、model、stream、延迟、状态和错误类别，不记录 prompt/completion。
- 原始 HAR 不得进入 Git。
- 未实现工具调用；带 `tools` 的请求会收到 `unsupported_feature`。

