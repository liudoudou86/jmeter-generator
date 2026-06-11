"""
HAR (HTTP Archive) parser for JMeter script generation.

Parses standard HAR 1.2 files, extracts API interfaces,
detects dynamic parameters, and outputs ScriptConfig JSON
compatible with jmx_builder.py.

Usage:
    python har_parser.py --har session.har --output config.json
    python har_parser.py --har session.har --output config.json \\
        --no-detect-dynamic --no-extract-auth --no-cookie-manager
"""

import argparse
import json
import os
import re
import sys
from urllib.parse import urlparse, parse_qs

HTTP2_PSEUDO_HEADERS = {":authority", ":method", ":path", ":scheme", ":status"}

DYNAMIC_PATTERNS = [
    {
        "name": "timestamp_10",
        "pattern": re.compile(r"\b\d{10}\b"),
        "jmeter_func": "${__time(/1,)}",
        "description": "10-digit Unix timestamp",
    },
    {
        "name": "timestamp_13",
        "pattern": re.compile(r"\b\d{13}\b"),
        "jmeter_func": "${__time(/1000,)}",
        "description": "13-digit Unix timestamp (milliseconds)",
    },
    {
        "name": "uuid_v4",
        "pattern": re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
            re.IGNORECASE,
        ),
        "jmeter_func": "${__UUID}",
        "description": "UUID v4",
    },
    {
        "name": "iso8601_datetime",
        "pattern": re.compile(
            r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
        ),
        "jmeter_func": "${__time(yyyy-MM-dd'T'HH:mm:ss'Z',)}",
        "description": "ISO 8601 datetime string",
    },
]

AUTH_HEADER_PATTERNS = [
    {"name": "auth_token", "header": "Authorization", "prefix": "Bearer "},
    {"name": "auth_basic", "header": "Authorization", "prefix": "Basic "},
]


class HarParseError(Exception):
    pass


def parse_har(filepath):
    if not os.path.isfile(filepath):
        raise HarParseError(f"File not found: {filepath}")

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise HarParseError(f"Invalid JSON in HAR file: {e}")

    log = data.get("log")
    if not log:
        raise HarParseError("Missing 'log' root element in HAR file")

    entries = log.get("entries", [])
    if not entries:
        raise HarParseError("No entries found in HAR log")

    version = log.get("version", "unknown")
    return version, entries


def is_pseudo_header(name):
    return name.lower() in HTTP2_PSEUDO_HEADERS


def parse_url(url):
    parsed = urlparse(url)
    protocol = parsed.scheme.upper()
    host = parsed.hostname or ""
    port = parsed.port
    path = parsed.path or "/"
    url_query_params = {}
    if parsed.query:
        url_query_params = {
            k: v[0] for k, v in parse_qs(parsed.query).items()
        }
    return protocol, host, port, path, url_query_params


def extract_body(entry):
    post_data = entry.get("request", {}).get("postData")
    if not post_data:
        return None

    mime_type = post_data.get("mimeType", "")
    text = post_data.get("text", "")

    if not text:
        return None

    if "json" in mime_type:
        body_type = "json"
    elif "x-www-form-urlencoded" in mime_type:
        body_type = "form"
    elif "xml" in mime_type:
        body_type = "xml"
    elif "text" in mime_type:
        body_type = "text"
    else:
        body_type = "text"

    return {"type": body_type, "content": text}

def entry_to_api_interface(entry):
    request = entry.get("request", {})
    method = request.get("method", "GET")
    url = request.get("url", "")

    protocol, host, port, path, url_query_params = parse_url(url)

    raw_headers = request.get("headers", [])

    headers = [
        {"name": h["name"], "value": h["value"]}
        for h in raw_headers
        if not is_pseudo_header(h["name"])
    ]

    query_params_map = dict(url_query_params)
    for qp in request.get("queryString", []):
        name = qp["name"]
        value = qp["value"]
        if name not in query_params_map:
            query_params_map[name] = value
    query_params = [{"name": k, "value": v} for k, v in query_params_map.items()]

    body = extract_body(entry)

    name = f"{method} {path}"

    interface = {
        "name": name,
        "method": method,
        "protocol": protocol,
        "host": host,
        "path": path,
        "headers": headers,
        "query_params": query_params,
    }

    if port:
        interface["port"] = port
    if body:
        interface["body"] = body

    return interface


def dedup_interfaces(interfaces):
    seen = set()
    result = []
    for iface in interfaces:
        key = (iface["method"], iface["host"], iface["path"],
                json.dumps(iface.get("query_params", []), sort_keys=True))
        if key not in seen:
            seen.add(key)
            result.append(iface)
    return result


def detect_dynamic_params_in_text(text):
    if not isinstance(text, str):
        return text, []

    changes = []
    for rule in DYNAMIC_PATTERNS:
        matches = rule["pattern"].findall(text)
        if matches:
            text = rule["pattern"].sub(rule["jmeter_func"], text)
            changes.append({
                "pattern": rule["name"],
                "count": len(matches),
                "jmeter_func": rule["jmeter_func"],
            })
    return text, changes


def detect_dynamic_params_in_interface(interface):
    all_changes = []
    interface["headers"] = _detect_in_headers(interface["headers"], all_changes)
    interface["query_params"] = _detect_in_query_params(
        interface["query_params"], all_changes
    )
    if interface.get("body"):
        body = interface["body"]
        body["content"], changes = detect_dynamic_params_in_text(body["content"])
        all_changes.extend(changes)
    return interface, all_changes


