# Local agentic coding on a 24 GB Mac: the system prompt is the benchmark

*Field notes — Apple M5 Pro, 24 GB, macOS 26.6 (25G72), LM Studio 0.4.20, OpenCode 1.18.9*

Seven models, 263 tool calls, six identical runs per configuration. Every model aced the
task in isolation. What separated them was a five-thousand-token system prompt — the
thing every real coding agent sends. Along the way: one kernel panic, a flickering
desktop as the only warning macOS ever gave, and eleven confident conclusions I had to
retract.

> The formatted version with an interactive chart is in [`report.html`](report.html).
> Raw numbers: [`../results/measurements.json`](../results/measurements.json).

---

## The result

The task was identical throughout: write `greet.py` with a `greet(name)` function, run it
with `python3`, verify the output, fix it if wrong. Two tools available, `bash` and
`write`. Six runs per configuration, success measured by actually importing the resulting
file and calling the function.

The only variable that mattered was how much system prompt sat in front of that task.

| Model | On disk | Small prompt | Agent prompt | + broken sampling |
|---|---:|---:|---:|---:|
| **Qwen3.5-9B 4-bit** | **5.95 GB** | — | **6/6** · 8.3 s | — |
| gpt-oss-20b MXFP4 | 12.08 GB | 6/6 | **6/6** · 16.4 s | **6/6** |
| Devstral-Small-2-24B MXFP4 | 14.39 GB | 6/6 | won't fit | — |
| Qwen3.6-35B-A3B MLX 3-bit | 15.20 GB | 6/6 | 3/6 | 0/6 |

"Small" is a one-sentence system prompt (245 prompt tokens); "agent prompt" is ~5,600
tokens of plausible instructions — the size OpenCode, aider and crush actually send.

Read the first column and every model looks fine: 9 to 12 seconds per task, not one
malformed tool call, nothing to choose between them. Read the agent-prompt column and
two of four are left.

**This is why "it works on my machine" reports about local coding models are so
unreliable.** A quick manual test uses a short prompt. An agent does not.

### The configuration, if that is all you want

```
model              gpt-oss-20b MXFP4        (12.08 GB)
context            32768
temperature        0.6      // see Finding 3 — may not matter
top_p              0.95
top_k              20
repetition_penalty 1.05
tool_choice        "auto"   // NEVER "required"
max_tokens         8192     // completions reach ~2400
iogpu.wired_limit_mb  leave at 0
```

Measured: 6/6 under a realistic agent prompt, 16.4 s median, 16.11 GB wired (67 %), loads
in 6.1 seconds. Confirmed end-to-end in OpenCode's interactive TUI, which built a working
three-file todo app from a single instruction.

Under the agent-sized prompt Qwen3.5-9B is not merely adequate but the fastest of the
set: **6/6 at an 8.3 s median**, 19 tool calls, no schema errors, no run without a tool
call, no length stop — against gpt-oss's 16.4 s on the identical test. At 5.95 GB of
weights.

That matters beyond this benchmark. Agent harnesses state context requirements: Hermes,
for instance, asks for at least 64K. At that length gpt-oss needs 67 % of memory and
Qwen3.5-9B 44 % — both qualify, one with room to spare.

---

## Finding 1 — It holds up on real work

Everything above uses a deliberately tiny task, which proves less than it looks like. So
the last test was a small but genuine repair job: an existing 100-line ISO-8601 duration
module with a 22-test suite, seven of them failing, from **three independent bugs** in
different places — a missing feature (week designators absent from both the regex and the
unit table), a crash (`int()` on fractional values), and a logic error (the sign captured
but never applied). Instruction: make the suite pass, do not touch the tests.

| Run | Steps | bash | write | Schema errors | Reasoning | Result | Wall |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10 | 7 | 2 | 1 | 1,548 | 22/22 | 63.7 s |
| 2 | 9 | 7 | 1 | 0 | 1,967 | 22/22 | 53.9 s |
| 3 | 7 | 5 | 1 | 0 | 719 | 22/22 | 37.1 s |
| 4 | 8 | 6 | 1 | 0 | 2,605 | 22/22 | 63.0 s |
| 5 | 5 | 3 | 1 | 0 | 556 | 22/22 | 27.8 s |
| 6 | 8 | 6 | 1 | 0 | 2,131 | 22/22 | 56.0 s |

