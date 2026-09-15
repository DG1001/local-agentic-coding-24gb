#!/usr/bin/env python3
"""Native mlx_lm counterpart to edge0's own examples/bench.py.

Same checkpoint, same MLX build, same prompt, same measurement shape --
the only difference is that the experts are resident instead of streamed.
That is the comparison edge0's README does not publish.

Caveat worth stating in any writeup: mlx_lm loads the base int4 weights
only.  The Recover-LoRA and prerouter adapters are edge0-specific and are
NOT applied here, so this is a speed/memory control, not a quality one.

Usage:
Run it from a checkout of Edge0-AI/Edge0, inside that project's venv --
it imports the prompts from examples/bench.py so both sides measure the
same thing:

    cp edge0_native_bench.py ~/path/to/Edge0/
    BENCH_LONG=1 .venv/bin/python edge0_native_bench.py models/edge0-35b
"""
import argparse, os, sys, time

import mlx.core as mx
from mlx_lm import load, stream_generate
from mlx_lm.sample_utils import make_sampler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "examples"))
from bench import _long_prompt, DEFAULT_PROMPT, PROMPTS  # same prompts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--ntok", type=int, default=200)
    ap.add_argument("--warmup", type=int, default=10)
    ap.add_argument("--runs", type=int, default=2)
    a = ap.parse_args()

    prompt = (os.environ.get("BENCH_PROMPT") or
              (_long_prompt() if os.environ.get("BENCH_LONG") == "1"
               else PROMPTS.get("edge0-35b", DEFAULT_PROMPT)))

    t0 = time.perf_counter()
    model, tok = load(a.model)
    print(f"[native] load {time.perf_counter()-t0:.1f}s", flush=True)

    # examples/bench.py samples a fixed ntok and never checks for EOS, so the
    # native run must not stop early either -- otherwise the timed windows
    # differ in length and the tok/s are not comparable.
    tok.eos_token_ids = set()

    text = tok.apply_chat_template([{"role": "user", "content": prompt}],
                                   tokenize=False, add_generation_prompt=True,
                                   enable_thinking=False)
    ids = tok.encode(text)
    sampler = make_sampler(temp=float(os.environ.get("BENCH_TEMP", 0.7)),
                           top_p=0.95, top_k=64)

    results = []
    for _ in range(a.runs):
        mx.clear_cache()
        mx.reset_peak_memory()
        n, t_decode, t_prefill = 0, 0.0, None
        start = time.perf_counter()
        for i, r in enumerate(stream_generate(
                model, tok, ids, max_tokens=a.warmup + a.ntok,
                sampler=sampler)):
            if i == 0:
                t_prefill = time.perf_counter() - start
            if i == a.warmup:          # timed window opens after warmup
                t_decode = time.perf_counter()
            if i >= a.warmup:
                n += 1
        t_decode = time.perf_counter() - t_decode
        peak = mx.get_peak_memory() / (1024 ** 3)
        tps = n / t_decode if t_decode else 0.0
        pf = len(ids) / t_prefill if t_prefill else 0.0
        results.append((tps, peak))
        print(f"prompt={len(ids)} tok  prefill={t_prefill:.2f}s ({pf:.0f} tok/s)"
              f"  decode={n}/{t_decode:.2f}s  tok/s={tps:.1f}"
              f"  peak_active={peak:.2f} GiB", flush=True)

    mean = sum(r[0] for r in results) / len(results)
    print(f"[native] mean tok/s={mean:.1f}  "
          f"peak_active<={max(r[1] for r in results):.2f} GiB", flush=True)


if __name__ == "__main__":
    main()
