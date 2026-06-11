# HAR 导入示例

## 示例文件

- `demo_har.har` — 包含 4 个请求的 Chrome HAR 导出文件

## 分步操作

### 1. 解析 HAR 文件

```bash
uv run python scripts/har_parser.py --har examples/demo_har.har --output examples/demo_har_config.json
```

预期输出：
```
HAR version: 1.2, entries: 4
  Deduplicated 0 duplicate request(s)
  Total unique API interfaces: 4
  Dynamic parameters detected:
    - timestamp_10: 2 occurrence(s)
    - uuid_v4: 1 occurrence(s)
  Auth variables extracted: ['auth_token', 'auth_cookie']
```

### 2. 生成 JMeter 脚本

```bash
uv run python scripts/jmx_builder.py --config examples/demo_har_config.json --output examples/demo_har_output.jmx
```

### 3. 一键完成

```bash
uv run python scripts/har_parser.py --har examples/demo_har.har --output /tmp/har_config.json \
  && uv run python scripts/jmx_builder.py --config /tmp/har_config.json --output examples/demo_har_output.jmx
```

## 效果说明

| 功能 | 示例效果 |
|------|----------|
| HTTP/2 伪头过滤 | `:authority`、`:method` 等被自动移除 |
| 动态参数检测 | `1704067200` → `${__time(/1,)}`，UUID → `${__UUID}` |
| 认证提取 | `Authorization: Bearer xxx` → `${auth_token}`，`Cookie: xxx` → `${auth_cookie}` |
| Cookie Manager | 生成的 JMX 中包含 HTTP Cookie Manager |

## 关闭自动检测

如果不需要动态参数检测或认证提取：

```bash
uv run python scripts/har_parser.py --har examples/demo_har.har --output config.json \
  --no-detect-dynamic --no-extract-auth
```
