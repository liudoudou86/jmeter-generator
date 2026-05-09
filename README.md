# JMeter Generator

根据用户提供的 API 接口信息和测试场景描述，自动生成可直接执行的 JMeter (`.jmx`) 脚本。支持 JMeter **5.x**。

## 目录结构

```
jmeter-generator/
├── SKILL.md                 # AI 驱动的 Skill 定义（供 opencode agent 使用）
├── config.json              # 默认配置（JMeter 版本、监听器等）
├── pyproject.toml           # Python 项目配置
├── scripts/
│   └── jmx_builder.py      # 核心构建脚本：将配置 JSON 转换为 .jmx 文件
├── references/
│   ├── jmeter_template.jmx  # JMX 模板参考
│   └── scenario_guide.md    # 测试场景描述编写指南
├── examples/
│   ├── demo_basic.md        # 完整对话流程示例
│   └── demo_output.jmx      # 生成结果示例
└── .venv/                   # Python 虚拟环境
```

## 快速开始

```bash
# 生成 JMeter 脚本
uv run python scripts/jmx_builder.py --config config.json --output script.jmx

# 执行生成的脚本
jmeter -n -t script.jmx -l results.jtl
```

## 工作流程

1. **收集接口信息** — 录入 API 的 Method、URL、Headers、Body
2. **解析测试场景** — 用自然语言描述并发数、持续时间、断言条件、变量提取等
3. **生成 JMeter 脚本** — 展示预览摘要，确认后调用 `jmx_builder.py` 生成 `.jmx` 文件

## 支持的断言类型

| type            | 说明                 |
| --------------- | -------------------- |
| `status_code`   | 检查 HTTP 状态码     |
| `response_time` | 检查响应时间（毫秒） |
| `json_path`     | JSON 路径值断言      |
| `response_body` | 响应体包含/等于/匹配 |

## 支持的变量提取

| source            | 说明                        |
| ----------------- | --------------------------- |
| `extractor`       | JSON Path 提取器（`$.xxx`） |
| `regex_extractor` | 正则表达式提取器            |
| `user_defined`    | 用户自定义变量              |

## 场景描述指南

见 `references/scenario_guide.md`，支持以下测试模板：

- 简单压测
- 带预热和断言
- 带参数提取
- 数据驱动（CSV 参数化）
- 多接口场景