**Six for six, median 55 seconds.** All three bugs found and fixed in a single pass each
time. The tests were never modified — worth checking explicitly, because editing the test
suite is the obvious shortcut and models take it.

The patch reads like something a person would write: the week group inserted at the
correct grammatical position (before the `T` separator, where ISO-8601 puts it), `int()`
changed to `float()` **and** the accumulator initialised to `0.0` — the second half being
the part that is easy to miss — plus four lines applying the sign after summation. No
invented features, no gratuitous restructuring.

The same task for the other models:

| Model | Weights | Engine | Verified | Median | Schema errors | Wired |
|---|---:|---|---:|---:|---:|---:|
| gpt-oss-20b MXFP4 | 12.08 GB | MLX | **6/6** | 55 s | 1/41 | 16.1 GB · 67 % |
| **Qwen3.5-9B 4-bit** | **5.95 GB** | MLX | **5/6** | **57 s** | 0/28 | **9.4 GB · 39 %** |
| Nanbeige4.2-3B Q4_K_M | **2.68 GB** | llama.cpp ¹ | 5/6 | 62 s | 0/42 | 11.3 GB · 47 % |
| Gemma 4 12B Q4_K_M | 7.38 GB | llama.cpp | 5/6 | 156 s | 0/30 | 12.3 GB · 51 % |
| Devstral-Small-2-24B IQ4_XS | 12.76 GB | llama.cpp | 2/2 | 132 s | 0/12 | — |
| Qwen3.6-35B-A3B 3-bit | 15.20 GB | MLX | 3/4 | 177 s | 0/31 | **20.2 GB · 84 %** |
| Gemma 4 12B MLX-4bit | 6.74 GB | MLX | **0/6** | — | 0/16 | engine defect, see Finding 6 |

¹ Upstream llama.cpp only — LM Studio's bundled runtimes cannot load it at all. See Finding 6.

The Qwen MoE is the slowest despite activating only 3B of its 35B parameters — its
failures are expensive, and its one bad run burned 8,211 reasoning tokens going nowhere.

Variance is substantial: gpt-oss run 5 finished in 4 tool calls and 556 reasoning tokens,
run 4 needed 2,605. A factor of 4.7 on an identical task. Single runs tell you little.

### A 3B model matches a 9B

`Nanbeige4.2-3B` scores the same 5/6 at **2.68 GB of weights** — under a third of
Qwen3.5-9B and on the slower backend, because no engine that ships with LM Studio can
load it. Median 62 s, or 55 s excluding two outliers at 378 and 413 seconds. Variance is
its weak point: four runs land between 40 and 65 seconds, two take six times that.

It also illustrates Finding 4 better than any other model here. Its weights are the
smallest in the set, but **its memory share is higher than Qwen3.5-9B's** — 47 % against
39 %. All 22 layers are full attention at 8 KV heads and head_dim 128, so the KV cache
runs 88 KB/token. At 32k that is 2.95 GB of cache against 2.68 GB of weights: **the
context costs more than the parameters.** Picking it by file size would have been a
mistake in both directions.

### Turning off reasoning does not help

An obvious idea, since Devstral solves this task with `reasoning_tokens: 0`: disable
thinking on the Qwen MoE and skip the loop entirely.

| Mode | Reasoning | Completion | Time | Tool call |
|---|---:|---:|---:|---|
| thinking on | 108 | 169 | 4.4 s | yes |
| `/no_think` | 2 | 2,047 *(limit)* | 64.8 s | **no** |

Without thinking the model stops calling tools altogether and rambles to the token limit.
For Qwen3.6 the reasoning is load-bearing for tool use — you cannot strip it and get a
non-reasoning model's behaviour. Devstral works without it because it was trained that
way, not because thinking is optional.

*(`chat_template_kwargs: {"enable_thinking": false}` is silently ignored by LM Studio;
only the `/no_think` token in the message actually takes effect.)*

---

## Finding 2 — One malformed tool call in 263

The question that started this investigation was whether 3-bit quantisation was
corrupting tool arguments. Across the whole study — six models, three prompt sizes, two
sampling regimes, plus the repair task — **263 tool calls produced exactly one schema
failure**: a `write` with a completely empty arguments object. The agent recovered on the
next step and the run still went green.

