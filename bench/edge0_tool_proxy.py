#!/usr/bin/env python3
"""OpenAI tool-calling shim in front of the edge0 server.

edge0's /v1/chat/completions ignores `tools` entirely and never emits
`tool_calls` (see src/edge0/server/chat.py: ChatRequest has no tools
field; app.py hardcodes finish_reason="stop").  The underlying
Qwen3.6-35B-A3B checkpoint *can* call tools -- its chat template knows
the format -- but edge0 calls apply_chat_template() without tools=, so
the model never sees the definitions.

This proxy closes exactly that gap and nothing else:

  request   OpenAI `tools` -> rendered into a system message, byte-for-byte
            the way models/edge0-35b/chat_template.jinja lines 45-53 would
            have rendered them; assistant `tool_calls` from the history
            re-serialised the way lines 105-128 would have.
  response  the model's <tool_call><function=..><parameter=..> blocks
            parsed back into OpenAI tool_calls + finish_reason.

Everything else is passed through untouched.

Usage:
    edge0 serve edge0-35b                      # upstream on :8000
    python3 edge0_tool_proxy.py                # shim on :8899
    LLM_URL=http://127.0.0.1:8899/v1/chat/completions \
        python3 bench/realagent.py edge0-35b /tmp/wd

Env:
    EDGE0_UPSTREAM  default http://127.0.0.1:8000/v1/chat/completions
    PROXY_PORT      default 8899
    EDGE0_THINK     "1" to leave the reasoning block on (default off)
"""
import json, os, re, sys, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

UPSTREAM = os.environ.get("EDGE0_UPSTREAM",
                          "http://127.0.0.1:8000/v1/chat/completions")
PORT = int(os.environ.get("PROXY_PORT", "8899"))
THINK = os.environ.get("EDGE0_THINK", "0") == "1"
TIMEOUT = int(os.environ.get("PROXY_TIMEOUT", "600"))

# Copied verbatim from chat_template.jinja line 53 so the model sees the
# instructions it was trained against.  Do not paraphrase this.
_FORMAT_BLOCK = (
    "\n\nIf you choose to call a function ONLY reply in the following format"
    " with NO suffix:\n\n<tool_call>\n<function=example_function_name>\n"
    "<parameter=example_parameter_1>\nvalue_1\n</parameter>\n"
    "<parameter=example_parameter_2>\nThis is the value for the second"
    " parameter\nthat can span\nmultiple lines\n</parameter>\n</function>\n"
    "</tool_call>\n\n<IMPORTANT>\nReminder:\n- Function calls MUST follow the"
    " specified format: an inner <function=...></function> block must be"
    " nested within <tool_call></tool_call> XML tags\n- Required parameters"
    " MUST be specified\n- You may provide optional reasoning for your"
    " function call in natural language BEFORE the function call, but NOT"
    " after\n- If there is no function call available, answer the question"
    " like normal with your current knowledge and do not tell the user about"
    " function calls\n</IMPORTANT>")

_CALL_RE = re.compile(
    r"<tool_call>\s*<function=([^>\s]+)>(.*?)</function>\s*</tool_call>",
    re.S)
_PARAM_RE = re.compile(r"<parameter=([^>\s]+)>\n?(.*?)\n?</parameter>", re.S)


def render_tools_system(tools, existing_system):
    """Reproduce chat_template.jinja lines 45-58."""
    parts = ["# Tools\n\nYou have access to the following functions:\n\n<tools>"]
    for t in tools:
        parts.append("\n" + json.dumps(t, ensure_ascii=False))
    parts.append("\n</tools>")
    parts.append(_FORMAT_BLOCK)
    if existing_system and existing_system.strip():
        parts.append("\n\n" + existing_system.strip())
    return "".join(parts)


