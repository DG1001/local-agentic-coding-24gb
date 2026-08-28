# Local agentic coding on a 24 GB Mac: the system prompt is the benchmark

*Field notes — Apple M5 Pro, 24 GB, macOS 26.6 (25G72), LM Studio 0.4.20, OpenCode 1.18.9*

Eight models, 350 tool calls, six identical runs per configuration. Every model aced the
task in isolation. What separated them was a five-thousand-token system prompt — the
thing every real coding agent sends. Along the way: one kernel panic, a flickering
desktop as the only warning macOS ever gave, and thirteen confident conclusions I had to
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
| Qwen3.8-27B IQ4_XS | 14.25 GB | llama.cpp | **6/6** | 212 s | 0/39 | 17.4 GB · 73 % |
| **Qwen3.5-9B 4-bit** | **5.95 GB** | MLX | **5/6** | **57 s** | 0/28 | **9.4 GB · 39 %** |
| Nanbeige4.2-3B Q4_K_M | **2.68 GB** | llama.cpp ¹ | 5/6 | 62 s | 0/42 | 11.3 GB · 47 % |
| Gemma 4 12B Q4_K_M | 7.38 GB | llama.cpp | 5/6 | 156 s | 0/30 | 12.3 GB · 51 % |
| Devstral-Small-2-24B IQ4_XS | 12.76 GB | llama.cpp | 2/2 | 132 s | 0/12 | — |
| Qwen3.6-35B-A3B 3-bit | 15.20 GB | MLX | 3/4 | 177 s | 0/31 | **20.2 GB · 84 %** |
| **Qwen3.6-35B-A3B 3-bit, no thinking** | 15.20 GB | mlx_lm.server | **6/6** | **32 s** | 0/48 | 17.4 GB · 73 % |
| Gemma 4 12B MLX-4bit | 6.74 GB | MLX | **0/6** | — | 0/16 | engine defect, see Finding 6 |

¹ Upstream llama.cpp only — LM Studio's bundled runtimes cannot load it at all. See Finding 6.

The Qwen MoE is the slowest *with its reasoning block* despite activating only 3B of its
35B parameters — its failures are expensive, and its one bad run burned 8,211 reasoning
tokens going nowhere. Remove the reasoning block and the same weights become the fastest
entry in the table; see below.

Variance is substantial: gpt-oss run 5 finished in 4 tool calls and 556 reasoning tokens,
run 4 needed 2,605. A factor of 4.7 on an identical task. Single runs tell you little.

The same effect appears at a larger scale in the 128 GB study, where it is named the
*agentic multiplier*: between two models whose token rates differ 7× (4.5 vs 30.4 tok/s),
actual task completion differed **20×** — 1,788 s against 90 s on the same bug hunt. Model
behaviour amplifies hardware differences. Our own numbers show the shape of it: the Qwen
MoE was the slowest model in the set despite activating only 3B of 35B parameters, because
its failures were expensive — and it became the fastest once the reasoning block was
removed, at 5.4× the same weights' own median. The multiplier is in the behaviour, not
the parameter count.

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

### Turning off reasoning turns the slowest model into the fastest

*(This section previously concluded the opposite. The retraction is below.)*

An obvious idea, since Devstral solves this task with `reasoning_tokens: 0`: disable
thinking on the Qwen MoE and skip the loop entirely. The first attempt did that by putting
`/no_think` in the user message, and the model stopped calling tools and rambled to the
token limit. Conclusion at the time: the reasoning is load-bearing for tool use.

That conclusion was wrong, and the template says why. **`Qwen3.6-35B-A3B` has no `/no_think`
handling at all.** Its chat template branches on exactly one thing:

```jinja
{%- if enable_thinking is defined and enable_thinking is false %}
    {{- '<think>\n\n</think>\n\n' }}
{%- else %}
    {{- '<think>\n' }}
{%- endif %}
```

`/no_think` in the message body is just a stray token in the prompt. The template still
opens `<think>` as prefill, so the model sits in thinking mode while being told not to
think — which is what the rambling was. Setting `enable_thinking: false` emits a *closed,
empty* block instead, and the model starts in ordinary output mode.

