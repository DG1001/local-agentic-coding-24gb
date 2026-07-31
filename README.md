# local-agentic-coding-24gb

Messungen und Werkzeuge zu der Frage, welches lokale Modell auf einem Mac mit
24 GB Unified Memory tatsächlich für agentisches Coding taugt — und woran es
scheitert, wenn es scheitert.

Sechs Modelle, 202 Toolcalls, sechs identische Läufe pro Konfiguration, gemessen
auf einem Apple M5 Pro unter macOS 26.6. Der vollständige Bericht liegt in
[`report/`](report/), die Rohzahlen in
[`results/measurements.json`](results/measurements.json).

## Das Kurzergebnis

Mit einem kurzen Systemprompt bestehen alle Modelle die Aufgabe. Was sie
trennt, ist ein realistischer Agenten-Prompt von rund 5.600 Token — die
Größenordnung, die OpenCode, aider und crush tatsächlich senden.

| Modell | Gewichte | Engine | Reparaturaufgabe | Wired |
|---|---:|---|---|---:|
| gpt-oss-20b MXFP4 | 12,08 GB | MLX | **6/6**, Median 55 s | 67 % |
| **Qwen3.5-9B 4-bit** | **5,95 GB** | MLX | **5/6**, Median 57 s | **39 %** |
| Gemma 4 12B Q4_K_M | 7,38 GB | llama.cpp | 5/6, Median 156 s | 51 % |
| Qwen3.6-35B-A3B 3-bit | 15,20 GB | MLX | 3/4, Median 177 s | 84 % |
| Devstral-Small-2-24B | 12,76 GB | llama.cpp | 2/2, Median 132 s | — |
| Gemma 4 12B MLX-4bit | 6,74 GB | MLX | **0/6** — Engine defekt | — |

Das kleinste Modell ist fast das beste: Qwen3.5-9B liegt bei halber Größe von gpt-oss
gleichauf in der Geschwindigkeit, einen Lauf hinter der Zuverlässigkeit — und braucht
39 statt 67 Prozent des Speichers.

Und bei drei von sechs Modellen entschied die **Inferenz-Engine** über Brauchbarkeit:
MLX deckelte Devstrals Kontext auf 4.864, verweigerte Qwen3.6-27B ganz und zerbrach an
Gemmas Kanal-Format. Unter llama.cpp liefen alle drei.

Und die eine Erkenntnis, die vor jedem Download Zeit spart: **die Dateigröße
ist die falsche Kennzahl.** Zwei ähnlich große Modelle können sich um den
Faktor 8 im KV-Cache-Bedarf unterscheiden. Dafür gibt es hier ein Werkzeug.

## `tools/kvcalc.py` — passt das Modell?

Liest `config.json`, zählt die Layer, die wirklich KV-Cache kosten, und rechnet
aus, was bei deinem Kontext übrig bleibt.

```bash
python3 tools/kvcalc.py mlx-community/gpt-oss-20b-MXFP4-Q8 --ram 24 --context 32768
```

```
  Attention     layer_types: 12 von 24 full-attention
  KV-Cache      24.0 KB/Token
  Gewichte      12.08 GB
  + KV @ 32768   0.81 GB
  + Overhead     2.50 GB
  = gesamt      15.38 GB von 24 GB  ->  64 %
  Bewertung     komfortabel
```

Zum Vergleich dasselbe für Devstral, das keine Sliding-Window-Layer hat:

```bash
python3 tools/kvcalc.py mistralai/Devstral-Small-2-24B-Instruct-2512 \
    --ram 24 --context 16384 --weights 14.39
```

```
  Attention     kein sliding window: alle 40 Layer kosten KV
  KV-Cache      160.0 KB/Token          ← 6,7× so viel
  = gesamt      19.57 GB von 24 GB  ->  82 %
  Bewertung     kritisch
```

Die Vorhersage traf: für gpt-oss sagt das Werkzeug 15,38 GB voraus, gemessen
wurden 16,11 GB.

Zeige immer auf das **Quant**, das du wirklich lädst, nicht auf das
Originalrepo — sonst rechnest du mit der bf16-Größe.

## Der Benchmark

Zwei Aufgaben, beide maschinell verifizierbar, beide gegen jeden
OpenAI-kompatiblen Endpunkt lauffähig.

### Reparaturaufgabe — die aussagekräftigere

