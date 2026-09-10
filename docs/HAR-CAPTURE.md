# HAR capture checklist

使用自有账号在当前 ChatGLM 网页重新捕获以下场景：

1. Flash 普通回答
2. deep thinking
3. 联网搜索
4. 主动停止
5. 长回答
6. 上游错误
7. 新建 conversation
8. 删除 conversation
9. refresh access token
10. GLM-5.3 极致真实提交

保存原始文件在工作区之外。提交前运行：

```powershell
python scripts/sanitize_har.py input.har tests/fixtures/har/chatglm-sanitized.har
```

检查输出中不存在 JWT、Cookie、refresh token、UID、device ID、完整 prompt 或完整 completion。脱敏 fixture 仍应保留 method、URL path、headers 名称、request body 结构、SSE MIME 和安全的示例值。