Getting that argument to the template is the whole difficulty. LM Studio discards
`chat_template_kwargs` without a word, and llama.cpp — which does accept
`--chat-template-kwargs` — cannot load MLX weights. The route that works is
`mlx_lm.server` (0.31.3; 0.29.1 does not know the `qwen3_5_moe` architecture):

```sh
mlx_lm.server --model <path> --port 8890 \
    --chat-template-args '{"enable_thinking":false}' \
    --prompt-cache-size 1 --prompt-cache-bytes 2GB
```

Same model, same 3-bit quant, same task, same harness — only the reasoning block removed:

| | thinking on | thinking off |
|---|---:|---:|
| Verified | 3/4 | **6/6** |
| Median | 176.8 s | **32.5 s** |
| Range | 51.8–251.0 s | 20.5–73.0 s |
| Steps | 2–14 | 6–13 |
| Reasoning tokens | 864–8,211 | 0 |
| Schema errors | 0/31 | 0/48 |
| Wired peak | 20.2 GB · 84 % | 17.4 GB · 73 % |

**A factor of 5.4 on the median, and it goes from the slowest model in the set to the
fastest.** The step count barely moved — the time was in the reasoning tokens, not in
extra turns. The single red run under thinking is the clearest evidence: two steps, 8,211
reasoning tokens, then a token-ID-0 loop. That failure mode cannot occur without a
reasoning block.

The generalisation from the first attempt — "Qwen3.6 needs its reasoning for tool use" —
was drawn from a mechanism that never disabled reasoning in the first place. What it
actually measured was a model given contradictory instructions.

---

## Finding 2 — One malformed tool call in 302

The question that started this investigation was whether 3-bit quantisation was
corrupting tool arguments. Across the whole study — six models, three prompt sizes, two
sampling regimes, plus the repair task — **350 tool calls produced exactly one schema
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

