# local-agentic-coding-24gb

Measurements and tooling for one question: which local model is actually usable for
agentic coding on a Mac with 24 GB of unified memory — and what breaks when one isn't.

Eight models, 302 tool calls, six identical runs per configuration, measured on an Apple
M5 Pro under macOS 26.6. Full write-up in [`report/`](report/), raw numbers in
[`results/measurements.json`](results/measurements.json).

> **Companion repo — the same question with 128 GB:**
> [local-agentic-coding-128gb](https://github.com/DG1001/local-agentic-coding-128gb)
> runs five large models (DeepSeek-V4-Flash, Laguna-S-2.1, KAT-Coder-V2.5, …) on an
> NVIDIA GB10 / DGX Spark-class box. The conclusions barely overlap with this one: at
> 24 GB the binding constraint is tooling, at 128 GB it is **memory bandwidth** — and
> the choice of agent harness turns out to matter as much as the model.

## The short version

With a one-sentence system prompt, every model passes. What separates them is a
realistic agent prompt of ~5,600 tokens — the size OpenCode, aider and crush actually
send.

| Model | Weights | Engine | Repair task | Wired |
|---|---:|---|---|---:|
| gpt-oss-20b MXFP4 | 12.08 GB | MLX | **6/6**, 55 s median | 67 % |
| Qwen3.8-27B IQ4_XS | 14.25 GB | llama.cpp | **6/6**, 212 s median | 73 % |
| **Qwen3.5-9B 4-bit** | **5.95 GB** | MLX | **5/6**, 57 s median | **39 %** |
| Nanbeige4.2-3B Q4_K_M | **2.68 GB** | llama.cpp (upstream) | 5/6, 62 s median | 47 % |
| Gemma 4 12B Q4_K_M | 7.38 GB | llama.cpp | 5/6, 156 s median | 51 % |
| Qwen3.6-35B-A3B 3-bit | 15.20 GB | MLX | 3/4, 177 s median | 84 % |
| Devstral-Small-2-24B | 12.76 GB | llama.cpp | 2/2, 132 s median | — |
| Gemma 4 12B MLX-4bit | 6.74 GB | MLX | **0/6** — engine defect | — |

**The smallest model nearly wins.** Qwen3.5-9B matches gpt-oss on speed at half the
weights, trails it by one run on reliability, and needs 39 % of memory instead of 67 %.
Under the agent-sized system prompt it scores **6/6 at an 8.3 s median** — twice as fast
as gpt-oss on the same test.

**Two models score 6/6 — and one of them takes four times as long.** Qwen3.8-27B, dense
and 14.25 GB, matches gpt-oss exactly on reliability and needs a 212 s median against
55 s. Dense models compute every parameter per token; MoE models activate a fraction.
Pick by *active* parameters, not total ones — the companion study measures the same
effect at 128 GB.

**And for four of eight models, the inference engine decided usability.** MLX capped
Devstral's context at 4,864, refused to load Qwen3.6-27B at all, and broke on Gemma's
channel format. Nanbeige4.2-3B fails on *both* of LM Studio's engines — only an upstream
llama.cpp build runs it. The engine version matters, not just the engine.

**And if you are running a general-purpose agent, cut its toolset — and budget for a
larger model.** Hermes Agent with its 17 default toolsets could not finish this task with
any model tested; the same gpt-oss that scores 6/6 through a two-tool harness left the
file with a `SyntaxError`. Restricted to `-t terminal,file` it finished in 2:28.
Qwen3.5-9B failed either way. A local general-purpose agent on 24 GB therefore costs a
21B-class model at ~67 % of memory, not the 39 % a 9B would have needed.

The one insight that saves time before any download: **file size is the wrong number.**
Two similarly sized models can differ by 8× in KV cache cost. There is a tool for that
here.

## If you landed here from a search

These are the concrete symptoms this study diagnosed. Each one looked like a model
failure and was not.

| Symptom | Cause | Where |
|---|---|---|
| `Model type nanbeige not supported` | LM Studio's MLX runtime predates the architecture; upstream llama.cpp runs it | Finding 6 |
| `llama-server exited before becoming healthy, exitCode=1` | LM Studio's bundled llama.cpp is too old — `lms runtime update` still says "up-to-date" | Finding 6 |
| `<\|channel>thought` repeating until the token limit | LM Studio's MLX path does not strip Gemma 4's channel markers; GGUF does | Finding 6 |
| `The number of tokens to keep from the initial prompt is greater than the context length` | LM Studio silently capped the context at load — check the `CONTEXT` column of `lms ps` | Finding 4 |
| Model loads fine but `lms ps` shows less context than requested | KV cache does not fit; recompute with `tools/kvcalc.py` | Finding 4 |
| Desktop flickers while a model generates | Wired memory past ~80 %; WindowServer is starved. Save and unload | Finding 10 |
| `panic ... @IOGPUGroupMemory.cpp` after a long agent session | Unresolved Apple IOGPU defect, triggered by unbounded KV growth | Finding 10 |
| `opencode run` hangs, or exits instantly with code 0 and an empty log | `permission` defaults to `ask`; without a TTY it gets EOF | Finding 12 |
| Agent rambles instead of calling tools | Sampling (`temp 0.3` without `top_k`/`top_p`) on a fragile model, or too many tools offered | Findings 3, 7 |
| `lms get` reports success but nothing downloaded | It returns exit code 0 on failure — check file sizes | Finding 12 |
| `hf download` aborts instantly, target directory stays at 4 KB | `HF_HUB_ENABLE_HF_TRANSFER=1` set but `hf_transfer` not installed | Finding 12 |
| Wired memory far higher than weights + KV | LM Studio's `PARALLEL` holds the KV cache per slot — use `--parallel 1` | Finding 7 |
| A ~16 GB quant refuses to load, a ~14 GB one is fine | Guardrail threshold, not a hard limit — recompute with `tools/kvcalc.py` before blaming the model | Findings 4, 5 |

**Models measured here:** gpt-oss-20b · Qwen3.5-9B · Qwen3.8-27B · Qwen3.6-35B-A3B · Qwen3.6-27B ·
Devstral-Small-2-24B · Gemma 4 12B · Gemma 4 26B-A4B · Nanbeige4.2-3B
**Runtimes:** MLX · llama.cpp · TurboFieldfare (SSD expert streaming)
**Harnesses:** OpenCode · Hermes Agent · a purpose-built 180-line Python loop
**Hardware:** Apple M5 Pro, 24 GB unified memory, macOS 26.6

## `tools/kvcalc.py` — will it fit?

Reads `config.json`, counts the layers that actually cost KV cache, and works out what
is left at your context length.

```bash
python3 tools/kvcalc.py mlx-community/gpt-oss-20b-MXFP4-Q8 --ram 24 --context 32768
```

```
  Attention     layer_types: 12 of 24 full-attention
  KV cache      24.0 KB/token
  Weights       12.08 GB
  + KV @ 32768   0.81 GB
  + Overhead     2.50 GB
  = total       15.38 GB of 24 GB  ->  64 %
  Verdict       comfortable
```

The same for Devstral, which has no sliding-window layers:

```bash
python3 tools/kvcalc.py mistralai/Devstral-Small-2-24B-Instruct-2512 \
    --ram 24 --context 16384 --weights 14.39
```

```
  Attention     no sliding window: all 40 layers cost KV
  KV cache      160.0 KB/token          <- 6.7x as much
  = total       19.57 GB of 24 GB  ->  82 %
  Verdict       critical
```

The prediction held: the tool says 15.38 GB for gpt-oss, measured was 16.11 GB.

Always point it at the **quantisation you actually load**, not the original repo —
otherwise you are computing with bf16 sizes.

## The benchmark

Two tasks, both machine-verifiable, both runnable against any OpenAI-compatible endpoint.

### Repair task — the meaningful one

An ISO-8601 duration parser with 22 tests, 7 of them failing, from three independent
bugs in different places: a missing feature (week designators absent from both the regex
*and* the unit table), a crash (`int()` on fractional values), and a logic error (sign
captured but never applied).

```bash
export LLM_URL=http://127.0.0.1:1234/v1/chat/completions
python3 bench/realagent.py <model-id> /tmp/run1
```

Verification is the test suite itself. The runner additionally checks that
`test_duration.py` is byte-identical afterwards — editing the tests is the obvious
shortcut, and models take it.

Output is a single JSON line:

```json
RESULT {"steps": 8, "tool_calls": 7, "schema_errors": 0, "bash_calls": 6,
        "write_calls": 1, "tests_before": "15/22 passing",
        "tests_after": "22/22 passing", "all_green": true,
        "tests_untouched": true, "wall_s": 63.0}
```

### Synthetic task — measures the effect of prompt size

The same trivial task, once with a one-sentence prompt and once with ~5,600 tokens of
agent instructions:

```bash
python3 bench/miniagent.py <model-id> /tmp/run_small small
python3 bench/miniagent.py <model-id> /tmp/run_large large
```

This is the test that separated the models.

### Configuration

Everything through environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `LLM_URL` | `http://127.0.0.1:1234/v1/chat/completions` | endpoint |
| `MAX_TOK` | 4096 | `max_tokens` |
| `TEMP` / `TOP_P` / `TOP_K` / `REP_PEN` | 0.6 / 0.95 / 20 / 1.05 | sampling |

`TOP_K=0` omits `top_p`, `top_k` and `repetition_penalty` **entirely** — that reproduces
the broken configuration which made one model unusable and did not bother another at all.

## What the harness deliberately does itself

It validates tool-call arguments against the declared schema rather than trusting the
agent framework. That is why it exists: the investigation started with `SchemaError`
messages from OpenCode, and the framework turned out to be the cause twice. A harness
with no layer in between separates model behaviour from tool behaviour.

Result across the whole series: **one malformed tool call in 302.**

## Requirements

Python 3.9 or newer, no dependencies beyond the standard library. `kvcalc.py` needs
network access for HF model IDs but also works with local paths.

## Layout

```
bench/          harness and tasks
  agentlib.py     core: payload building, schema validation, tool execution
  realagent.py    repair task
  miniagent.py    synthetic task, prompt-size comparison
  task/           the broken ISO-8601 parser and its test suite
tools/
  kvcalc.py       memory footprint from config.json
  install_supervisor.sh   restart watchdog for TurboFieldfare's installer
configs/
  opencode.example.json   providers for LM Studio and TurboFieldfare
report/           the full write-up (Markdown and HTML)
results/          raw numbers from every measurement
```

## Limits of these measurements

One machine, one day, six runs per configuration. Enough to tell 3/6 from 6/6, not
enough to tell 5/6 from 6/6. Treat single-run differences as noise.

The repair task is real but small — one module, three bugs, a test suite that runs in
milliseconds. It says nothing about a refactor spanning twenty files.

The report contains a section listing eleven conclusions that had to be retracted during
the investigation. It is there because the pattern transfers better than the individual
results: five of the eleven were tooling behaviour mistaken for model behaviour.

## Licence

MIT, see [LICENSE](LICENSE).
