# NewAPI integration

创建 OpenAI-compatible 渠道：

```text
名称：ChatGLM Web
类型：OpenAI
Base URL：http://chatglm-adapter:8000
API Key：<ADAPTER_INTERNAL_API_KEY>
模型：chatglm-glm-5.3-flash
```

NewAPI 负责用户、Key、额度、模型映射、优先级、权重和自动禁用。adapter 不重复实现这些网关能力。

推荐让用户侧模型名保持 `chatglm-glm-5.3-flash`，避免与 BigModel/Z.AI 的同名模型混淆。