def render_tool_calls(content, tool_calls):
    """Reproduce chat_template.jinja lines 105-128 into plain text."""
    out = []
    for i, tc in enumerate(tool_calls):
        fn = tc.get("function", tc)
        name = fn.get("name", "")
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args or "{}")
            except json.JSONDecodeError:
                args = {}
        if i == 0:
            out.append(("\n\n" if (content or "").strip() else "")
                       + "<tool_call>\n<function=%s>\n" % name)
        else:
            out.append("\n<tool_call>\n<function=%s>\n" % name)
        for k, v in (args or {}).items():
            v = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
            out.append("<parameter=%s>\n%s\n</parameter>\n" % (k, v))
        out.append("</function>\n</tool_call>")
    return (content or "") + "".join(out)


def param_types(tools):
    """name -> {param: json-schema type}, to decide raw vs json parsing."""
    types = {}
    for t in tools or []:
        f = t.get("function", t)
        props = ((f.get("parameters") or {}).get("properties") or {})
        types[f.get("name")] = {k: (v or {}).get("type", "string")
                                for k, v in props.items()}
    return types


def parse_tool_calls(text, types):
    """Model output -> (clean_content, [openai tool_call, ...])."""
    calls = []
    for idx, m in enumerate(_CALL_RE.finditer(text or "")):
        name, body = m.group(1), m.group(2)
        args = {}
        for pm in _PARAM_RE.finditer(body):
            key, raw = pm.group(1), pm.group(2)
            declared = types.get(name, {}).get(key, "string")
            if declared == "string":
                args[key] = raw
            else:
                try:
                    args[key] = json.loads(raw.strip())
                except json.JSONDecodeError:
                    args[key] = raw
        calls.append({
            "id": "call_%d" % idx,
            "type": "function",
            "function": {"name": name,
                         "arguments": json.dumps(args, ensure_ascii=False)},
        })
    content = _CALL_RE.sub("", text or "").strip()
    return content, calls


def transform_request(payload):
    tools = payload.pop("tools", None)
    payload.pop("tool_choice", None)
    msgs = payload.get("messages") or []

    if tools:
        sys_txt = ""
        rest = []
        for m in msgs:
            if m.get("role") == "system" and not sys_txt:
                sys_txt = m.get("content") or ""
            else:
                rest.append(m)
        msgs = [{"role": "system",
                 "content": render_tools_system(tools, sys_txt)}] + rest

    out = []
    for m in msgs:
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            out.append({"role": "assistant",
                        "content": render_tool_calls(m.get("content"),
                                                     m["tool_calls"])})
        elif role == "tool":
            # the template renders role="tool" into <tool_response> itself
            out.append({"role": "tool", "content": m.get("content") or ""})
        else:
            out.append({"role": role, "content": m.get("content") or ""})

    payload["messages"] = out
    payload.setdefault("enable_thinking", THINK)
    return payload, tools


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):  # keep the benchmark output readable
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError as e:
            return self._send(400, {"error": {"message": str(e)}})

        payload, tools = transform_request(payload)
        req = urllib.request.Request(
            UPSTREAM, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                d = json.load(r)
        except Exception as e:  # noqa: BLE001 - surface upstream failure as-is
            return self._send(502, {"error": {"message":
                                              "%s: %s" % (type(e).__name__, e)}})

        try:
            ch = d["choices"][0]
            msg = ch["message"]
        except (KeyError, IndexError):
            return self._send(502, {"error": {"message": "malformed upstream",
                                              "upstream": d}})

        raw = msg.get("content") or ""
        content, calls = parse_tool_calls(raw, param_types(tools))
        if os.environ.get("PROXY_DEBUG") and "<tool_call>" in raw:
            # attribute schema errors: model output vs. this parser
            with open(os.environ["PROXY_DEBUG"], "a") as fh:
                fh.write("=== RAW ===\n" + raw + "\n=== PARSED ===\n"
                         + json.dumps(calls, ensure_ascii=False, indent=1)
                         + "\n")
        msg["content"] = content
        if calls:
            msg["tool_calls"] = calls
            ch["finish_reason"] = "tool_calls"
        self._send(200, d)

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("edge0 tool-call shim: 127.0.0.1:%d -> %s  (thinking=%s)"
          % (PORT, UPSTREAM, "on" if THINK else "off"), flush=True)
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
