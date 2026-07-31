#!/usr/bin/env python3
"""Minimales Agent-Harness. Validiert Toolcall-Argumente selbst gegen das
deklarierte Schema -- das ist die eigentliche Fehlermessung.

Konfiguration ueber Umgebungsvariablen:
  LLM_URL, MAX_TOK, TEMP, TOP_P, TOP_K, REP_PEN
"""
import json, os, subprocess, sys, urllib.request

URL = os.environ.get("LLM_URL", "http://127.0.0.1:1234/v1/chat/completions")
REQ_TIMEOUT = int(os.environ.get("REQ_TIMEOUT", "300"))
MAX_TOK = int(os.environ.get("MAX_TOK", "4096"))
TEMP = float(os.environ.get("TEMP", "0.6"))
TOP_P = float(os.environ.get("TOP_P", "0.95"))
TOP_K = int(os.environ.get("TOP_K", "20"))
REP_PEN = float(os.environ.get("REP_PEN", "1.05"))

TOOLS = [
    {"type": "function", "function": {
        "name": "bash", "description": "Execute a shell command and return its output.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "The shell command to execute"}},
            "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "write", "description": "Write content to a file, creating or overwriting it.",
        "parameters": {"type": "object", "properties": {
            "filePath": {"type": "string", "description": "Path to the file"},
            "content": {"type": "string", "description": "Full content to write"}},
            "required": ["filePath", "content"]}}},
]


def post(payload):
    req = urllib.request.Request(
        URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=REQ_TIMEOUT) as r:
        return json.load(r)


def build_payload(model, msgs):
    p = {"model": model, "messages": msgs, "tools": TOOLS,
         "tool_choice": "auto", "max_tokens": MAX_TOK, "temperature": TEMP}
    if TOP_K > 0:
        p["top_p"] = TOP_P
        p["top_k"] = TOP_K
        p["repetition_penalty"] = REP_PEN
    return p


def run_tool(name, args, workdir, stats):
    """Fuehrt Tool aus, nachdem das Schema geprueft wurde."""
    spec = next(t["function"] for t in TOOLS if t["function"]["name"] == name)
    missing = [k for k in spec["parameters"]["required"] if k not in args]
    if missing:
        stats["schema_errors"] += 1
        stats["schema_detail"].append(f"{name}: missing {missing}, got {sorted(args)}")
        return f"ERROR: missing required parameter(s) {missing}. Provided keys: {sorted(args)}"

    if name == "bash":
        try:
            p = subprocess.run(args["command"], shell=True, cwd=workdir,
                               capture_output=True, text=True, timeout=60)
            return (p.stdout + p.stderr)[:4000] or "(no output)"
        except subprocess.TimeoutExpired:
            return "ERROR: command timed out"
    if name == "write":
        fp = args["filePath"]
        if not os.path.isabs(fp):
            fp = os.path.join(workdir, fp)
        os.makedirs(os.path.dirname(fp) or workdir, exist_ok=True)
        with open(fp, "w") as f:
            f.write(args["content"])
        return f"Wrote {len(args['content'])} bytes to {fp}"
    return "ERROR: unknown tool"


def new_stats():
    return {"schema_errors": 0, "schema_detail": [], "steps": 0, "tool_calls": 0,
            "reasoning_tokens": 0, "completion_tokens": 0, "prompt_tokens": 0,
            "cached_tokens": 0, "length_stops": 0, "timeouts": 0,
            "bash_calls": 0, "write_calls": 0}


def account(stats, d):
    u = d.get("usage", {}) or {}
    stats["completion_tokens"] += u.get("completion_tokens", 0)
    stats["prompt_tokens"] += u.get("prompt_tokens", 0)
    stats["cached_tokens"] += (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    stats["reasoning_tokens"] += (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
    return u