def _detect_in_headers(headers, all_changes):
    result = []
    for h in headers:
        new_value, changes = detect_dynamic_params_in_text(h["value"])
        h["value"] = new_value
        all_changes.extend(changes)
        result.append(h)
    return result


def _detect_in_query_params(params, all_changes):
    result = []
    for qp in params:
        new_value, changes = detect_dynamic_params_in_text(qp["value"])
        qp["value"] = new_value
        all_changes.extend(changes)
        result.append(qp)
    return result


def extract_auth_vars(interfaces):
    auth_vars = {}
    all_auth_headers = {}

    for iface in interfaces:
        for h in iface["headers"]:
            hname = h["name"].lower()
            hvalue = h["value"]

            if hname == "authorization":
                for rule in AUTH_HEADER_PATTERNS:
                    if hvalue.startswith(rule["prefix"]):
                        var_name = rule["name"]
                        if var_name not in auth_vars:
                            auth_vars[var_name] = hvalue
                            all_auth_headers[var_name] = h
                        break
                else:
                    if "auth_custom" not in auth_vars:
                        auth_vars["auth_custom"] = hvalue
                        all_auth_headers["auth_custom"] = h

            elif hname == "cookie":
                if "auth_cookie" not in auth_vars:
                    auth_vars["auth_cookie"] = hvalue
                    all_auth_headers["auth_cookie"] = h

    variables = []
    for var_name, var_value in auth_vars.items():
        ref = "${" + var_name + "}"
        variables.append({
            "name": var_name,
            "source": "user_defined",
            "default_value": var_value,
        })
        if var_name in all_auth_headers:
            all_auth_headers[var_name]["value"] = ref

    return interfaces, variables


def build_scenario_skeleton():
    return {
        "threads": 10,
        "ramp_up": 10,
        "duration": 60,
        "loops": None,
        "assertions": [
            {"type": "status_code", "condition": "equals", "expected": "200"}
        ],
        "variables": [],
        "csv_data": None,
        "cookie_manager": True,
    }


def build_script_config(interfaces, variables, output_path, test_name=None):
    if not test_name:
        test_name = f"HAR Import Test"

    scenario = build_scenario_skeleton()
    scenario["variables"] = variables

    return {
        "test_name": test_name,
        "api_interfaces": interfaces,
        "scenario": scenario,
        "output_path": output_path,
    }


def parse_har_to_config(
    har_path,
    detect_dynamic=True,
    extract_auth=True,
    output_path="har_import_config.json",
):
    version, entries = parse_har(har_path)

    print(f"HAR version: {version}, entries: {len(entries)}")

    interfaces = []
    for entry in entries:
        try:
            iface = entry_to_api_interface(entry)
            interfaces.append(iface)
        except Exception as e:
            print(f"  Warning: Skipping entry due to error: {e}", file=sys.stderr)
            continue

    total_raw = len(interfaces)
    interfaces = dedup_interfaces(interfaces)
    dedup_count = total_raw - len(interfaces)

    if dedup_count > 0:
        print(f"  Deduplicated {dedup_count} duplicate request(s)")
    print(f"  Total unique API interfaces: {len(interfaces)}")

    all_dynamic_changes = []

    if detect_dynamic:
        interfaces_with_dynamic = []
        for iface in interfaces:
            updated_iface, changes = detect_dynamic_params_in_interface(iface)
            interfaces_with_dynamic.append(updated_iface)
            all_dynamic_changes.extend(changes)
        interfaces = interfaces_with_dynamic

        dynamic_summary = {}
        for c in all_dynamic_changes:
            key = c["pattern"]
            dynamic_summary[key] = dynamic_summary.get(key, 0) + c["count"]

        if dynamic_summary:
            print(f"  Dynamic parameters detected:")
            for rule_name, count in dynamic_summary.items():
                print(f"    - {rule_name}: {count} occurrence(s)")
        else:
            print(f"  No dynamic parameters detected")
    else:
        print(f"  Dynamic parameter detection: disabled")

    variables = []

    if extract_auth:
        interfaces, auth_vars = extract_auth_vars(interfaces)
        variables.extend(auth_vars)
        if auth_vars:
            print(f"  Auth variables extracted: {[v['name'] for v in auth_vars]}")
        else:
            print(f"  No auth variables detected")
    else:
        print(f"  Auth extraction: disabled")

    config = build_script_config(interfaces, variables, output_path)
    return config


def main():
    parser = argparse.ArgumentParser(
        description="Parse HAR file and generate JMeter script config"
    )
    parser.add_argument("--har", required=True, help="Path to .har file")
    parser.add_argument("--output", default="har_import_config.json",
                        help="Output config JSON path")
    parser.add_argument("--no-detect-dynamic", action="store_true",
                        help="Disable dynamic parameter auto-detection")
    parser.add_argument("--no-extract-auth", action="store_true",
                        help="Disable auth header extraction")
    parser.add_argument("--test-name", default=None,
                        help="Test name for the generated script")
    args = parser.parse_args()

    try:
        config = parse_har_to_config(
            har_path=args.har,
            detect_dynamic=not args.no_detect_dynamic,
            extract_auth=not args.no_extract_auth,
            output_path=args.output,
        )
    except HarParseError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"\nConfig written to: {args.output}")
    print(f"API interfaces: {len(config['api_interfaces'])}")
    print(f"Variables: {len(config['scenario']['variables'])}")
    print(f"\nNext step: uv run python scripts/jmx_builder.py "
          f"--config {args.output} --output script.jmx")


if __name__ == "__main__":
    main()