The harness validates this itself rather than trusting the agent framework, declaring the
JSON schema and checking every incoming call against its own `required` list before
executing it.

One detail is suggestive but unproven: the single failure came on the real task, where
`write` arguments carry an entire 1,400-token source file, not the two short strings the
toy task needed. Large arguments may well be where this risk lives. One occurrence is not
evidence; it stands here as a hypothesis.

> **The distinction that matters:** "model emits broken tool arguments" and "model emits
> no tool calls at all" look identical in an agent's error log and have nothing in common
> underneath. The first points at quantisation. The second — the one that actually
> happened — points at instruction following under context pressure. I spent hours on the
> wrong one.

---

## Finding 3 — Sampling rescues a fragile model and is irrelevant to a robust one

Qwen's documented recommendation for thinking mode is `temperature 0.6`, `top_p 0.95`,
`top_k 20`. I had been running `temperature 0.3` with no truncation parameters at all. On
the Qwen MoE the difference is not subtle:

| Sampling | Reasoning tokens | Wall | Finish | Result |
|---|---:|---:|---|---|
| temp 0.3, no top_k/top_p | 8,191 | 143 s | length | nothing |
| temp 0.6, top_p 0.95, top_k 20 | 105 | 4 s | tool_calls | correct call |

A 78× difference from four numbers. Low temperature without nucleus and top-k truncation
drives this model into a repetition loop. The fingerprint in LM Studio's server log is
unmistakable: repeated *token ID 0* (`!`) rejected as an invalid sample.

> **Sampling reduces this failure — it does not remove it.** The correct parameters took
> the Qwen MoE from 0/6 to 3/6 on the synthetic task and 3/4 on the real one. But the
> token-ID-0 loop still appeared *with correct sampling*, in one run of four, burning
> 8,211 reasoning tokens.

**Then I ran the same broken configuration against gpt-oss, and it did not care.**

| Model | Verified | Median | Tool calls | Length stops |
|---|---:|---:|---:|---:|
| gpt-oss-20b | **6/6** | 14.4 s | 14 | 0 |
| Qwen3.6-35B-A3B | 0/6 | — | 0 | every step |

gpt-oss was in fact *faster* with the "broken" settings — 14.4 s against 16.4 s — because
lower temperature made it more decisive and it needed fewer steps.

So the honest version of this finding is narrower than the one I first published: these
parameters are not a general fix for local agentic coding. They are a rescue for a model
that is fragile to them. If your model needs them, it is telling you something about
itself.

---

## Finding 4 — File size is the wrong number. Compute the KV cache.

I picked candidates by weight size, and it led me astray. Devstral-Small-2-24B is
*smaller* on disk than the Qwen MoE — 14.39 against 15.20 GB — and far less usable on
this machine, because its attention architecture is completely different.

Qwen3.5/3.6 interleave linear-attention layers with full-attention ones; gpt-oss
alternates sliding-window and full attention with a 128-token window. Only full-attention
layers cost KV cache. Devstral has `sliding_window: null` — all 40 layers are full
attention, at 8 KV heads and `head_dim` 128.

```
bytes/token = full_attention_layers
            × num_key_value_heads
            × head_dim
            × 2   (K and V)
            × 2   (bytes per fp16 element)
```

| Model | Layers | Full-attn | KV heads | head_dim | KB/token | KV @32k | Usable context |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3.6-35B-A3B | 40 | 10 | 2 | 256 | 20 | 0.65 GB | 32,768 |
| gpt-oss-20b | 24 | 12 | 8 | 64 | 24 | 0.75 GB | 32,768 |
| Qwen3.5-9B | 32 | 8 | 4 | 256 | 32 | 1.07 GB | 92,672 |
| gemma-4-12B | 48 | 8 | 8 | 256 | 64 | 2.15 GB | 90,624 |
| Devstral-Small-2-24B | 40 | **40** | 8 | 128 | **160** | **5.00 GB** | **4,864** |
| Qwen3-14B *(older gen)* | 40 | **40** | 8 | 128 | **160** | 5.37 GB | — |

[`tools/kvcalc.py`](../tools/kvcalc.py) computes this from `config.json` before you spend
a gigabyte of bandwidth.