Ein ISO-8601-Parser mit 22 Tests, von denen 7 fehlschlagen. Drei unabhängige
Fehler an verschiedenen Stellen: ein fehlendes Feature (Wochen-Designatoren
fehlen in Regex *und* Einheitentabelle), ein Absturz (`int()` auf Bruchzahlen)
und ein Logikfehler (Vorzeichen erfasst, aber nie angewandt).

```bash
export LLM_URL=http://127.0.0.1:1234/v1/chat/completions
python3 bench/realagent.py <model-id> /tmp/run1
```

Verifiziert wird über die Testsuite selbst. Zusätzlich prüft der Runner, ob
`test_duration.py` byte-identisch geblieben ist — die Tests zu ändern ist die
naheliegende Abkürzung, und Modelle nehmen sie.

Ausgabe als eine JSON-Zeile:

```json
RESULT {"steps": 8, "tool_calls": 7, "schema_errors": 0, "bash_calls": 6,
        "write_calls": 1, "tests_before": "15/22 passing",
        "tests_after": "22/22 passing", "all_green": true,
        "tests_untouched": true, "wall_s": 63.0}
```

### Synthetische Aufgabe — misst den Einfluss der Prompt-Größe

Dieselbe triviale Aufgabe, einmal mit Ein-Satz-Prompt und einmal mit ~5.600
Token Agenten-Instruktionen:

```bash
python3 bench/miniagent.py <model-id> /tmp/run_small small
python3 bench/miniagent.py <model-id> /tmp/run_large large
```

Das ist der Test, der die Modelle getrennt hat.

### Konfiguration

Alles über Umgebungsvariablen:

| Variable | Standard | Zweck |
|---|---|---|
| `LLM_URL` | `http://127.0.0.1:1234/v1/chat/completions` | Endpunkt |
| `MAX_TOK` | 4096 | `max_tokens` |
| `TEMP` / `TOP_P` / `TOP_K` / `REP_PEN` | 0.6 / 0.95 / 20 / 1.05 | Sampling |

`TOP_K=0` lässt `top_p`, `top_k` und `repetition_penalty` **ganz weg** — damit
reproduziert man die fehlerhafte Konfiguration, die im Bericht ein Modell
unbrauchbar machte und ein anderes gar nicht störte.

## Was das Harness absichtlich selbst tut

Es validiert Toolcall-Argumente gegen das deklarierte Schema, statt dem
Agenten-Framework zu vertrauen. Genau dafür wurde es gebaut: die Untersuchung
begann mit `SchemaError`-Meldungen aus OpenCode, und es stellte sich heraus,
dass das Framework zweimal selbst die Ursache war. Ein Harness ohne
Zwischenschicht trennt Modellverhalten von Werkzeugverhalten.

Ergebnis über die gesamte Reihe: **ein fehlerhafter Toolcall bei 202.**

## Anforderungen

Python 3.9 oder neuer, keine Abhängigkeiten außer der Standardbibliothek.
`kvcalc.py` braucht Netzzugang für HF-Modell-IDs, arbeitet aber auch mit
lokalen Pfaden.

## Struktur

```
bench/          Harness und Aufgaben
  agentlib.py     Kern: Payload-Bau, Schema-Validierung, Tool-Ausführung
  realagent.py    Reparaturaufgabe
  miniagent.py    synthetische Aufgabe, Prompt-Größen-Vergleich
  task/           der defekte ISO-8601-Parser samt Testsuite
tools/
  kvcalc.py       Speicherbedarf aus config.json
  install_supervisor.sh   Neustart-Wächter für TurboFieldfares Installer
configs/
  opencode.example.json   Provider für LM Studio und TurboFieldfare
report/           der vollständige Bericht
results/          Rohzahlen aller Messungen
```

## Grenzen dieser Messungen

Eine Maschine, ein Tag, sechs Läufe pro Konfiguration. Das reicht, um 3/6 von
6/6 zu unterscheiden, nicht um 5/6 von 6/6 zu trennen. Einzelne Lauf-Unterschiede
sind Rauschen.

Die Reparaturaufgabe ist echt, aber klein — ein Modul, drei Fehler, eine
Testsuite, die in Millisekunden läuft. Über ein Refactoring über zwanzig Dateien
sagt sie nichts.

Der Bericht enthält einen eigenen Abschnitt mit zehn Schlussfolgerungen, die
im Lauf der Untersuchung zurückgezogen werden mussten. Er steht dort, weil das
Muster übertragbarer ist als die Einzelergebnisse.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
