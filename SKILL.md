---
name: jmeter-generator
description: |
  根据用户提供的 API 接口信息和测试场景描述，自动生成可直接执行的 JMeter (.jmx) 脚本。
  适用场景: "帮我生成 JMeter 脚本"、"为一个登录接口创建压测脚本"、"帮我写一个压测脚本"
---

# JMeter 脚本生成器

我负责将 API 接口信息和测试场景描述转化为可直接执行的 JMeter `.jmx` 脚本。目标 JMeter 版本：**5.x**。

## 路径约定

本 skill 中所有引用及运行脚本的路径优先从当前 skill 目录查找，例如：
- 引用 `references/jmeter_template.jmx`
- 运行脚本 `uv run python scripts/jmx_builder.py --config config.json --output script.jmx`

## 核心工作流程

### 阶段一：收集接口信息

1. **引导用户录入接口**：询问 Method、URL、Headers、Body
2. **组装数据结构**：将录入信息组装为 ApiInterface（见数据结构定义）
3. **多接口支持**：用户可录入多个接口，按顺序编号

**用户输入示例**：

```
POST https://api.example.com/login
Headers: Content-Type: application/json
Body: {"username":"test","password":"123456"}
```

**输出结构**：

```json
{
  "name": "登录接口",
  "method": "POST",
  "protocol": "HTTPS",
  "host": "api.example.com",
  "path": "/login",
  "headers": [{"name": "Content-Type", "value": "application/json"}],
  "body": {"type": "json", "content": "{\"username\":\"test\",\"password\":\"123456\"}"}
}
```

### 阶段二：解析测试场景

1. **接收自然语言描述**：用户描述测试意图
2. **关键词解析**：按解析规则表提取结构化参数
3. **歧义检测**：缺少关键参数时主动追问
4. **二次确认**：关键参数确认后生成 TestScenario

**用户输入示例**：

```
100 个并发跑 5 分钟，检查返回码 200，响应不超过 2 秒，提取 token
```

**解析结果**：

```json
{
  "threads": 100,
  "duration": 300,
  "ramp_up": 30,
  "assertions": [
    {"type": "status_code", "condition": "equals", "expected": "200"},
    {"type": "response_time", "condition": "less_than", "expected": "2000"}
  ],
  "variables": [
    {"name": "token", "source": "extractor", "expression": "$.token"}
  ]
}
```

**带 CSV 参数化示例**：

用户输入：*"100 并发，从 users.csv 读取用户名和密码，循环 1000 次，检查登录成功"*

解析结果：
```json
{
  "threads": 100,
  "loops": 1000,
  "csv_data": {"filename": "users.csv", "variableNames": "username,password"},
  "assertions": [
    {"type": "response_body", "condition": "contains", "expected": "success"}
  ]
}
```

### 阶段三：生成 JMeter 脚本

1. **预览摘要**：输出前展示脚本结构摘要（接口数、线程数、断言数、是否参数化）
2. **用户确认**：展示摘要后等待用户确认
3. **合并数据**：将 ApiInterface + TestScenario 组装为 ScriptConfig，写入临时 JSON
4. **调用构建脚本**：运行 `uv run python scripts/jmx_builder.py --config <temp.json> --output <output.jmx>`
5. **输出结果**：告知用户文件路径，提示 `jmeter -n -t` 执行

**预览示例**：
```
📋 脚本预览
━━━━━━━━━━━━━━━━━━━━━
接口: 2 个 (POST /login, GET /user/profile)
线程: 100 并发 | 预热 30s | 持续 300s
断言: 状态码=200, 响应时间<2000ms
提取器: token ($.token)
参数化: data.csv (username, password)
监听器: Summary Report, View Results Tree
━━━━━━━━━━━━━━━━━━━━━
确认生成脚本？(y/n)
```

## 自然语言解析规则