> **LM Studio silently capped the context.** I requested 16,384 tokens. The model loaded
> successfully in 6.1 seconds with no warning of any kind — and the `CONTEXT` column of
> `lms ps` read **4,864**. `--parallel 1` made no difference. The only symptom came later
> as HTTP 400: *"The number of tokens to keep from the initial prompt is greater than the
> context length"*. Check `lms ps` after every load.

Note the contrast at the other end of the table: because hybrid attention makes their KV
cache cheap, LM Studio granted Qwen3.5-9B and Gemma 4 12B over 90,000 tokens unprompted.

---

## Finding 5 — The smallest model nearly wins

`Qwen3.5-9B` is the surprise of the series. At **half the weights of gpt-oss** it matches
its speed, trails its reliability by one run, and needs **39 % of memory instead of
67 %**. A 9B of the newer generation beats a 35B of the previous one decisively, at a
fifth of the footprint.

Its one failure is benign in shape: run 3 stopped after 4 seconds with a single tool call
and 107 reasoning tokens. It ran the tests once and gave up. No loop, no token limit, no
degenerate output — a fresh session would have fixed it. That is a different animal from
the Qwen MoE's failures, which were expensive and could not be aborted.

Which inverts the question this investigation started with. It began as "which large
model still fits" and ends at **"which smallest model does the job reliably"** — because
on this machine, memory headroom converts directly into stability.

---

## Finding 6 — The engine decides usability, not just speed

Four times in one day, switching engine turned a model from unusable into working. Every time, the failure looked like a model failure in the log.

| Model | Under MLX | Under GGUF |
|---|---|---|
| Devstral-Small-2-24B | context silently capped at 4,864 | 16,384 as requested |
| Qwen3.6-27B | guardrail refuses to load at all | loads at full context |
| Gemma 4 12B | **0/6** — channel-marker loop | **5/6** |
| Nanbeige4.2-3B | `Model type nanbeige not supported` | LM Studio's build crashes; upstream works |

The fourth case sharpens the finding. `Nanbeige4.2-3B` fails on *both* LM Studio paths —
MLX rejects the architecture outright, and the bundled llama.cpp 2.27.1 exits with
`llama-server exited before becoming healthy, exitCode=1`. `lms runtime update` reports
everything already up to date. A `brew install llama.cpp` (build 10210) runs it without
complaint.

So it is not enough to choose between MLX and llama.cpp. **The engine version matters** —
LM Studio's bundled runtimes lagged this architecture by weeks, and the CLI gives no hint
that a newer build exists elsewhere.

The Gemma case is the cleanest, because the same model ran the same task through the same
harness with the same sampling — the engine was the only variable.

Under LM Studio's MLX path, Gemma's channel markers leak into `content` as raw text:

```
<|channel>thought
<channel|>
```

It starts at 28 characters. After the step that reads `duration.py`, generation
degenerates into nothing but markers — **49,258 characters, 8,191 tokens, length stop** —
in two independent runs at exactly the same point. `reasoning_tokens` read 0 throughout.

My first explanation was a feedback loop: the harness writes content back as an assistant
message, the model sees its own broken markers and produces more. The control experiment
refuted it — with markers stripped (cleaned content: 0 characters at every step) it broke
at the same place again. The loop is generated fresh, not fed back.

Under llama.cpp the problem vanishes completely: not a single marker, and
`reasoning_tokens` lands between 225 and 2,797. What is correctly recognised and
separated as reasoning there is the garbage that blows up the output under MLX — two
sides of the same thing.

> **The cost is speed.** llama.cpp does not use the M5's neural accelerators and runs
> roughly 2.4× behind MLX. Gemma needs a 156 s median under GGUF against 55 s for gpt-oss
> under MLX, with heavy variance: four clean runs between 146 and 164 seconds, plus one
> outlier at 1,226 seconds.
>
> For models that run cleanly under MLX, MLX stays the better choice. But when a model
> behaves strangely, switching the engine is the *first* test, not the last.

---

## Finding 7 — Wired memory is a step function, and pressure monitoring cannot see it

MLX loads safetensors via `mmap`. At idle those pages are file-backed — active or
inactive, not wired. The moment inference starts the GPU wires them, and wired memory
jumps to a plateau in under two seconds.

Sampled every 2 seconds through a 1,200-token generation on the 15.2 GB model:

