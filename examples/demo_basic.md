# 示例：登录接口压测

## 完整对话流程

**用户**：帮我为登录接口生成一个 JMeter 压测脚本

**AI**（阶段一：收集接口信息）：
好的，请提供以下接口信息：
- 请求方法 (GET/POST/PUT/DELETE)？
- 完整的请求 URL？
- 是否需要自定义 Headers？
- 请求体内容（如果有）？

**用户**：
POST https://api.example.com/login
Headers: Content-Type: application/json
Body: {"username":"test_user","password":"pass123"}

**AI**（阶段二：解析测试场景）：
接口信息已记录。请描述测试场景，例如：
"100 个并发用户跑 5 分钟，检查返回码 200"

**用户**：
200 个并发用户跑 3 分钟，预热 30 秒，检查返回码 200，响应时间不超过 2 秒，提取返回的 token 字段

**AI**（阶段三：生成脚本）：
已解析您的场景：
- 并发用户数：200
- 预热时间：30 秒
- 持续时间：180 秒
- 断言：状态码=200，响应时间<2000ms
- 后置处理器：提取 $.token → ${token}

正在生成 JMeter 脚本...

脚本已生成：`jmeter_20250509_120000.jmx`

执行命令：
```bash
jmeter -n -t jmeter_20250509_120000.jmx -l results.jtl
```

**生成的脚本结构**：
- TestPlan: Auto Generated Test
  - ThreadGroup: 200 threads, ramp-up 30s, duration 180s
    - HTTP Request Defaults
    - HTTP Request: 登录接口 (POST /login)
      - HTTP Header: Content-Type=application/json
      - JSON Extractor: $.token → ${token}
      - Response Assertion: 状态码=200
      - Duration Assertion: <2000ms
    - Summary Report
    - View Results Tree
