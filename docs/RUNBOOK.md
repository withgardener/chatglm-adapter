# Runbook

## Refresh token

更新 Docker secret 文件后，以原子替换方式写入，再重启 adapter。不要在 shell history、Compose environment、NewAPI 或日志中粘贴 token。

## Access token 失效

查看错误类别和上游 HTTP 状态，不查看 credential。401 会触发一次强制 refresh；若仍失败，检查 refresh token 是否 rotation、账号是否被网页要求重新登录。

## 签名失败

检查 `X-Timestamp` 格式、时钟、nonce 生成和 secret 配置。使用脱敏 fixture 运行 signer regression test，不打印真实 header 值。

## 协议变化

出现未知 SSE event、schema changed 或连续 4xx 时，停止生产升级，重新抓取当前网页并更新 evidence ledger。不要用 `:latest` 回滚或升级。

## 队列

单账号默认 `UPSTREAM_MAX_CONCURRENCY=1`。队列满返回 429，等待超时返回 503；不要无限放大队列。

## DEBUG

DEBUG 也不得记录 prompt、completion、Authorization、Cookie、access token、refresh token 或完整 HAR。调试只使用脱敏事件 schema。

## 发布/回滚

使用 immutable semver image 和 git SHA；部署前运行完整单元测试、集成测试和 protocol probe。回滚到已验证的具体 tag/digest。

