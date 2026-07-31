#!/usr/bin/env python3
"""kvcalc - will this model fit, and at what context?

File size is the wrong number to pick a local model by. What decides whether a
model is usable is weights + KV cache at the context you actually need, and the
KV cache depends on the attention architecture, not on the parameter count.

Two models of nearly identical size can differ by 8x in KV cost:

    Qwen3.6-35B-A3B    10 of 40 layers full-attention ->  20 KB/token
    Devstral-Small-2   40 of 40 layers full-attention -> 160 KB/token

This reads config.json (from the Hugging Face API or a local path), works out
how many layers actually cost KV cache, and tells you what fits.

Usage:
    kvcalc.py <model-id-or-path> [--ram 24] [--context 32768] [--kv-bits 16]

Examples:
    kvcalc.py openai/gpt-oss-20b
    kvcalc.py mistralai/Devstral-Small-2-24B-Instruct-2512 --context 16384
    kvcalc.py ~/.lmstudio/models/some/local-model --ram 16 --kv-bits 8

MIT licensed. Part of local-agentic-coding-24gb.
"""

import argparse, json, os, sys, urllib.request

API = "https://huggingface.co/api/models/{}"
RAW = "https://huggingface.co/{}/raw/main/config.json"

# Measured across four models on a 24 GB M5 Pro: the wired plateau sits roughly
# 2-3 GB above weights plus KV cache (Metal scratch, expert buffers, runtime).
# A planning allowance, not an exact figure.
RUNTIME_OVERHEAD_GB = 2.5


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "kvcalc/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def load_config(target):
    """Accepts a HF model ID or a local path."""
    local = os.path.expanduser(target)
    for cand in (local, os.path.join(local, "config.json")):
        if os.path.isfile(cand):
            return json.load(open(cand)), None
    cfg = fetch_json(RAW.format(target))
    weights = None
    try:
        meta = fetch_json(API.format(target) + "?blobs=true")
        tot = sum(f.get("size") or 0 for f in meta.get("siblings", [])
                  if f["rfilename"].endswith((".safetensors", ".gguf")))
        weights = tot / 1e9 if tot else None
    except Exception:
        pass
    return cfg, weights


def analyse(cfg):
    """Extracts the KV-relevant parameters. Handles nested text_config
    (mistral3, gemma3) and sliding-window architectures."""
    t = cfg.get("text_config", cfg)
    n = t.get("num_hidden_layers")
    kv = t.get("num_key_value_heads") or t.get("num_attention_heads")
    hd = t.get("head_dim")
    if not hd and t.get("hidden_size") and t.get("num_attention_heads"):
        hd = t["hidden_size"] // t["num_attention_heads"]

    layer_types = t.get("layer_types")
    sliding = t.get("sliding_window")
    if layer_types:
        full = sum(1 for x in layer_types if "full" in str(x).lower())
        how = f"layer_types: {full} of {n} full-attention"
    elif sliding and t.get("sliding_window_pattern"):
        p = t["sliding_window_pattern"]
        full = max(1, n // p)
        how = f"sliding_window_pattern {p}: ~{full} of {n} full-attention"
    elif sliding:
        full = n
        how = f"sliding_window={sliding}, no pattern declared -> conservatively counted all {n}"
    else:
        full = n
        how = f"no sliding window: all {n} layers cost KV"

    experts = t.get("num_local_experts") or t.get("num_experts")
    active = t.get("num_experts_per_tok")
    return {"layers": n, "full": full, "kv_heads": kv, "head_dim": hd,
            "how": how, "model_type": cfg.get("model_type") or t.get("model_type"),
            "max_pos": t.get("max_position_embeddings"),
            "experts": experts, "active_experts": active}


def main():
    ap = argparse.ArgumentParser(description="Will this model fit, and at what context?")
    ap.add_argument("model", help="HF model ID or local path")
    ap.add_argument("--ram", type=float, default=24.0, help="available RAM in GB (default 24)")
    ap.add_argument("--context", type=int, default=32768, help="required context (default 32768)")
    ap.add_argument("--weights", type=float, help="weights size in GB, if not derivable")
    ap.add_argument("--kv-bits", type=int, default=16, choices=[16, 8, 4],
                    help="KV quantisation; llama.cpp supports 8 or 4, MLX via --kv-bits")
    a = ap.parse_args()

    try:
        cfg, weights = load_config(a.model)
    except Exception as e:
        sys.exit(f"cannot read config.json: {type(e).__name__}: {e}")
    if a.weights:
        weights = a.weights

    d = analyse(cfg)
    if not all((d["layers"], d["kv_heads"], d["head_dim"])):
        sys.exit(f"incomplete config: {d}")

    kv_per_tok = d["full"] * d["kv_heads"] * d["head_dim"] * 2 * (a.kv_bits / 8)
    kv_gb = kv_per_tok * a.context / 1e9

    print(f"\n{a.model}")
    print(f"  Type          {d['model_type']}"
          + (f"  |  MoE: {d['experts']} experts, {d['active_experts']} active" if d["experts"] else "  |  dense"))
    print(f"  Attention     {d['how']}")
    print(f"  KV geometry   {d['kv_heads']} KV heads x head_dim {d['head_dim']}"
          + (f"  |  {a.kv_bits}-bit KV" if a.kv_bits != 16 else ""))
    if d["max_pos"]:
        print(f"  max context   {d['max_pos']:,}")

    print(f"\n  KV cache      {kv_per_tok/1024:.1f} KB/token")
    for c in (4096, 8192, 16384, 32768, 65536):
        mark = "  <-- requested" if c == a.context else ""
        print(f"    {c:>6,} tokens -> {kv_per_tok*c/1e9:5.2f} GB{mark}")

    if weights:
        total = weights + kv_gb + RUNTIME_OVERHEAD_GB
        pct = total / a.ram * 100
        print(f"\n  Weights       {weights:.2f} GB")
        print(f"  + KV @ {a.context}  {kv_gb:.2f} GB")
        print(f"  + overhead    {RUNTIME_OVERHEAD_GB:.2f} GB (measured allowance)")
        print(f"  = total       {total:.2f} GB of {a.ram:.0f} GB  ->  {pct:.0f} %")
        if pct < 70:
            print("\n  Verdict       comfortable")
        elif pct < 80:
            print("\n  Verdict       tight but workable")
        else:
            print("\n  Verdict       critical. On Apple Silicon this is the band where the")
            print("                IOGPU kernel bug strikes (mlx-lm #883).")
            print("                Choose a smaller context or a smaller quantisation.")
        if kv_gb > weights * 0.25 and a.kv_bits == 16:
            print("\n  Note          The KV cache is a substantial item here.")
            print("                --kv-bits 8 halves it (llama.cpp, or mlx-lm --kv-bits).")
        print("\n  Careful       Weights size comes from the repo you named. Point at the")
        print("                quantisation you actually load (e.g. mlx-community/...-4bit),")
        print("                not the original - otherwise you compute with bf16 sizes.")
    else:
        print("\n  Weights size not derivable - supply it with --weights <GB>.")
    print()


if __name__ == "__main__":
    main()
