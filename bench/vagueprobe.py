#!/usr/bin/env python3
"""Does the model act on a vague prompt, or narrate the action in prose?

The measurement behind Findings 16 and 17. repair_task names the command to run
in its task text, and that turned out to hide a whole failure mode: given a
vague instruction -- what one actually types in the tenth turn of a session --
some configurations stop emitting tool calls and describe them instead
("Ich werde jetzt die Dateien mit dem Werkzeug glob betrachten"). No argument
is ever malformed, so no schema-error column anywhere in the report sees it.

One request per turn, no tools are executed: the only question is whether the
first answer contains a tool call. Counted are turns with at least one tool
call, not the number of calls -- an early version summed calls and reported
14/12.

The tool surface is jaja's six tools with placeholder schemas; the system
prompt is jaja's in substance. max_tokens is 600 because that is what the
published cells were measured with. A model with a long reasoning block can
exhaust it and end on finish_reason 'length' without a call, which is why the
finish reasons are printed alongside the count.

Usage: vagueprobe.py <vague|explicit> [turns]

Endpoint through LLM_URL as in agentlib.py.
"""
import json, os, sys, urllib.request

URL = os.environ.get("LLM_URL", "http://127.0.0.1:1234/v1/chat/completions")

TOOLS = [{"type": "function", "function": {
            "name": name, "description": desc,
            "parameters": {"type": "object",
                           "properties": {"a": {"type": "string"}},
                           "required": ["a"]}}}
         for name, desc in [("glob", "Dateien nach Muster finden"),
                            ("grep", "In Dateien suchen"),
                            ("read", "Datei lesen"),
                            ("write", "Datei schreiben"),
                            ("edit", "Stelle in Datei aendern"),
                            ("bash", "Shell-Befehl ausfuehren")]]

SYSTEM = ("Du bist ein Programmierassistent und arbeitest in einem "
          "Projektverzeichnis. Arbeite selbststaendig: lies, aendere und pruefe. "
          "Nutze Werkzeuge, statt zu beschreiben, was zu tun waere.")

PROMPTS = {
    "vague":    "schau dir die daten an und mach weiter",
    "explicit": "Lies zuerst sketch.js mit dem read-Werkzeug. Rufe jetzt ein Werkzeug auf.",
}


def one_turn(prompt):
    body = {"model": "m", "tools": TOOLS, "tool_choice": "auto",
            "max_tokens": 600, "temperature": 0.6, "top_p": 0.95,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": prompt}]}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        choice = json.load(r)["choices"][0]
    return bool(choice["message"].get("tool_calls")), choice.get("finish_reason")


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else "vague"
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    if kind not in PROMPTS:
        sys.exit(f"unknown prompt kind {kind!r}, expected one of {sorted(PROMPTS)}")

    acted, reasons = 0, {}
    for _ in range(turns):
        called, reason = one_turn(PROMPTS[kind])
        acted += called
        reasons[reason] = reasons.get(reason, 0) + 1

    print(f"{kind}: {acted}/{turns} turns with a tool call   finish_reason: {reasons}")
    print("RESULT " + json.dumps({"prompt": kind, "turns": turns,
                                  "with_tool_call": acted, "finish_reasons": reasons}))


if __name__ == "__main__":
    main()