| Time | Wired | Phase |
|---:|---:|---|
| 0 s | 2.24 GB | idle |
| 2 s | 19.26 GB | ramp complete |
| 4–16 s | 19.15 – 19.29 GB | generating |
| 18 s | 2.38 GB | released |

Flat across the whole generation — 30 MB of drift. Not a leak. But it sits at 80 % of
physical memory for the duration of every single request, and `memory_pressure` reports
the system as comfortable throughout.

The plateau runs roughly **weights + 2–3 GB** on top of whatever the OS already holds:

| Model | Prompt | Context | Wired peak | Share |
|---|---|---:|---:|---:|
| Qwen3.5-9B | repair task | 92,672 | 9.41 GB | 39 % |
| gpt-oss-20b | small | 32,768 | 14.79 GB | 62 % |
| gpt-oss-20b | large | 32,768 | 16.11 GB | 67 % |
| Devstral-Small-2-24B | small | 4,864 | 16.25 GB | 68 % |
| Qwen3.6-35B-A3B | small | 32,768 | 18.80 GB | 78 % |
| Qwen3.6-35B-A3B | large | 32,768 | 19.29 GB | 80 % |

---

## Finding 8 — You can trade the whole memory problem away, for latency

Everything above fights for headroom inside 24 GB.
[TurboFieldfare](https://github.com/drumih/turbo-fieldfare) sidesteps the fight: a Swift
and Metal runtime, neither MLX nor llama.cpp, written for exactly one model — Gemma 4
26B-A4B. It keeps a 1.35 GB core resident and **streams each token's experts off the
SSD**. That only works because the model is a mixture of experts with 4B active of 26B.

The memory claim is not marketing:

| Model · runtime | Parameters | Wired | Share | Process RSS |
|---|---:|---:|---:|---:|
| Gemma 4 26B-A4B · TurboFieldfare | 26B | **5.65 GB** | **24 %** | 1.60 GB |
| gpt-oss-20b · MLX | 21B | 16.11 GB | 67 % | 11.27 GiB |
| Qwen3.6-35B-A3B · MLX | 35B | 20.17 GB | 84 % | 14.16 GiB |

A 26-billion-parameter model at 24 % of memory. The entire band where the kernel bug from
Finding 9 lives is no longer reachable. Prompt-prefix reuse works too: 12,642 of 20,087
prompt tokens came from cache.

**And then it is too slow.** That verdict comes from actually driving it through
OpenCode, not from a benchmark: it answers, the analysis is sound, and the wait makes it
impractical for interactive work.

The trade is explicit and made on the wrong machine. On an 8 GB MacBook Air, where the
alternative is "cannot run a 26B model at all", latency for feasibility is obviously
correct. On 24 GB, where a 6 GB model fits with room to spare, you are paying latency for
memory you did not need.

> **Eleven days old, and it shows.** The repair task produced 0/6 here, but that number is
> not a capability measurement — a second model was resident for part of the series (my
> error), and *every* run hit an HTTP 500 I could not reproduce in isolation.
>
> The installer has no timeout on its HTTP range requests, so a dropped connection leaves
> it waiting silently — mine sat for 53 minutes at 44 % with 0 % CPU and no error message.
> Its `--resume` is genuinely lossless, which saves the situation, but unattended
> installation is not something to count on yet.

---

## Finding 9 — The kernel panic is an unresolved Apple bug, not MLX

Mid-session the machine went down hard:

```
panic(cpu 12 caller 0xfffffe0050784280):
"pending memory object unexpectedly found in non pending hash"
@IOGPUGroupMemory.cpp:528

Kernel Extensions in backtrace:
  com.apple.iokit.IOGPUFamily(130.13)
  com.apple.AGXG17X(351.2)

Darwin Kernel Version 25.5.0 / OS version 25F80
```

A known defect class in Apple's IOGPU kernel extension, reported repeatedly:

- [mlx-lm #883](https://github.com/ml-explore/mlx-lm/issues/883) — Qwen3-Coder-30B-A3B in
  an agentic session, KV cache growing unbounded to ~58k tokens, 80.14 GB wired of 96 GB,
  panic at `IOGPUMemory.cpp:550`. The reporter's memory-pressure monitor read *false*
  throughout. Open.
- [mlx #3186](https://github.com/ml-explore/mlx/issues/3186) — M4 Max 36 GB, reproducible
  at ~173k-token prefill. Escalated to Apple as FB22091885. Open.
- [mlx #3346](https://github.com/ml-explore/mlx/issues/3346) — M3 Ultra 96 GB, names both
  as IOGPU kext defects including a race in `IOGPUGroupMemory.cpp:219` — same file as my
  panic, different line.

> **Why this is worse than it sounds:** wired memory bypasses macOS memory-pressure
> detection, so nothing warns you before the kernel falls over. A 96 GB machine panicked
> at 83 % wired. A 15 GB model on a 24 GB machine sits at 80 % during *every* inference
> call. The only instrument that sees it is `memory_pressure | grep "wired down"`.

> **There is exactly one visible warning sign, and it is in no tool.** Late in the session
> the desktop began to **flicker** during a Qwen MoE run. Wired was at 20.17 GB — 84 %,
> the highest reading of the day and past the 83 % at which mlx-lm #883 reports its panic.
> WindowServer needs GPU memory too, and when it cannot get it, the UI stutters. If your
> desktop flickers during a generation: save and unload.

macOS 26.6 ships GPU driver fixes — CVE-2026-64691 and CVE-2026-43723. Neither names the
`IOGPUGroupMemory` race.

**What actually fed it:** not model size and not a large prefill. The agent log showed
`step=138` through `step=145`, four seconds apart and still climbing — an **endless loop
of 145+ steps**, each growing the KV cache. That loop existed because of the sampling
misconfiguration in Finding 3.

> **Do not do what I did:** I had raised `iogpu.wired_limit_mb` to 20480 and was about to
> install a LaunchDaemon to persist it. Don't. mlx-lm #883 recommends moving the wired
> limit *down* — from the ~75 % default toward 50–60 % — not up.

---

## Finding 10 — Three fixes that made things measurably worse

| Change | Intent | Success | What happened |
|---|---|---:|---|
| `tool_choice: "required"` | force a tool call | 0/3 | 8,191 tokens with *zero* reasoning tokens and empty content |
| `max_tokens: 2048` | cap runaway reasoning | 0/2 | every step hit the limit; real completions reach 2,361 |
| nudge on missing tool call | get it back on track | 0/1 | 3 nudges, 32,764 tokens, 489 s, no tool call |

The nudging result is the useful one. I assumed the model was choosing prose and could be
talked into acting. Nudging does not work — but my conclusion that the state is always
terminal was too strong. On the real task one run entered the degenerate loop, kept going,
and came out with all 22 tests green after 251 seconds. Another went in and never
returned. **Recovery is possible but not reliable; a fresh session is still the better
bet.**

The `max_tokens` one is my own misreading. I justified 2048 with measured reasoning-token
counts of 70–210 — but reasoning tokens are a subset of completion tokens, and full
completions reached 2,361.

---

## Finding 11 — Tooling behaviour that costs an hour each

### LM Studio

- **`lms get` returns exit code 0 when the download fails.** Twice — once because it
  silently lowercased a HuggingFace repo ID. Never trust the return value; check sizes.
- Model keys match by prefix. `qwen3.6-35b-a3b` is a prefix of `qwen3.6-35b-a3b-ud-mlx`,
  and with `-y` it warns "2 models match, loading the first one" and picks whichever.
  Renaming with a leading dot does not hide it — LM Studio scans dot-directories.
- The `modelLoadingGuardrails` naming is **inverted**: `mode: "high"` is the permissive
  default, `mode: "low"` is strict.
- The guardrail rejects on weights alone. A 16.08 GB model failed identically at 16,384,
  8,192 and 4,096 context with 20 GB free. "Load Anyway" exists only in the GUI.
- Context can be silently reduced at load time (Finding 4). Always check `lms ps`.
- Server logs under `~/.lmstudio/server-logs/` are where real diagnosis happens. Note that
  the counter `Done reasoning. Reasoned for N seconds` is **cumulative since server
  start**, not per request.

### OpenCode

- `permission` defaults to `ask` for `bash` and `edit`. In non-interactive `opencode run`
  this hangs forever in the foreground and **exits immediately with code 0 and an empty
  log** when stdin is not a TTY. Two contradictory-looking symptoms, one cause.
- `provider.<p>.models.<id>.temperature` is a **boolean capability flag**, not a value. A
  `0.6` there does nothing. Sampling values go in `models.<id>.options` or
  `agent.<name>.temperature` / `top_p`.
- The interactive TUI worked throughout; `opencode run` in batch mode hung in six of seven
  attempts before session creation, without a single request reaching the model server.
  Cause not found.

### HuggingFace CLI and macOS

- **Never `SIGSTOP` an `hf download`.** Xet CDN URLs are presigned; suspending lets them
  expire and resume returns 403.
- `hf download` did not resume my `.incomplete` shards — it discarded 1.5 GB.
- With `HF_HUB_ENABLE_HF_TRANSFER=1` set but the package missing, `hf` aborts immediately
  instead of falling back. The target directory sits at 4 KB and nothing says why.
- Unsloth "UD" quants are much larger than the bit width implies.
  `Qwen3.6-35B-A3B-UD-MLX-3bit` is 17.4 GB against 15.2 GB for a plain 3-bit.
- macOS has no `timeout(1)`. And `sudo softwareupdate -i -a --restart` downloaded 26.6 to
  100 %, exited 0, and installed nothing. The GUI updater worked.
- htop cannot show **per-process network** on macOS — there is no `/proc`. `nettop` and
  `bandwhich` can. More importantly: with bursty traffic any short sample shows the wrong
  thing; use windows of several minutes.

---

## Corrections

Eleven conclusions had to be retracted. They are here because the pattern transfers better
than the individual cases: a real symptom, a plausible cause, no control experiment.

| Time | Claim | What was actually true |
|---|---|---|
| 09:58 | "wired memory is running away" | ramp to a flat plateau, 30 MB drift. Aborted a valid measurement for nothing |
| 10:07 | "the output budget is too small" | a direct API call returned a clean tool call in 118 tokens |
| 10:28 | "the 3-bit quantisation is defective" | real evidence, wrong reading: it was the sampling. 1 error in 263 tool calls |
| 10:37 | "system prompt size is irrelevant" | true only under broken sampling. With it fixed, prompt size was the strongest predictor |
| 10:53 | "max_tokens 2048 is enough" | misread my own table: 70–210 were reasoning, not completion tokens |
| 11:15 | "it was the sampling" *(published)* | control against gpt-oss: 6/6 with the same broken config |
| 11:41 | "Devstral scores 0/6" | wrong twice: HTTP 400 before the first token, then my own verification logic |
| 19:00 | "Devstral is not viable on 24 GB" *(published)* | measured LM Studio, attributed to the model. MLX handles 13,728 tokens |
| 19:15 | "GGUF is unbearably slow" | three timeouts caused by my own 24,000-token prompt |
| 20:06 | "807 seconds of reasoning on one request" *(published)* | a cumulative counter. It later read 36,646 s — the server's uptime |
| 17:12 | "Gemma 4 refuses to call `write`" | an LM Studio MLX channel-format defect. Under GGUF it calls `write` and scores 5/6 |

**The pattern.** Five of the eleven were tooling behaviour mistaken for model behaviour:
backgrounding `opencode run` (EOF on stdin, instant exit 0), the permission prompt (silent
hang), my verification logic (correct code scored as failure), Devstral's context cap, and
Gemma's channel markers. Every one looked exactly like a model failing.

With a harness you wrote yourself, the first hypothesis for a surprising result should be
the harness — not the model. I reached for the model every time, because that was the
interesting answer.

The others share a different shape: measured a real effect on one model and stated it as a
general principle. The control experiment that would have caught all of them — the same
configuration against a second model — took eleven minutes when I finally ran it.

---

## What remains open

- Whether macOS 26.6 fixes the `IOGPUGroupMemory` race. The patched GPU driver CVEs are
  plausible candidates but do not name it.
- Why the Qwen MoE degrades under a long system prompt while gpt-oss does not. The *what*
  is measured; the mechanism is not.
- Whether the sliding-window models hold up at genuinely long contexts. Everything here
  ran at 32k or below; mlx #3186 reproduces its panic at ~173k prefill.
- How any of this scales past a single file. The repair task is real but small.
- Whether large tool-call arguments drive the schema-failure risk. One occurrence in 202
  is a hypothesis, not a result.
- Why `opencode run` hangs before session creation while the TUI works.

---

*All numbers measured on one machine on one day. Six runs per configuration — enough to
tell 3/6 from 6/6, not enough to tell 5/6 from 6/6.*