> **On other hardware the wrong number is a different one.** A
> [companion study on a 128 GB DGX-Spark-class box](https://github.com/DG1001/local-agentic-coding-128gb)
> (NVIDIA GB10, ~273 GB/s) reaches the same conclusion from the opposite direction: there
> memory is never the constraint, **bandwidth** is, and the number to select on is *active*
> parameters. A dense Qwen3.6-27B runs at 4.5 tok/s while a MoE with ~3B active does 30.4 —
> at 96 % GPU utilisation and 43.6 W, i.e. the compute units idling on memory.
>
> Both studies land on the same warning and a different remedy: file size tells you
> nothing. At 24 GB compute **weights + KV at your context**; on bandwidth-bound hardware
> count **active parameters**.

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

### The counter-test: a dense 27B that also scores 6/6

`Qwen3.8-27B` (released 14 August 2026) is the strongest case against that conclusion,
and it loses on time. In `unsloth`'s `UD-IQ4_XS` quantisation it is 14.25 GB, loads with
16,384 tokens of context at **73 % wired**, and returns **6/6 with zero schema errors in
39 tool calls** — the second model in this series to match gpt-oss's perfect score, and it
does so more consistently: 5 to 7 steps every run, where gpt-oss ranged from 5 to 10.

It is also **four times slower**: a 212 s median against gpt-oss's 55 s, for an identical
result. That gap is architectural, not incidental. gpt-oss is a mixture-of-experts and
activates a fraction of its parameters per token; a dense 27B computes all of them. The
[128 GB companion study](https://github.com/DG1001/local-agentic-coding-128gb) measured
the same shape on entirely different hardware — a dense 27B there scored a perfect 86/86
and needed 3 h 07 m at 4.5 tok/s, against minutes for MoE models of comparable quality.
**Pick by active parameters, not by total parameters**, and the rule holds at both ends of
the memory range.

Two practical notes for this model specifically. Unsloth's "runs well on a 24 GB Mac"
applies to `UD-IQ4_XS` and below — `UD-Q4_K_M` (16.46 GB) and the MLX 4-bit build
(16.05 GB) project to 83–88 %, the same band in which LM Studio's guardrail refused
Qwen3.6-27B outright. And `lms load` defaults `PARALLEL` to **4**: without an explicit
`--parallel 1`, the 1.07 GB KV cache is held four times over and the same configuration
lands at 88 % instead of 73 %.

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

## Finding 7 — Seventeen tools break what two tools solve

Everything so far compares models and engines. This one compares **agent configuration**,
and it turned out to matter more than either.

[Hermes Agent](https://github.com/NousResearch/hermes-agent) is a general-purpose agent,
not a coding agent — the local-model equivalent of what OpenClaw does. Same repair task,
same models, same LM Studio endpoint. The only variable is how many toolsets are enabled.

| Configuration | Model | Result |
|---|---|---|
| Hermes default, 17 toolsets | Qwen3.5-9B | **failed** — 4/22 passing, 35 steps, never terminated in 15 min |
| Hermes default, 17 toolsets | gpt-oss-20b | **failed** — file left with a `SyntaxError` after 7 min |
| **Hermes, `-t terminal,file`** | gpt-oss-20b | **22/22 in 2:28**, tests untouched |
| Hermes, `-t terminal,file` | Qwen3.5-9B | **failed** — 6/22 after 15.5 min |

The same gpt-oss that scores 6/6 on this task through a two-tool harness cannot finish it
through a seventeen-tool one. Cutting the toolsets fixed it outright.

**But it did not fix Qwen3.5-9B**, and that bounds the finding. With two toolsets the 9B
came within two failing tests after eight minutes — then diverged again, ending at 16.
Memory was never the constraint: it peaked at 11.55 GB, 48 %.

So tool width explains the 21B model's behaviour, not the 9B's. Note that the same 9B
solves this task 5/6 through my own two-tool harness with terse schemas. Hermes'
`terminal` and `file` toolsets still bundle several functions each and ship a much larger
system prompt than two hand-written schemas. Reducing the surface helps; it does not turn
a 9B into a 21B.

The reason is visible in the tool list Hermes sends with every request:

| To do this | it offers |
|---|---|
| read a file | `read`, `read_file` |
| modify a file | `write`, `write_file`, `patch`, `edit` |
| run a command | `bash`, `terminal`, `execute_code` |
| search | `grep`, `search_files`, `glob` |

Four ways to edit a file and three to run a command, every step, for a model that has to
pick correctly each time. Prompt size is not the issue — Hermes' largest request measured
~5,120 tokens, and Qwen3.5-9B handles 5,600 tokens of system prompt at 6/6. It is the
width of the choice.

**This is the practically most consequential finding here for anyone running a
general-purpose agent locally.** It also explains why Hermes' own documentation recommends
70B-class models: not because smaller ones are too weak at the task, but because the
default configuration demands a breadth of tool selection that only large models handle
reliably. Reduce the surface and a 21B model does the job in under three minutes.

The practical consequence for 24 GB: **a local general-purpose agent costs a 21B-class
model at ~67 % of memory**, not the 39 % a 9B would have needed. The headroom the small
model buys you holds for a coding agent like OpenCode — not for this.

> **One caveat on rigour:** these are single runs per configuration, not six. The gpt-oss
> contrast — fails at 17 toolsets, 22/22 at two — is large enough that the direction is not
> in doubt. The Qwen3.5-9B result is a single failed run and should be read as such.

### A related trap: PARALLEL multiplies your KV cache

While setting this up I raised gpt-oss to 65,536 context because Hermes asks for at least
64K — and the desktop started flickering again. Wired had reached **18.75 GB (78 %)**.

**But seven tools are not seventeen.** Finding 13 runs the same task through three
harnesses at two, six and seven tools and finds no penalty at any of them — so read this
finding as being about *seventeen*, not about "more than two".

LM Studio defaults to `PARALLEL 4`, and it holds the KV cache **per slot**. What should
have been 1.57 GB of cache became up to 6.3 GB. With `--parallel 1` the identical context
peaked at 17.47 GB (73 %) and ran fine. For a single agent, one slot is all you need — and
the `PARALLEL` column has been sitting in every `lms ps` output all along.

---

## Finding 8 — Wired memory is a step function, and pressure monitoring cannot see it

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

## Finding 9 — You can trade the whole memory problem away, for latency

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
Finding 10 lives is no longer reachable. Prompt-prefix reuse works too: 12,642 of 20,087
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

## Finding 10 — The kernel panic is an unresolved Apple bug, not MLX

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

## Finding 11 — Three fixes that made things measurably worse

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

## Finding 12 — Tooling behaviour that costs an hour each

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

### mlx_lm.server

- **`--prompt-cache-size` defaults to 10 — that is ten complete KV caches held at once.**
  Every step of an agent run has a different prefix, so the server allocates a new cache per
  step and keeps them all. Step eleven dies with `[METAL] Command buffer execution failed:
  Insufficient Memory`. Short runs pass, long runs fail — which reads exactly like an
  unstable model until you find it. There is **no default byte ceiling**; set
  `--prompt-cache-size 1 --prompt-cache-bytes 2GB` for agent work.
- After that OOM the server process stays alive and the client hangs indefinitely — a
  `REQ_TIMEOUT` on the request never fired. Watch the server log, not the client.
- It is the only one of the three runtimes that passes `enable_thinking` to the template
  (`--chat-template-args`). LM Studio drops it; llama.cpp accepts the equivalent flag but
  cannot load MLX weights. For an MLX reasoning model this server is the only route.
- Version matters: 0.29.1 does not know the `qwen3_5_moe` architecture and refuses to load.
  0.31.3 does. LM Studio ships its own newer MLX engine, so a model that loads in the GUI
  can still be unloadable by the `mlx_lm` in your `PATH`.

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

## Finding 13 — The tool count is not the cost. The turn count is.

Finding 7 leaves an obvious hole: all the model numbers above come from a two-tool
harness, while a real agent offers more. So the same repair task was run through
**OpenCode 1.18.15** with six tools live — `bash, edit, glob, grep, read, write` — against
Qwen3.8-27B. The result is not what Finding 7 predicts.

| | Harness, 2 tools | OpenCode, 6 tools | [jaja](https://github.com/DG1001/jaja), 7 tools |
|---|---:|---:|---:|
| System prompt | ~5,600 tok | 5,199 tok | **~150 tok** |
| Wall-clock | 212 s median | **201 s** | 237 s |
| Turns | 5–7 | 6 | 10 |
| Tool calls | 6 | 6 | 11 |
| Tool errors | 0 | 0 | 0 |
| Result | 22/22 | 22/22 | 22/22 |

**Two, six and seven tools give 212, 201 and 237 seconds.** That is noise, not a trend.
Seventeen toolsets broke every model tested; seven cost nothing measurable. Whatever
breaks at seventeen is not a gentle slope starting at three.

The third harness is the one that settles it. `jaja` offers *more* tools than OpenCode and
a system prompt **thirty-five times shorter** — a few lines of German against 5,199
tokens. It should have won on prefill alone. It came last, and its own output says why:

```
Token: 50147 Eingabe, 2461 Ausgabe
```

**50,147 input tokens for eleven tool calls.** The short prompt saves a few thousand
tokens per turn, but jaja takes ten turns where OpenCode takes six, and every turn resends
the entire history. **Turn count beats prompt size.** The extra turns are visible in the
trace and they are not mistakes — it reads the two files separately, verifies with `diff`
that the test file is untouched, splits three edits across two turns, and re-reads after
the first test run. More careful, and more expensive.

For a dense model this is the number that matters. Every turn pushes the whole context
through all 27B parameters again. A harness that reaches the same answer in six turns
instead of ten is 40 % cheaper before a single token of its system prompt is counted.

But the first attempt at this run looked like a catastrophe: four automatic compactions,
an `edit` failing with *"Could not find oldString in the file"*, a `read` aborting, and
the task limping to completion across eleven hours. The cause was one number in my own
config. OpenCode decides when to compact like this:

```js
Math.max(0, limit.context - maxOutputTokens(model, outputTokenMax))
```

**`output` is not a cap on the answer. It is subtracted from the working context.** With
`context: 16384, output: 8192` the compaction threshold is **8,192 tokens** — and
OpenCode's own system prompt is 5,199 of them. The model had roughly three thousand
tokens of room before its history was folded up. The failing `edit` follows directly:
after compaction it no longer knew the file's current state.

Changed to `context: 24576, output: 4096`, the threshold becomes 20,480, the prompt grows
5,199 → 9,160 across the run, and **nothing compacts at all**.

Worth knowing when reading the per-step timings:

```
16:06:47   72.8 s   prompt  5199    71 prompt-tok/s   <- cold
16:07:59   64.1 s   prompt  7544   118
16:09:03   18.4 s   prompt  8200   445
16:09:22   14.6 s   prompt  8421   577
16:09:37   14.5 s   prompt  8656   599
16:09:51   16.3 s   prompt  9160   562
```

The first call costs 72.8 s, every later one 14–18 s. Prompt throughput rises eightfold
because llama.cpp reuses the KV prefix — **even though `cache.read` and `cache.write` are
reported as 0 in every single message**. LM Studio does not report prefix reuse over the
OpenAI-compatible API. Do not conclude from those zeroes that caching is off, and do not
judge a dense model's latency by its first request.

Wired peaked at 17.99 GB (75 %), against 17.82 GB predicted by `tools/kvcalc.py`.

---

## Corrections

Fourteen conclusions had to be retracted. They are here because the pattern transfers better
than the individual cases: a real symptom, a plausible cause, no control experiment.

| Time | Claim | What was actually true |
|---|---|---|
| 09:58 | "wired memory is running away" | ramp to a flat plateau, 30 MB drift. Aborted a valid measurement for nothing |
| 10:07 | "the output budget is too small" | a direct API call returned a clean tool call in 118 tokens |
| 10:28 | "the 3-bit quantisation is defective" | real evidence, wrong reading: it was the sampling. 1 error in 350 tool calls |
| 10:37 | "system prompt size is irrelevant" | true only under broken sampling. With it fixed, prompt size was the strongest predictor |
| 10:53 | "max_tokens 2048 is enough" | misread my own table: 70–210 were reasoning, not completion tokens |
| 11:15 | "it was the sampling" *(published)* | control against gpt-oss: 6/6 with the same broken config |
| 11:41 | "Devstral scores 0/6" | wrong twice: HTTP 400 before the first token, then my own verification logic |
| 19:00 | "Devstral is not viable on 24 GB" *(published)* | measured LM Studio, attributed to the model. MLX handles 13,728 tokens |
| 19:15 | "GGUF is unbearably slow" | three timeouts caused by my own 24,000-token prompt |
| 20:06 | "807 seconds of reasoning on one request" *(published)* | a cumulative counter. It later read 36,646 s — the server's uptime |
| 17:12 | "Gemma 4 refuses to call `write`" | an LM Studio MLX channel-format defect. Under GGUF it calls `write` and scores 5/6 |
| 14:20 | "the user had to nudge it four times" | the "Continue if…" messages are OpenCode's own, flagged `synthetic: true, compaction_continue: true`. The run *was* autonomous |
| 14:35 | "there is no prefix caching — `cache.read` is 0" | a reporting gap. Prompt throughput rises 71 → 599 tok/s across the run; llama.cpp reuses the prefix, LM Studio just does not say so |
| 21:05 | "Qwen3.6 needs its reasoning block for tool use" *(published)* | `/no_think` is not in that model's chat template at all. The template still opened `<think>`, so the model was told not to think while sitting in thinking mode. With `enable_thinking: false` it goes 6/6 at a 5.4× faster median |

**The pattern.** Eight of the fourteen were tooling behaviour mistaken for model behaviour:
backgrounding `opencode run` (EOF on stdin, instant exit 0), the permission prompt (silent
hang), my verification logic (correct code scored as failure), Devstral's context cap,
Gemma's channel markers, and a chat template that ignored the switch I was setting. Every
one looked exactly like a model failing.

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
- Where between seven and seventeen tools the agent surface starts to cost something.
  Seven is free on a 27B; seventeen breaks everything. The curve in between is unmeasured.
- Whether turn count is reducible by prompting. jaja's extra four turns look like caution,
  not confusion — but nobody measured whether telling it to batch edits would help.

---

*All numbers measured on one machine on one day. Six runs per configuration — enough to
tell 3/6 from 6/6, not enough to tell 5/6 from 6/6.*
