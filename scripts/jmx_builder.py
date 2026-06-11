"""
JMeter .jmx script builder.

Usage:
    python jmx_builder.py --config config.json --output script.jmx

Input JSON format (ScriptConfig):
{
  "test_name": "My Test",
  "api_interfaces": [
    {
      "name": "Login",
      "method": "POST",
      "protocol": "HTTPS",
      "host": "api.example.com",
      "port": 443,
      "path": "/login",
      "headers": [{"name": "Content-Type", "value": "application/json"}],
      "query_params": [],
      "body": {"type": "json", "content": "{\"key\":\"value\"}"},
      "timeout": 60000
    }
  ],
  "scenario": {
    "threads": 100,
    "ramp_up": 30,
    "duration": 300,
    "loops": null,
    "assertions": [
      {"type": "status_code", "condition": "equals", "expected": "200"},
      {"type": "response_time", "condition": "less_than", "expected": "2000"}
    ],
    "variables": [
      {"name": "token", "source": "extractor",
       "expression": "$.token", "default_value": ""}
    ],
    "csv_data": null
  },
  "output_path": "script.jmx"
}
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom


def prettify(elem):
    rough_string = ET.tostring(elem, encoding="unicode")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding="UTF-8").decode("utf-8")


def make_element(tag, attrib=None, text=None):
    el = ET.Element(tag, attrib or {})
    if text is not None:
        el.text = text
    return el


def make_hash_tree(children=None):
    ht = ET.Element("hashTree")
    if children:
        for child in children or []:
            ht.append(child)
            ht.append(make_hash_tree(child.get("_children", [])))
    return ht


def build_element(tag, guiclass, testclass, testname, props=None, children=None):
    el = ET.Element(tag, {
        "guiclass": guiclass,
        "testclass": testclass,
        "testname": testname,
        "enabled": "true",
    })
    if props:
        for prop in props:
            el.append(prop)

    ht = ET.Element("hashTree")
    for child in children or []:
        ht.append(child)
        child_ht = child.find("hashTree")
        if child_ht is None:
            ht.append(ET.Element("hashTree"))
    el.set("_children", str(id(ht)))
    el.append(ht)
    return el


def build_string_prop(name, value):
    return make_element("stringProp", {"name": name}, value)


def build_bool_prop(name, value):
    return make_element("boolProp", {"name": name}, "true" if value else "false")


def build_int_prop(name, value):
    return make_element("intProp", {"name": name}, str(value))


def build_long_prop(name, value):
    return make_element("longProp", {"name": name}, str(value))


def build_element_prop(name, element_type, guiclass, testclass, testname, props=None, enabled=True):
    el = ET.Element("elementProp", {
        "name": name,
        "elementType": element_type,
        "guiclass": guiclass,
        "testclass": testclass,
        "testname": testname,
        "enabled": "true" if enabled else "false",
    })
    if props:
        for p in props:
            el.append(p)
    return el


def build_collection_prop(name):
    return make_element("collectionProp", {"name": name})


def build_header_manager(headers):
    if not headers:
        return None
    collection = build_collection_prop("HeaderManager.headers")
    for h in headers:
        header_el = make_element("elementProp", {
            "name": "",
            "elementType": "Header",
        })
        header_el.append(build_string_prop("Header.name", h["name"]))
        header_el.append(build_string_prop("Header.value", h["value"]))
        collection.append(header_el)

    el = ET.Element("HeaderManager", {
        "guiclass": "HeaderPanel",
        "testclass": "HeaderManager",
        "testname": "HTTP Header Manager",
        "enabled": "true",
    })
    el.append(collection)
    return el


def build_http_request_defaults(api):
    args_el = build_element_prop(
        "HTTPsampler.Arguments", "Arguments",
        "HTTPArgumentsPanel", "Arguments", "Arguments", enabled=True,
    )
    args_el.append(build_collection_prop("Arguments.arguments"))

    el = ET.Element("ConfigTestElement", {
        "guiclass": "HttpDefaultsGui",
        "testclass": "ConfigTestElement",
        "testname": "HTTP Request Defaults",
        "enabled": "true",
    })
    el.append(args_el)
    el.append(build_string_prop("HTTPSampler.domain", api["host"]))
    el.append(build_string_prop("HTTPSampler.port", str(api.get("port", ""))))
    el.append(build_string_prop("HTTPSampler.protocol", api.get("protocol", "HTTP").lower()))
    timeout = str(api.get("timeout", 60000))
    el.append(build_string_prop("HTTPSampler.connect_timeout", timeout))
    el.append(build_string_prop("HTTPSampler.response_timeout", timeout))
    return el


def build_http_sampler(api, scenario):
    args_el = build_element_prop(
        "HTTPsampler.Arguments", "Arguments",
        "HTTPArgumentsPanel", "Arguments", "Arguments", enabled=True,
    )
    collection = build_collection_prop("Arguments.arguments")

    if api.get("body") and api["body"].get("content"):
        body_content = api["body"]["content"]
        arg_el = make_element("elementProp", {
            "name": "body",
            "elementType": "HTTPArgument",
        })
        arg_el.append(build_bool_prop("HTTPArgument.always_encode", True))
        arg_el.append(build_string_prop("Argument.value", body_content))
        arg_el.append(build_string_prop("Argument.metadata", "="))
        arg_el.append(build_bool_prop("HTTPArgument.use_equals", True))
        arg_el.append(build_string_prop("Argument.name", "body"))
        collection.append(arg_el)

    if api.get("query_params"):
        for qp in api["query_params"]:
            qp_el = make_element("elementProp", {
                "name": qp["name"],
                "elementType": "HTTPArgument",
            })
            qp_el.append(build_bool_prop("HTTPArgument.always_encode", True))
            qp_el.append(build_string_prop("Argument.value", qp.get("value", "")))
            qp_el.append(build_string_prop("Argument.metadata", "="))
            qp_el.append(build_bool_prop("HTTPArgument.use_equals", True))
            qp_el.append(build_string_prop("Argument.name", qp["name"]))
            collection.append(qp_el)

    args_el.append(collection)

    el = ET.Element("HTTPSamplerProxy", {
        "guiclass": "HttpTestSampleGui",
        "testclass": "HTTPSamplerProxy",
        "testname": api.get("name", api["path"]),
        "enabled": "true",
    })
    el.append(args_el)
    el.append(build_string_prop("HTTPSampler.domain", ""))
    el.append(build_string_prop("HTTPSampler.port", ""))
    el.append(build_string_prop("HTTPSampler.protocol", ""))
    el.append(build_string_prop("HTTPSampler.contentEncoding", "UTF-8"))
    el.append(build_string_prop("HTTPSampler.path", api["path"]))
    el.append(build_string_prop("HTTPSampler.method", api["method"]))

    has_raw_body = bool(api.get("body") and api["body"].get("content"))
    el.append(build_bool_prop("HTTPSampler.postBodyRaw", has_raw_body))

    sampler_children = []

    for var in (scenario.get("variables") or []):
        if var["source"] == "extractor":
            extractor = build_extractor(var)
            if extractor is not None:
                sampler_children.append(extractor)
        elif var["source"] == "regex_extractor":
            extractor = build_regex_extractor(var)
            if extractor is not None:
                sampler_children.append(extractor)

    for assertion in (scenario.get("assertions") or []):
        assertion_el = build_assertion(assertion)
        if assertion_el is not None:
            sampler_children.append(assertion_el)

    return el, sampler_children


def build_extractor(var):
    expr = var.get("expression", "")
    if expr.startswith("$."):
        el = ET.Element("JSONPostProcessor", {
            "guiclass": "JSONPostProcessorGui",
            "testclass": "JSONPostProcessor",
            "testname": f"JSON Extractor - {var['name']}",
            "enabled": "true",
        })
        el.append(build_string_prop("JSONPostProcessor.referenceNames", var["name"]))
        el.append(build_string_prop("JSONPostProcessor.jsonPathExpressions", expr))
        el.append(build_string_prop("JSONPostProcessor.matchNumbers", "1"))
        return el
    return None


def build_regex_extractor(var):
    el = ET.Element("RegexExtractor", {
        "guiclass": "RegexExtractorGui",
        "testclass": "RegexExtractor",
        "testname": f"Regex Extractor - {var['name']}",
        "enabled": "true",
    })
    el.append(build_string_prop("RegexExtractor.referenceName", var["name"]))
    el.append(build_string_prop("RegexExtractor.regex", var.get("expression", "")))
    el.append(build_string_prop("RegexExtractor.template", "$1$"))
    el.append(build_string_prop("RegexExtractor.match_number", var.get("match_number", "1")))
    el.append(build_string_prop("RegexExtractor.default", var.get("default_value", "")))
    return el


def build_assertion(assertion):
    atype = assertion["type"]
    if atype == "status_code":
        el = ET.Element("ResponseAssertion", {
            "guiclass": "AssertionGui",
            "testclass": "ResponseAssertion",
            "testname": "Response Assertion - Status Code",
            "enabled": "true",
        })
        collection = build_collection_prop("Assertion.test_strings")
        collection.append(build_string_prop("-1836983129", assertion["expected"]))
        el.append(collection)
        el.append(build_string_prop("Assertion.test_field", "Assertion.response_code"))
        el.append(build_bool_prop("Assertion.assume_success", False))
        el.append(build_int_prop("Assertion.test_type", 2))
        return el

    elif atype == "response_time":
        el = ET.Element("DurationAssertion", {
            "guiclass": "DurationAssertionGui",
            "testclass": "DurationAssertion",
            "testname": "Duration Assertion",
            "enabled": "true",
        })
        el.append(build_string_prop("DurationAssertion.duration", assertion["expected"]))
        return el

    elif atype == "json_path":
        el = ET.Element("JSONPathAssertion", {
            "guiclass": "JSONPathAssertionGui",
            "testclass": "JSONPathAssertion",
            "testname": "JSON Assertion",
            "enabled": "true",
        })
        el.append(build_string_prop("JSON_PATH", assertion.get("json_path", "")))
        el.append(build_string_prop("EXPECTED_VALUE", assertion["expected"]))
        el.append(build_bool_prop("JSONVALIDATION", True))
        el.append(build_bool_prop("EXPECT_NULL", False))
        el.append(build_bool_prop("INVERT", False))
        el.append(build_bool_prop("ISREGEX", False))
        return el

    elif atype == "response_body":
        el = ET.Element("ResponseAssertion", {
            "guiclass": "AssertionGui",
            "testclass": "ResponseAssertion",
            "testname": "Response Assertion - Body",
            "enabled": "true",
        })
        collection = build_collection_prop("Assertion.test_strings")
        collection.append(build_string_prop("-1836983129", assertion["expected"]))
        el.append(collection)

        cond_map = {"contains": 2, "equals": 8, "matches": 1}
        test_type = cond_map.get(assertion.get("condition", "contains"), 2)
        el.append(build_string_prop("Assertion.test_field", "Assertion.response_data"))
        el.append(build_bool_prop("Assertion.assume_success", False))
        el.append(build_int_prop("Assertion.test_type", test_type))
        return el

    return None


def build_thread_group(scenario):
    duration = scenario.get("duration")
    loops = scenario.get("loops")

    if duration and loops is None:
        loops = -1

    loop_controller = build_element_prop(
        "ThreadGroup.main_controller", "LoopController",
        "LoopControlPanel", "LoopController", "Loop Controller",
        props=[
            build_bool_prop("LoopController.continue_forever", loops == -1),
            build_int_prop("LoopController.loops", -1 if loops is None else loops),
        ],
    )

    threads = scenario.get("threads", 1)
    duration = scenario.get("duration")
    loops = scenario.get("loops")

    name = f"{threads} users"
    if duration:
        name += f" - {duration}s duration"
    elif loops is not None:
        name += f" - {loops} loops"

    el = ET.Element("ThreadGroup", {
        "guiclass": "ThreadGroupGui",
        "testclass": "ThreadGroup",
        "testname": name,
        "enabled": "true",
    })
    el.append(build_string_prop("ThreadGroup.on_sample_error", "continue"))
    el.append(loop_controller)
    el.append(build_string_prop("ThreadGroup.num_threads", str(threads)))
    el.append(build_string_prop("ThreadGroup.ramp_time",
                                str(scenario.get("ramp_up", threads))))
    el.append(build_long_prop("ThreadGroup.duration", duration or 0))
    el.append(build_long_prop("ThreadGroup.delay", 0))
    el.append(build_bool_prop("ThreadGroup.same_user_on_next_iteration", True))
    return el


def build_csv_data_set(csv_data):
    if not csv_data:
        return None

    el = ET.Element("CSVDataSet", {
        "guiclass": "TestBeanGUI",
        "testclass": "CSVDataSet",
        "testname": "CSV Data Set Config",
        "enabled": "true",
    })
    el.append(build_string_prop("filename", csv_data.get("filename", "")))
    el.append(build_string_prop("variableNames", csv_data.get("variableNames", "")))
    el.append(build_string_prop("delimiter", csv_data.get("delimiter", ",")))
    el.append(build_bool_prop("recycle", csv_data.get("recycle", True)))
    el.append(build_bool_prop("stopThread", csv_data.get("stopThread", False)))
    el.append(build_string_prop("shareMode", csv_data.get("shareMode", "shareMode.all")))
    return el


def build_user_defined_variables(variables):
    if not variables:
        return None

    udv_vars = [v for v in variables if v.get("source") == "user_defined"]

    collection = build_collection_prop("Arguments.arguments")
    for v in udv_vars:
        arg_el = make_element("elementProp", {
            "name": v["name"],
            "elementType": "Argument",
        })
        arg_el.append(build_string_prop("Argument.name", v["name"]))
        arg_el.append(build_string_prop("Argument.value", v.get("default_value", "")))
        arg_el.append(build_string_prop("Argument.metadata", "="))
        collection.append(arg_el)

    if not udv_vars:
        return None

    el = ET.Element("Arguments", {
        "guiclass": "ArgumentsPanel",
        "testclass": "Arguments",
        "testname": "User Defined Variables",
        "enabled": "true",
    })
    el.append(collection)
    return el


def build_cookie_manager():
    el = ET.Element("CookieManager", {
        "guiclass": "CookiePanel",
        "testclass": "CookieManager",
        "testname": "HTTP Cookie Manager",
        "enabled": "true",
    })
    el.append(build_bool_prop("CookieManager.clearEachIteration", False))
    el.append(build_bool_prop("CookieManager.controlledByThreadGroup", False))
    el.append(build_string_prop("CookieManager.policy", "standard"))
    el.append(build_string_prop("CookieManager.implementation", "HC4CookieHandler"))
    return el


def build_listeners():
    summary = ET.Element("ResultCollector", {
        "guiclass": "SummaryReport",
        "testclass": "ResultCollector",
        "testname": "Summary Report",
        "enabled": "true",
    })
    summary.append(build_bool_prop("ResultCollector.error_logging", False))
    save_config = make_element("objProp")
    save_config.set("name", "saveConfig")
    save_config_val = ET.SubElement(save_config, "value")
    save_config_val.set("class", "SampleSaveConfiguration")
    from xml.etree.ElementTree import SubElement
    for name, val in [
        ("time", True), ("latency", True), ("timestamp", True),
        ("success", True), ("label", True), ("code", True),
        ("message", True), ("threadName", True), ("dataType", True),
        ("encoding", False), ("assertions", True), ("subresults", True),
        ("responseData", False), ("samplerData", False), ("xml", False),
        ("fieldNames", True), ("responseHeaders", False),
        ("requestHeaders", False), ("responseDataOnError", True),
        ("saveAssertionResultsFailureMessage", True),
    ]:
        SubElement(save_config_val, name).text = "true" if val else "false"
    summary.append(save_config)
    summary.append(build_string_prop("filename", ""))

    results_tree = ET.Element("ResultCollector", {
        "guiclass": "ViewResultsFullVisualizer",
        "testclass": "ResultCollector",
        "testname": "View Results Tree",
        "enabled": "true",
    })
    results_tree.append(build_bool_prop("ResultCollector.error_logging", False))
    save_config = make_element("objProp")
    save_config.set("name", "saveConfig")
    save_config_val = ET.SubElement(save_config, "value")
    save_config_val.set("class", "SampleSaveConfiguration")
    fields = [
        ("time", True), ("latency", True), ("timestamp", True),
        ("success", True), ("label", True), ("code", True),
        ("message", True), ("threadName", True), ("dataType", True),
        ("encoding", False), ("assertions", True), ("subresults", True),
        ("responseData", False), ("samplerData", False), ("xml", False),
        ("fieldNames", True), ("responseHeaders", False),
        ("requestHeaders", False), ("responseDataOnError", True),
        ("saveAssertionResultsFailureMessage", True),
    ]
    from xml.etree.ElementTree import SubElement
    for name, val in fields:
        SubElement(save_config_val, name).text = "true" if val else "false"
    results_tree.append(save_config)

    return [summary, results_tree]


def build_script(config):
    scenario = config.get("scenario", {})
    apis = config.get("api_interfaces", [])

    root = ET.Element("jmeterTestPlan", {
        "version": "1.2",
        "properties": "5.0",
        "jmeter": "5.5",
    })

    # TestPlan
    test_plan = ET.Element("TestPlan", {
        "guiclass": "TestPlanGui",
        "testclass": "TestPlan",
        "testname": config.get("test_name", "Auto Generated Test"),
        "enabled": "true",
    })
    test_plan.append(build_string_prop("TestPlan.comments", ""))
    test_plan.append(build_bool_prop("TestPlan.functional_mode", False))
    test_plan.append(build_bool_prop("TestPlan.tearDownOnShutdown", True))
    test_plan.append(build_bool_prop("TestPlan.serialize_threadgroups", False))

    udv = build_user_defined_variables(scenario.get("variables") or [])
    if udv:
        test_plan.append(udv)
    else:
        empty_udv = ET.Element("elementProp", {
            "name": "TestPlan.user_defined_variables",
            "elementType": "Arguments",
            "guiclass": "ArgumentsPanel",
            "testclass": "Arguments",
            "testname": "User Defined Variables",
            "enabled": "true",
        })
        empty_udv.append(build_collection_prop("Arguments.arguments"))
        test_plan.append(empty_udv)

    outer_hash = ET.Element("hashTree")
    outer_hash.append(test_plan)

    tp_hash = ET.Element("hashTree")

    if apis:
        tg = build_thread_group(scenario)
        tp_hash.append(tg)

        tg_hash = ET.Element("hashTree")

        defaults = build_http_request_defaults(apis[0])
        tg_hash.append(defaults)
        tg_hash.append(ET.Element("hashTree"))

        headers = apis[0].get("headers", [])
        if headers:
            hm = build_header_manager(headers)
            tg_hash.append(hm)
            tg_hash.append(ET.Element("hashTree"))

        if scenario.get("cookie_manager", False):
            cm = build_cookie_manager()
            tg_hash.append(cm)
            tg_hash.append(ET.Element("hashTree"))

        csv_data = scenario.get("csv_data")
        if csv_data:
            csv_el = build_csv_data_set(csv_data)
            if csv_el:
                tg_hash.append(csv_el)
                tg_hash.append(ET.Element("hashTree"))

        for api in apis:
            sampler, sampler_children = build_http_sampler(api, scenario)
            tg_hash.append(sampler)
            s_hash = ET.Element("hashTree")
            for child in sampler_children:
                s_hash.append(child)
                s_hash.append(ET.Element("hashTree"))
            tg_hash.append(s_hash)

        for listener in build_listeners():
            tg_hash.append(listener)
            tg_hash.append(ET.Element("hashTree"))

        tp_hash.append(tg_hash)
    else:
        tp_hash.append(ET.Element("hashTree"))

    outer_hash.append(tp_hash)
    root.append(outer_hash)

    return root


def main():
    parser = argparse.ArgumentParser(description="JMeter .jmx script builder")
    parser.add_argument("--config", required=True, help="Path to config JSON file")
    parser.add_argument("--output", required=True, help="Output .jmx file path")
    args = parser.parse_args()

    try:
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in config: {e}", file=sys.stderr)
        sys.exit(1)

    root = build_script(config)
    xml_str = prettify(root)
    # Remove the XML declaration added by minidom's toprettyxml and use our own
    xml_str = xml_str.replace("<?xml version=\"1.0\" encoding=\"UTF-8\"?>", "").strip()
    xml_output = f"""<?xml version="1.0" encoding="UTF-8"?>
{xml_str}
"""

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(xml_output)

    print(f"JMeter script generated: {args.output}")


if __name__ == "__main__":
    main()
