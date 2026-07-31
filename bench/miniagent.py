#!/usr/bin/env python3
"""Synthetic agent run: measures the effect of system-prompt size.

The same trivial task, once with a one-sentence system prompt and once with
~5,600 tokens of plausible agent instructions -- the size OpenCode, aider and
crush actually send.

This is the test that separated the models: with the short prompt they all
passed, with the long one only a single model did.

Usage: miniagent.py <model> <workdir> <small|large> [maxsteps]

Configuration through environment variables, see agentlib.py:
    LLM_URL, MAX_TOK, TEMP, TOP_P, TOP_K, REP_PEN
TOP_K=0 omits top_p/top_k/repetition_penalty entirely -- that reproduces the
broken sampling configuration from the report.
"""
import io, json, os, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agentlib as A

SYS_SMALL = ("You are a coding agent. Use the provided tools to complete the task. "
             "When done, reply with a short summary.")

# Inflated to the size of a real agent prompt. The content is deliberately
# generic: what is measured is size, not quality.
SYS_LARGE = SYS_SMALL + "\n\n" + "\n".join(
    f"## Guideline {i}\n"
    f"- Prefer editing existing files over creating new ones when guideline {i} applies.\n"
    f"- Never add comments unless explicitly requested by the user in scenario {i}.\n"
    f"- Always verify your work by running the relevant command for case {i}.\n"
    f"- Follow the existing code conventions of the project in context {i}.\n"
    f"- Do not commit changes unless the user asks, per rule {i}.\n"
    for i in range(1, 61)
)

TASK = ('Create a file greet.py with a function greet(name) that returns the string '
        '"Hello, <name>!". Then run it with python3 to verify that greet("World") '
        'produces exactly: Hello, World!  Fix and re-run if it fails.')

# Suppress import-time output: some models additionally write a module-level
# print(greet("World")). That satisfies the task; a naive check would wrongly
# score it as a failure.
_CHECK = (
    "import io,contextlib,sys\n"
    "buf=io.StringIO()\n"
    "with contextlib.redirect_stdout(buf):\n"
    "    import greet\n"
    "sys.stdout.write(repr(greet.greet('World')))\n"
)


def check_task(workdir):
    if not os.path.exists(os.path.join(workdir, "greet.py")):
        return "NOFILE"
    p = subprocess.run([sys.executable, "-c", _CHECK], cwd=workdir,
                       capture_output=True, text=True)
    if p.stdout.strip() == repr("Hello, World!"):
        return "PASS"
    tail = (p.stdout.strip() or (p.stderr.strip().splitlines() or [""])[-1])[:70]
    return f"FAIL({tail})"


def main():
    model, workdir, size = sys.argv[1], sys.argv[2], sys.argv[3]
    maxsteps = int(sys.argv[4]) if len(sys.argv) > 4 else 15
    os.makedirs(workdir, exist_ok=True)

    msgs = [{"role": "system", "content": SYS_SMALL if size == "small" else SYS_LARGE},
            {"role": "user", "content": f"{TASK}\n\nWork in the directory: {workdir}"}]
    stats = A.new_stats()
    t0 = time.time()

    for step in range(maxsteps):
        stats["steps"] = step + 1
        try:
            d = A.post(A.build_payload(model, msgs))
        except Exception as e:
            stats["timeouts"] += 1
            print(f"  step {step+1}: REQUEST FAILED {type(e).__name__}: {str(e)[:100]}", flush=True)
            break

        u = A.account(stats, d)
        ch = d["choices"][0]
        if ch.get("finish_reason") == "length":
            stats["length_stops"] += 1
        m = ch["message"]
        tcs = m.get("tool_calls") or []
        if not tcs and not (m.get("content") or "").strip():
            stats["empty_responses"] = stats.get("empty_responses", 0) + 1

        print(f"  step {step+1}: {ch.get('finish_reason')} compl={u.get('completion_tokens')} "
              f"reason={(u.get('completion_tokens_details') or {}).get('reasoning_tokens')} "
              f"tools={[t['function']['name'] for t in tcs]}", flush=True)

        msgs.append({"role": "assistant", "content": m.get("content") or "",
                     "tool_calls": tcs} if tcs else
                    {"role": "assistant", "content": m.get("content") or ""})
        if not tcs:
            break

        for tc in tcs:
            stats["tool_calls"] += 1
            fn = tc["function"]["name"]
            stats["bash_calls" if fn == "bash" else "write_calls"] += 1
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError as e:
                stats["schema_errors"] += 1
                stats["schema_detail"].append(f"{fn}: invalid JSON args: {e}")
                args, out = {}, f"ERROR: arguments were not valid JSON: {e}"
            else:
                out = A.run_tool(fn, args, workdir, stats)
            msgs.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})

    stats["verify"] = check_task(workdir)
    stats["prompt_size"] = size
    stats["wall_s"] = round(time.time() - t0, 1)
    print("RESULT " + json.dumps(stats), flush=True)


if __name__ == "__main__":
    main()