| 用户表述 | 解析结果 |
|----------|----------|
| "N个并发"、"N线程"、"N users" | threads = N |
| "跑M分钟"、"持续M秒"、"duration M" | duration = M (秒) |
| "预热30秒"、"ramp-up 30" | ramp_up = 30 |
| "循环N次"、"loop N" | loops = N |
| "永远跑"、"持续跑" | loops = -1 |
| "检查返回码200"、"状态码200" | assertion: status_code = 200 |
| "响应不超过Ns"、"响应<Ns" | assertion: response_time < N*1000 |
| "检查xxx字段"、"验证yyy" | assertion: json_path = xxx |
| "提取token"、"拿到token" | variable: token, source=extractor, expression=$.token |
| "从data.csv读取"、"参数化" | csv_data: filename=data.csv |
| "检查返回体包含xxx" | assertion: response_body contains xxx |

## 歧义追问策略

| 场景 | 追问 |
|------|------|
| 未指定并发数 | "请问需要多少个并发用户？" |
| 未指定持续时间/循环次数 | "请问需要跑多久（如5分钟），或者循环多少次？" |
| 并发数 > 10000 | "并发超过 10000 可能会对目标服务器造成较大压力，确认继续吗？" |
| 未指定断言 | "需要检查哪些响应条件？如状态码、响应时间等" |
| Method 非标准 | "`{method}` 不是标准 HTTP Method，已默认转为 GET，需要修改吗？" |

## 数据模型

### ApiInterface

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | String | 是 | 接口名称 |
| method | String | 是 | GET/POST/PUT/DELETE/PATCH |
| protocol | String | 是 | HTTP/HTTPS |
| host | String | 是 | 主机地址 |
| port | Integer | 可选 | 端口，默认 80/443 |
| path | String | 是 | 接口路径 |
| headers | Array | 可选 | [{name, value}] |
| query_params | Array | 可选 | [{name, value}] |
| body | Object | 可选 | {type, content} |

### TestScenario

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| threads | Integer | 是 | 并发用户数 |
| ramp_up | Integer | 否 | 预热秒数, 默认 threads |
| duration | Integer | 否 | 持续秒数, 与 loops 互斥 |
| loops | Integer | 否 | 循环次数, -1=永远 |
| assertions | Array | 否 | 断言列表 |
| variables | Array | 否 | 变量列表 |
| csv_data | Object | 否 | {filename, variableNames, delimiter} |

## 快速决策树

### 用户提供了什么？

| 输入 | 处理方式 |
|------|----------|
| 接口信息 | → 阶段一：继续询问场景描述 |
| 测试场景描述 | → 阶段二：如果已有接口信息则生成脚本 |
| 一体化的描述（含接口+场景） | → 阶段一+二：分别解析 |
| "帮我写个压测脚本" | → 从零开始引导 |

### 当前状态

| 状态 | AI 行为 |
|------|---------|
| 已有接口信息，缺场景 | 追问场景描述 |
| 已有场景，缺接口 | 追问接口信息 |
| 两者都齐 | 进入脚本生成 |

## 如何使用脚本

- **生成 JMeter 脚本**：运行 `uv run python scripts/jmx_builder.py --config <config.json> --output <script.jmx>`
- **查看 JMX 模板**：读取 `references/jmeter_template.jmx`
- **查看场景编写指南**：读取 `references/scenario_guide.md`
- **查看示例**：读取 `examples/demo_basic.md`

---

## 实施说明

执行本 skill 时，请按以下步骤操作：

1. **读取 `references/jmeter_template.jmx`** 了解 JMX 基础结构
2. **按阶段一收集接口信息**，组装为 ApiInterface
3. **按阶段二解析场景**，按解析规则表提取参数，有歧义时追问
4. **展示脚本预览摘要**，等待用户确认
5. **合并为 ScriptConfig** 写入临时 JSON 文件
6. **调用 `uv run python scripts/jmx_builder.py --config <temp.json> --output <output.jmx>`** 生成 .jmx
7. **输出结果**：告知文件路径（默认 `jmeter_<timestamp>.jmx`，用户可自定义），提示 `jmeter -n -t` 执行
