# Lokales agentisches Coding auf einem 24-GB-Mac: der Systemprompt ist der Benchmark

*Feldnotizen — Apple M5 Pro, 24 GB, macOS 26.6 (25G72), LM Studio 0.4.20, OpenCode 1.18.9*

Sechs Modelle, 202 Toolcalls, sechs identische Läufe pro Konfiguration. Jedes Modell
löste die Aufgabe isoliert. Getrennt hat sie ein Systemprompt von fünftausend Token —
das, was jeder echte Coding-Agent mitschickt. Unterwegs: ein Kernel-Panic, ein
flackernder Bildschirm als einzige Warnung, die macOS je gab, und zehn Schlussfolgerungen,
die ich zurückziehen musste.

> Die formatierte Fassung mit interaktivem Diagramm liegt in [`report.html`](report.html).
> Rohzahlen: [`../results/measurements.json`](../results/measurements.json).

---

## Das Ergebnis

Aufgabe durchgehend identisch: `greet.py` mit einer `greet(name)`-Funktion schreiben, mit
`python3` ausführen, Ausgabe verifizieren, bei Fehler korrigieren. Zwei Werkzeuge,
`bash` und `write`. Sechs Läufe pro Konfiguration, Erfolg gemessen, indem die
entstandene Datei importiert und die Funktion aufgerufen wird.

Die einzige Variable, die zählte, war die Menge Systemprompt davor.

| Modell | Auf Platte | Kurzer Prompt | Agenten-Prompt | + kaputtes Sampling |
|---|---:|---:|---:|---:|
| gpt-oss-20b MXFP4 | 12,08 GB | 6/6 | **6/6** | **6/6** |
| Qwen3.5-9B 4-bit | 5,95 GB | — | — | — |
| Devstral-Small-2-24B MXFP4 | 14,39 GB | 6/6 | passt nicht | — |
| Qwen3.6-35B-A3B MLX 3-bit | 15,20 GB | 6/6 | 3/6 | 0/6 |

„Kurz" ist ein Ein-Satz-Systemprompt (245 Prompt-Token), „Agenten-Prompt" sind rund
5.600 Token plausibler Instruktionen — die Größenordnung, die OpenCode, aider und crush
tatsächlich senden.

Liest man nur die erste Spalte, sieht jedes Modell brauchbar aus: 9 bis 12 Sekunden pro
Aufgabe, kein einziger fehlerhafter Toolcall, nichts zu entscheiden. Liest man die
letzten beiden, steht nur noch gpt-oss.

**Deshalb sind „läuft bei mir"-Berichte über lokale Coding-Modelle so unzuverlässig.**
Ein schneller Handtest nutzt einen kurzen Prompt. Ein Agent nicht.

### Die Konfiguration, falls du nur die willst

```
model              gpt-oss-20b MXFP4        (12,08 GB)
context            32768
temperature        0.6      // siehe Befund 3 — möglicherweise egal
top_p              0.95
top_k              20
repetition_penalty 1.05
tool_choice        "auto"   // NIEMALS "required"
max_tokens         8192     // Completions erreichen ~2400
iogpu.wired_limit_mb  auf 0 lassen
```

Gemessen: 6/6 unter realistischem Agenten-Prompt, Median 16,4 s, 16,11 GB Wired (67 %),
lädt in 6,1 Sekunden. End-to-end in OpenCodes interaktiver TUI bestätigt, die daraus eine
funktionierende Todo-App aus drei Dateien gebaut hat.

---

## Befund 1 — Es trägt auch bei echter Arbeit

Alles bisherige nutzt eine bewusst winzige Aufgabe, was weniger beweist, als es aussieht.
Der letzte Test war deshalb eine kleine, aber echte Reparatur: ein bestehendes
ISO-8601-Modul mit 100 Zeilen und einer 22-Test-Suite, sieben davon rot, verursacht durch
**drei unabhängige Fehler** an verschiedenen Stellen — ein fehlendes Feature
(Wochen-Designatoren fehlen in Regex *und* Einheitentabelle), ein Absturz (`int()` auf
Bruchzahlen) und ein Logikfehler (Vorzeichen erfasst, nie angewandt). Auftrag: Suite grün
bekommen, Tests nicht anfassen.

| Lauf | Schritte | bash | write | Schema-Fehler | Reasoning | Ergebnis | Dauer |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10 | 7 | 2 | 1 | 1.548 | 22/22 | 63,7 s |
| 2 | 9 | 7 | 1 | 0 | 1.967 | 22/22 | 53,9 s |
| 3 | 7 | 5 | 1 | 0 | 719 | 22/22 | 37,1 s |
| 4 | 8 | 6 | 1 | 0 | 2.605 | 22/22 | 63,0 s |
| 5 | 5 | 3 | 1 | 0 | 556 | 22/22 | 27,8 s |
| 6 | 8 | 6 | 1 | 0 | 2.131 | 22/22 | 56,0 s |

**Sechs von sechs, Median 55 Sekunden.** Alle drei Fehler jedes Mal in einem Durchgang
gefunden. Die Tests blieben unverändert — was ausdrücklich geprüft wird, weil die
Testsuite zu ändern die naheliegende Abkürzung ist und Modelle sie nehmen.

Der Patch liest sich wie von Hand geschrieben: die Wochengruppe an der grammatisch
richtigen Stelle eingefügt (vor dem `T`-Trenner, wo ISO-8601 sie vorsieht), `int()` zu
`float()` geändert **und** der Akkumulator auf `0.0` initialisiert — der zweite Teil ist
der, den man leicht übersieht — plus vier Zeilen für das Vorzeichen nach der Summenbildung.
Keine erfundenen Features, keine überflüssigen Umbauten.

Dieselbe Aufgabe für die anderen Modelle:

| Modell | Gewichte | Engine | Erfolg | Median | Schema-Fehler | Wired |
|---|---:|---|---:|---:|---:|---:|
| gpt-oss-20b MXFP4 | 12,08 GB | MLX | **6/6** | 55 s | 1/41 | 16,1 GB · 67 % |
| **Qwen3.5-9B 4-bit** | **5,95 GB** | MLX | **5/6** | **57 s** | 0/28 | **9,4 GB · 39 %** |
| Gemma 4 12B Q4_K_M | 7,38 GB | llama.cpp | 5/6 | 156 s | 0/30 | 12,3 GB · 51 % |
| Devstral-Small-2-24B IQ4_XS | 12,76 GB | llama.cpp | 2/2 | 132 s | 0/12 | — |
| Qwen3.6-35B-A3B 3-bit | 15,20 GB | MLX | 3/4 | 177 s | 0/31 | **20,2 GB · 84 %** |
| Gemma 4 12B MLX-4bit | 6,74 GB | **MLX** | **0/6** | — | 0/16 | Engine defekt, s. Befund 5 |

gpt-oss gewinnt auf allen drei Achsen zugleich: zuverlässiger, dreimal schneller, 17
Prozentpunkte mehr Speicherreserve. Das Qwen-MoE ist trotz nur 3B aktiver von 35B
Parametern das langsamste — seine Fehlschläge sind teuer, ein schlechter Lauf verbrannte
8.211 Reasoning-Tokens ohne Ergebnis.

Die Streuung ist erheblich: Lauf 5 kam mit 4 Toolcalls und 556 Reasoning-Tokens aus,
Lauf 4 brauchte 2.605. Faktor 4,7 bei identischer Aufgabe. Einzelne Läufe sagen wenig.

### Das kleinste Modell gewinnt fast

Qwen3.5-9B ist das überraschendste Ergebnis der Reihe. Bei **halber Gewichtsgröße** von
gpt-oss liegt es bei gleicher Geschwindigkeit, einen Lauf hinter dessen Zuverlässigkeit —
und braucht **39 % statt 67 %** des Speichers. Ein 9B der neueren Generation schlägt ein
35B der vorherigen deutlich, bei einem Fünftel des Speichers.

Der eine Fehlschlag ist gutartig gebaut: Lauf 3 brach nach 4 Sekunden mit einem einzigen
Toolcall und 107 Reasoning-Token ab — es führte die Tests einmal aus und hörte auf. Kein
Schleifen, kein Token-Limit, keine degenerierte Ausgabe. Eine neue Session hätte gereicht.
Das unterscheidet sich grundlegend von den Fehlschlägen des Qwen-MoE, die teuer waren und
sich nicht abbrechen ließen.

Bemerkenswert ist auch der Kontext: LM Studio vergab von sich aus **92.672 Token**, weil
die hybride Attention die KV-Cache billig macht. Devstral bekam auf derselben Maschine
4.864.

Damit hat sich die Fragestellung der Untersuchung umgedreht. Sie begann mit „welches große
Modell passt noch hinein" und endet bei **„welches kleinste Modell löst die Aufgabe
zuverlässig"** — weil Speicherreserve auf dieser Maschine direkt in Stabilität umschlägt.

### Reasoning abschalten hilft nicht

Naheliegender Gedanke, da Devstral die Aufgabe mit `reasoning_tokens: 0` löst: beim
Qwen-MoE das Denken abschalten und die Schleife umgehen.

| Modus | Reasoning | Completion | Zeit | Toolcall |
|---|---:|---:|---:|---|
| Thinking an | 108 | 169 | 4,4 s | ja |
| `/no_think` | 2 | 2.047 *(Limit)* | 64,8 s | **nein** |

Ohne Denken ruft das Modell gar keine Tools mehr auf und schwafelt bis ins Token-Limit.
Bei Qwen3.6 trägt das Reasoning das Tool-Calling — man kann es nicht entfernen und das
Verhalten eines Nicht-Reasoning-Modells erwarten. Devstral kommt ohne aus, weil es so
trainiert wurde, nicht weil Denken optional wäre.

*(`chat_template_kwargs: {"enable_thinking": false}` wird von LM Studio stillschweigend
ignoriert; nur das `/no_think`-Token in der Nachricht wirkt tatsächlich.)*

---

## Befund 2 — Ein fehlerhafter Toolcall bei 202

Die Frage, mit der diese Untersuchung begann, war, ob 3-bit-Quantisierung Toolcall-
Argumente beschädigt. Über die gesamte Reihe — sechs Modelle, drei Promptgrößen, zwei
Sampling-Regime, dazu die Reparaturaufgabe — ergaben **202 Toolcalls genau einen
Schema-Fehler**: ein `write` mit vollständig leerem Argument-Objekt. Der Agent erholte
sich im nächsten Schritt, der Lauf wurde trotzdem grün.

Das Harness prüft das selbst, statt dem Agenten-Framework zu vertrauen: es deklariert das
JSON-Schema und validiert jeden eingehenden Aufruf gegen die eigene `required`-Liste,
bevor es ihn ausführt.

Ein Detail ist auffällig, aber unbelegt: der einzige Fehler trat bei der echten Aufgabe
auf, wo `write`-Argumente eine ganze Quelldatei von 1.400 Token transportieren statt
zweier kurzer Strings. Große Argumente könnten der Risikofaktor sein. Ein Vorkommnis ist
kein Beleg; es steht hier als Hypothese.

> **Die Unterscheidung, auf die es ankommt:** „Modell erzeugt kaputte Toolcall-Argumente"
> und „Modell erzeugt gar keine Toolcalls" sehen im Fehlerlog eines Agenten identisch aus
> und haben nichts miteinander zu tun. Das erste zeigt auf die Quantisierung. Das zweite —
> das tatsächlich eintrat — zeigt auf Instruktionsbefolgung unter Kontextdruck. Ich habe
> Stunden auf das falsche verwendet.

---

## Befund 3 — Sampling rettet ein empfindliches Modell und ist einem robusten egal

Qwens dokumentierte Empfehlung für den Thinking-Modus ist `temperature 0.6`,
`top_p 0.95`, `top_k 20`. Ich hatte mit `temperature 0.3` ganz ohne Truncation-Parameter
gearbeitet. Beim Qwen-MoE ist der Unterschied nicht subtil:

| Sampling | Reasoning-Token | Dauer | Finish | Ergebnis |
|---|---:|---:|---|---|
| temp 0.3, kein top_k/top_p | 8.191 | 143 s | length | nichts |
| temp 0.6, top_p 0.95, top_k 20 | 105 | 4 s | tool_calls | korrekter Aufruf |

Ein Faktor 78 aus vier Zahlen. Niedrige Temperatur ohne Nucleus- und Top-k-Begrenzung
treibt dieses Modell in eine Wiederholungsschleife. Der Fingerabdruck im Server-Log von
LM Studio ist eindeutig: wiederholt *Token-ID 0* (`!`), als ungültiges Sample verworfen.

> **Sampling verringert diesen Fehler — es beseitigt ihn nicht.** Die korrekten Parameter
> brachten das MoE von 0/6 auf 3/6 bei der synthetischen und 3/4 bei der echten Aufgabe.
> Aber die Token-ID-0-Schleife trat *mit korrektem Sampling* weiterhin auf, in einem von
> vier Läufen, mit 8.211 verbrannten Reasoning-Tokens.

**Dann lief dieselbe kaputte Konfiguration gegen gpt-oss, und es störte sich nicht daran.**

| Modell | Erfolg | Median | Toolcalls | Length-Stops |
|---|---:|---:|---:|---:|
| gpt-oss-20b | **6/6** | 14,4 s | 14 | 0 |
| Qwen3.6-35B-A3B | 0/6 | — | 0 | jeder Schritt |

gpt-oss war mit den „kaputten" Einstellungen sogar *schneller* — 14,4 s statt 16,4 s —
weil die niedrigere Temperatur es entschlossener machte und es weniger Schritte brauchte.

Die ehrliche Fassung dieses Befunds ist enger als die, die ich zuerst veröffentlicht
hatte: diese Parameter sind keine allgemeine Lösung für lokales agentisches Coding. Sie
sind die Rettung für ein Modell, das ihnen gegenüber empfindlich ist. Wenn dein Modell
sie braucht, sagt es dir damit etwas über sich.

---

## Befund 4 — Die Dateigröße ist die falsche Zahl. Rechne die KV-Cache aus.

Ich habe Kandidaten nach Gewichtsgröße ausgewählt, und das führte in die Irre.
Devstral-Small-2-24B ist auf der Platte *kleiner* als das Qwen-MoE — 14,39 gegen 15,20 GB
— und auf dieser Maschine deutlich schlechter nutzbar, weil die Attention-Architektur
grundverschieden ist.

Qwen3.5/3.6 verschränken Linear-Attention- mit Full-Attention-Layern; gpt-oss wechselt
zwischen Sliding-Window und Full Attention mit einem 128-Token-Fenster. Nur
Full-Attention-Layer kosten KV-Cache. Devstral hat `sliding_window: null` — alle 40 Layer
sind Full Attention, bei 8 KV-Heads und `head_dim` 128.

```
bytes/token = full_attention_layers
            × num_key_value_heads
            × head_dim
            × 2   (K und V)
            × 2   (Bytes pro fp16-Element)
```

| Modell | Layer | Full-Attn | KV-Heads | head_dim | KB/Token | KV @32k | nutzbarer Kontext |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3.6-35B-A3B | 40 | 10 | 2 | 256 | 20 | 0,65 GB | 32.768 |
| gpt-oss-20b | 24 | 12 | 8 | 64 | 24 | 0,75 GB | 32.768 |
| Devstral-Small-2-24B | 40 | **40** | 8 | 128 | **160** | **5,00 GB** | **4.864** |
| gemma-4-26b-a4b | 30 | 5 | 8 | 256 | 40 | 1,25 GB | 16.384 |

Dafür gibt es in diesem Repo [`tools/kvcalc.py`](../tools/kvcalc.py) — es liest
`config.json` und rechnet aus, was bei deinem Kontext übrig bleibt, bevor du ein Gigabyte
herunterlädst.

> **LM Studio hat den Kontext stillschweigend gekürzt.** Ich forderte 16.384 Token an. Das
> Modell lud erfolgreich in 6,1 Sekunden, ohne jede Warnung — und die `CONTEXT`-Spalte von
> `lms ps` zeigte **4.864**. `--parallel 1` änderte nichts. Das einzige Symptom kam später
> als HTTP 400: *„The number of tokens to keep from the initial prompt is greater than the
> context length"*. Prüfe `lms ps` nach jedem Laden.

### Und dann entscheidet die Runtime, ob irgendetwas davon zählt

Aus der 4.864er-Grenze schloss ich, Devstral sei auf 24 GB unbrauchbar. Das war falsch,
und die Art des Fehlers ist lehrreich: ich hatte ein *Werkzeug* gemessen und das Ergebnis
dem *Modell* zugeschrieben. Drei Wege zu denselben Gewichten, drei Ergebnisse:

| Weg | nutzbarer Kontext | Tool-Calling | Urteil |
|---|---:|---|---|
| LM Studio + MLX (MXFP4) | 4.864 — gedeckelt | funktioniert | Kontext zu klein für einen Agenten |
| `mlx_lm.server` + MLX | 13.728 gemessen | **defekt** | liefert eine leere Nachricht |
| LM Studio + GGUF (IQ4_XS) | 16.384 — wie angefordert | funktioniert | **nutzbar** |

Direkt über MLX verarbeitete Devstral einen 13.728-Token-Prompt in 31,7 s bei 16,43 GB
Peak — der Beweis, dass weder Modell noch MLX ein 4.864-Token-Problem haben. Aber
`mlx_lm.server` 0.31.3 liefert die Toolcalls dieses Modells nicht aus: es meldet korrekt
`has_tool_calling = True`, das Modell erzeugt 34 Token, und die Antwort enthält nichts
außer `{"role": "assistant"}`. Reiner Chat funktioniert; sobald `tools` mitgeschickt wird,
ist die Antwort leer.

Der GGUF-Weg ist der einzige, der beides kann. Er kostet Geschwindigkeit — 132 s pro
Aufgabe gegen 55 s für gpt-oss unter MLX — aber er ist der Unterschied zwischen nutzbar
und unbrauchbar.

Noch eine llama.cpp-Falle: bei Kontextüberlauf **hängt** es, statt einen Fehler zu
liefern. Ein 24.000-Token-Prompt in einen 16.384-Token-Kontext ergab Stille, bis LM Studio
fünfzehn Minuten später `Channel Error` protokollierte. MLX antwortet auf denselben Fehler
mit einem sauberen HTTP 400.

---

## Befund 5 — Die Engine entscheidet über Brauchbarkeit, nicht nur über Tempo

Dreimal an einem Tag hat der Wechsel von MLX auf llama.cpp ein Modell von „unbrauchbar"
zu „funktioniert" gedreht. Jedes Mal sah der Fehler im Log wie Modellversagen aus.

| Modell | unter MLX | unter GGUF |
|---|---|---|
| Devstral-Small-2-24B | Kontext still auf 4.864 gedeckelt | 16.384 wie angefordert |
| Qwen3.6-27B | Guardrail verweigert das Laden komplett | lädt mit vollem Kontext |
| Gemma 4 12B | **0/6** — Kanal-Marker-Schleife | **5/6** |

Der Gemma-Fall ist der klarste, weil dasselbe Modell mit derselben Aufgabe, demselben
Harness und denselben Sampling-Werten gemessen wurde — die Engine war die einzige Variable.

Unter LM Studios MLX-Pfad lecken Gemmas Kanal-Marker als Rohtext in `content`:

```
<|channel>thought
<channel|>
```

Anfangs sind es 28 Zeichen. Nach dem Schritt, der `duration.py` einliest, degeneriert die
Generierung in eine reine Marker-Schleife — **49.258 Zeichen, 8.191 Tokens, Length-Stop**,
in zwei unabhängigen Durchläufen an exakt derselben Stelle. `reasoning_tokens` meldete
durchgehend 0.

Meine erste Erklärung war eine Rückkopplung: mein Harness schreibt den Content als
Assistant-Nachricht zurück, das Modell sieht seine eigenen kaputten Marker und produziert
mehr davon. Die Gegenprobe widerlegte das — mit herausgefilterten Markern (bereinigter
Content: 0 Zeichen in allen Schritten) kippte es an derselben Stelle erneut. Die Schleife
entsteht neu, nicht durch Rückkopplung.

Unter llama.cpp verschwindet das Problem vollständig: kein einziger Marker, und
`reasoning_tokens` liegt bei 225 bis 2.797. Was dort korrekt als Reasoning erkannt und
abgetrennt wird, ist unter MLX der Müll, der die Ausgabe sprengt — zwei Seiten derselben
Sache.

**Der Preis ist Tempo.** llama.cpp nutzt die Neural Accelerators des M5 nicht und liegt
rund 2,4× hinter MLX. Gemma braucht unter GGUF 156 s im Median gegen 55 s für gpt-oss
unter MLX, mit erheblicher Streuung: vier saubere Läufe zwischen 146 und 164 Sekunden,
dazu ein Ausreißer mit 1.226 Sekunden.

Für Modelle, die unter MLX sauber laufen, bleibt MLX die bessere Wahl. Aber wenn ein
Modell sich merkwürdig verhält, ist der Engine-Wechsel der erste Test — nicht der letzte.

---

## Befund 6 — Wired Memory ist eine Sprungfunktion, und die Pressure-Anzeige sieht sie nicht

MLX lädt Safetensors per `mmap`. Im Leerlauf sind diese Seiten file-backed — active oder
inactive, nicht wired. Sobald die Inferenz startet, verdrahtet die GPU sie, und der
Wired-Speicher springt in unter zwei Sekunden auf ein Plateau.

Gemessen alle 2 Sekunden über eine 1.200-Token-Generierung beim 15,2-GB-Modell:

| Zeit | Wired | Phase |
|---:|---:|---|
| 0 s | 2,24 GB | Leerlauf |
| 2 s | 19,26 GB | Anlauf abgeschlossen |
| 4–16 s | 19,15 – 19,29 GB | Generierung |
| 18 s | 2,38 GB | freigegeben |

Flach über die gesamte Generierung — 30 MB Drift. Kein Leck. Aber es liegt für die Dauer
jeder einzelnen Anfrage bei 80 % des physischen Speichers, und `memory_pressure` meldet
die ganze Zeit „alles in Ordnung".

Das Plateau liegt grob bei **Gewichte + 2–3 GB** über dem, was das System ohnehin hält:

| Modell | Prompt | Kontext | Wired-Peak | Anteil |
|---|---|---:|---:|---:|
| gpt-oss-20b | kurz | 32.768 | 14,79 GB | 62 % |
| gpt-oss-20b | lang | 32.768 | 16,11 GB | 67 % |
| Devstral-Small-2-24B | kurz | 4.864 | 16,25 GB | 68 % |
| Qwen3.6-35B-A3B | kurz | 32.768 | 18,80 GB | 78 % |
| Qwen3.6-35B-A3B | lang | 32.768 | 19,29 GB | 80 % |

---

## Befund 7 — Man kann das ganze Speicherproblem wegtauschen, gegen Latenz

Alles bisherige kämpft um Luft innerhalb von 24 GB.
[TurboFieldfare](https://github.com/drumih/turbo-fieldfare) umgeht den Kampf: eine
Swift-und-Metal-Runtime, weder MLX noch llama.cpp, geschrieben für genau ein Modell —
Gemma 4 26B-A4B. Sie hält einen 1,35 GB großen Kern resident und **streamt die Experten
jedes Tokens von der SSD**. Das funktioniert nur, weil das Modell ein Mixture of Experts
mit 4B aktiven von 26B Parametern ist.

Die Speicherbehauptung ist kein Marketing:

| Modell · Runtime | Parameter | Wired | Anteil | Prozess-RSS |
|---|---:|---:|---:|---:|
| Gemma 4 26B-A4B · TurboFieldfare | 26B | **5,65 GB** | **24 %** | 1,60 GB |
| gpt-oss-20b · MLX | 21B | 16,11 GB | 67 % | 11,27 GiB |
| Qwen3.6-35B-A3B · MLX | 35B | 20,17 GB | 84 % | 14,16 GiB |

Ein 26-Milliarden-Parameter-Modell bei 24 % des Speichers. Der gesamte Bereich, in dem der
Kernel-Bug aus Befund 7 lauert, ist damit nicht mehr erreichbar. Prompt-Prefix-Reuse
funktioniert ebenfalls: 12.642 von 20.087 Prompt-Token kamen aus dem Cache.

**Und dann ist es zu langsam.** Das ist das Urteil aus der praktischen Nutzung über
OpenCode, nicht aus einem Benchmark: es antwortet, die Analyse taugt, und die Wartezeit
macht es für interaktive Arbeit unbrauchbar. Das README des Projekts misst 31–35 tok/s auf
einem 24-GB-M5-Pro — respektabel — aber Decode-Geschwindigkeit ist nicht die ganze
Geschichte, wenn jeder Schritt Experten von der Platte nachlädt.

Der Handel ist explizit und auf der falschen Maschine getroffen. Auf einem 8-GB-MacBook-Air,
wo die Alternative „geht gar nicht" heißt, ist Latenz gegen Machbarkeit offensichtlich
richtig. Auf 24 GB, wo ein 12-GB-Modell mit Reserve hineinpasst, zahlt man Latenz für
Speicher, den man nicht brauchte.

> **Elf Tage alt, und man merkt es.** Die Reparaturaufgabe ergab hier 0/6, aber diese Zahl
> ist keine Fähigkeitsmessung. Zwei Störgrößen: während eines Teils der Serie war ein
> zweites Modell resident (mein Fehler), und *jeder* Lauf lief in einen HTTP 500, den ich
> isoliert nicht reproduzieren konnte.
>
> Eine Beobachtung steht unabhängig davon: über 18 Toolcalls rief das Modell jedes Mal
> `bash` und **kein einziges Mal `write`** auf. Es führte die Tests aus, sah sie
> scheitern, und versuchte nie eine Änderung.
>
> Der Installer ist ähnlich rau: kein Timeout auf HTTP-Range-Requests, eine abgebrochene
> Verbindung lässt ihn still warten — meiner stand 53 Minuten bei 44 % mit 0 % CPU ohne
> Fehlermeldung. Sein `--resume` ist verlustfrei, was die Lage rettet, aber unbeaufsichtigt
> installieren sollte man das noch nicht.

Beobachten, nicht übernehmen. Erstes Release am 20. Juli 2026, der
OpenAI-kompatible Server am 27., Long-Context-Prefill am 29. — fünf Releases in zehn Tagen.

---

## Befund 8 — Der Kernel-Panic ist ein ungelöster Apple-Bug, nicht MLX

Mitten in der Sitzung ging die Maschine hart zu Boden:

```
panic(cpu 12 caller 0xfffffe0050784280):
"pending memory object unexpectedly found in non pending hash"
@IOGPUGroupMemory.cpp:528

Kernel Extensions in backtrace:
  com.apple.iokit.IOGPUFamily(130.13)
  com.apple.AGXG17X(351.2)

Darwin Kernel Version 25.5.0 / OS version 25F80
```

Eine bekannte Fehlerklasse in Apples IOGPU-Kernel-Extension, mehrfach gemeldet:

- [mlx-lm #883](https://github.com/ml-explore/mlx-lm/issues/883) — Qwen3-Coder-30B-A3B in
  einer Agenten-Session, KV-Cache wuchs unbegrenzt auf ~58k Token, 80,14 GB Wired von
  96 GB, Panic bei `IOGPUMemory.cpp:550`. Der Memory-Pressure-Monitor meldete durchgehend
  *false*. Offen.
- [mlx #3186](https://github.com/ml-explore/mlx/issues/3186) — M4 Max 36 GB, reproduzierbar
  bei ~173k-Token-Prefill. An Apple eskaliert als FB22091885. Offen.
- [mlx #3346](https://github.com/ml-explore/mlx/issues/3346) — M3 Ultra 96 GB, benennt beide
  als IOGPU-Kext-Defekte inklusive einer Race Condition in `IOGPUGroupMemory.cpp:219` —
  dieselbe Datei wie mein Panic, andere Zeile.

> **Warum das schlimmer ist, als es klingt:** Wired Memory umgeht die
> Memory-Pressure-Erkennung von macOS, es warnt also nichts, bevor der Kernel umfällt. Eine
> 96-GB-Maschine stürzte bei 83 % Wired ab. Ein 15-GB-Modell auf einer 24-GB-Maschine liegt
> bei *jeder* Inferenz bei 80 %. Das einzige Instrument, das es sieht, ist
> `memory_pressure | grep "wired down"`.

> **Es gibt genau ein sichtbares Warnsignal, und es steht in keinem Werkzeug.** Spät in der
> Sitzung begann der Bildschirm während eines Qwen-MoE-Laufs zu **flackern**. Wired lag bei
> 20,17 GB — 84 %, der höchste Wert des Tages und über den 83 %, bei denen mlx-lm #883
> seinen Panic meldet. WindowServer braucht ebenfalls GPU-Speicher, und wenn er ihn nicht
> bekommt, stottert die Oberfläche. Wenn dein Bildschirm während einer Generierung
> flackert: speichern und Modell entladen.

macOS 26.6 liefert GPU-Treiber-Fixes — CVE-2026-64691 (unerwartete Systembeendigung,
Buffer Overflow) und CVE-2026-43723 (Speicherkorruption). Keiner nennt die
`IOGPUGroupMemory`-Race.

**Was ihn tatsächlich gefüttert hat:** nicht die Modellgröße und kein großer Prefill. Das
Agenten-Log zeigte `step=138` bis `step=145`, vier Sekunden auseinander und weiter
steigend — eine **Endlosschleife über 145+ Schritte**, jeder davon vergrößerte die
KV-Cache. Diese Schleife existierte wegen der Sampling-Fehlkonfiguration aus Befund 3.

> **Nicht nachmachen:** Ich hatte `iogpu.wired_limit_mb` auf 20480 gesetzt und wollte einen
> LaunchDaemon installieren, um das zu verstetigen. Tu das nicht. mlx-lm #883 empfiehlt,
> das Wired-Limit zu *senken* — vom ~75-%-Default Richtung 50–60 % — nicht zu erhöhen.

---

## Befund 9 — Drei Korrekturen, die es messbar schlechter machten

| Änderung | Absicht | Erfolg | Was passierte |
|---|---|---:|---|
| `tool_choice: "required"` | Toolaufruf erzwingen | 0/3 | 8.191 Token mit *null* Reasoning-Token und leerem Inhalt |
| `max_tokens: 2048` | Runaway-Reasoning deckeln | 0/2 | jeder Schritt lief ins Limit; echte Completions erreichen 2.361 |
| Nachfassen bei fehlendem Toolcall | zurück auf Kurs bringen | 0/1 | 3 Nudges, 32.764 Token, 489 s, kein Toolcall |

Das Nudging-Ergebnis ist das nützliche. Ich nahm an, das Modell entscheide sich für Prosa
und lasse sich zur Handlung bewegen. Nachfassen funktioniert nicht — aber meine
Schlussfolgerung, der Zustand sei immer endgültig, war zu stark. Bei der echten Aufgabe
geriet ein Lauf in die degenerierte Schleife, machte weiter und kam nach 251 Sekunden mit
allen 22 Tests grün heraus. Ein anderer ging hinein und kam nicht zurück. **Erholung ist
möglich, aber nicht verlässlich; eine frische Session bleibt die bessere Wette.**

Die `max_tokens`-Sache ist mein eigener Lesefehler. Ich begründete 2048 mit gemessenen
Reasoning-Token von 70–210 — aber Reasoning-Token sind eine Teilmenge der
Completion-Token, und vollständige Completions erreichten 2.361.

---

## Befund 10 — Werkzeugverhalten, das jeweils eine Stunde kostet

### LM Studio

- **`lms get` liefert Exit-Code 0, wenn der Download scheitert.** Zweimal passiert — einmal,
  weil es eine HuggingFace-Repo-ID stillschweigend kleinschrieb. Nie dem Rückgabewert
  trauen, Dateigrößen prüfen.
- Modell-Keys matchen per Präfix. `qwen3.6-35b-a3b` ist ein Präfix von
  `qwen3.6-35b-a3b-ud-mlx`, und mit `-y` warnt es „2 models match, loading the first one"
  und nimmt irgendeines. Umbenennen mit führendem Punkt hilft nicht — LM Studio scannt
  Punkt-Verzeichnisse. Aus dem Modellbaum verschieben und
  `~/.lmstudio/.internal/model-index-cache.json` löschen.
- Die Benennung von `modelLoadingGuardrails` ist **invertiert**: `mode: "high"` ist der
  permissive Standard, `mode: "low"` ist streng.
- Die Guardrail lehnt allein anhand der Gewichte ab. Ein 16,08-GB-Modell scheiterte
  identisch bei 16.384, 8.192 und 4.096 Kontext mit 20 GB frei. Der „Load Anyway"-Ausweg
  existiert nur in der GUI.
- Kontext kann beim Laden still reduziert werden (Befund 4). Immer mit `lms ps` prüfen.
- Die Server-Logs unter `~/.lmstudio/server-logs/` sind der Ort für echte Diagnose.
  Achtung: der Zähler `Done reasoning. Reasoned for N seconds` ist **kumulativ** seit
  Serverstart, nicht pro Anfrage.

### OpenCode

- `permission` steht per Default auf `ask` für `bash` und `edit`. In nicht-interaktivem
  `opencode run` hängt das im Vordergrund ewig und **endet im Hintergrund sofort mit
  Code 0 und leerem Log**, wenn stdin kein TTY ist. Zwei widersprüchlich aussehende
  Symptome, eine Ursache.
- `provider.<p>.models.<id>.temperature` ist ein **Boolean-Capability-Flag**, kein Wert.
  Eine `0.6` dort bewirkt nichts. Sampling-Werte gehören in `models.<id>.options` oder
  `agent.<name>.temperature` / `top_p`.
- Der interaktive TUI funktionierte durchweg; `opencode run` im Batch-Modus hing in sechs
  von sieben Versuchen vor der Session-Erstellung, ohne dass eine Anfrage den Modellserver
  erreichte. Ursache nicht gefunden. Wenn der Batch-Runner klemmt, liegt es nicht an
  deinem Modell.

### HuggingFace-CLI und macOS

- **Nie ein `hf download` mit `SIGSTOP` anhalten.** Xet-CDN-URLs sind vorsigniert; das
  Aussetzen lässt sie ablaufen, der Resume liefert 403.
- `hf download` setzte meine `.incomplete`-Shards nicht fort — es verwarf 1,5 GB.
- Unsloth-„UD"-Quants sind deutlich größer, als die Bit-Breite nahelegt.
  `Qwen3.6-35B-A3B-UD-MLX-3bit` ist 17,4 GB gegen 15,2 GB für ein normales 3-bit.
- macOS hat kein `timeout(1)`. Und `sudo softwareupdate -i -a --restart` lud 26.6 auf
  100 %, beendete sich mit 0 und installierte nichts. Der GUI-Updater funktionierte.
- htop kann unter macOS **kein Netzwerk pro Prozess** anzeigen — es gibt kein `/proc`.
  `nettop` und `bandwhich` können es. Wichtiger noch: bei stoßweisem Verkehr zeigt jede
  kurze Messung das Falsche; Fenster von mehreren Minuten nehmen.

---

## Korrekturen

Zehn Schlussfolgerungen mussten zurückgezogen werden. Sie stehen hier, weil das Muster
übertragbarer ist als die Einzelfälle: ein echtes Symptom, eine plausible Ursache, kein
Kontrollexperiment.

| Zeit | Behauptung | Was tatsächlich zutraf |
|---|---|---|
| 09:58 | „Wired läuft weg" | Anlauframpe zu einem flachen Plateau, 30 MB Drift. Messung ohne Grund abgebrochen |
| 10:07 | „Output-Budget zu klein" | Direkter API-Aufruf lieferte einen sauberen Toolcall in 118 Token |
| 10:28 | „Die 3-bit-Quantisierung ist defekt" | Echte Belege, falsche Deutung: es war das Sampling. 1 Fehler bei 202 Toolcalls |
| 10:37 | „Promptgröße ist irrelevant" | Galt nur unter kaputtem Sampling. Mit korrektem war sie der stärkste Prädiktor |
| 10:53 | „max_tokens 2048 reicht" | Eigene Tabelle falsch gelesen: 70–210 waren Reasoning-, nicht Completion-Token |
| 11:15 | „Es war das Sampling" *(veröffentlicht)* | Kontrolle gegen gpt-oss: 6/6 mit derselben kaputten Konfiguration |
| 11:41 | „Devstral schafft 0/6" | Zweimal falsch: HTTP 400 vor dem ersten Token, dann meine eigene Verifikationslogik |
| 19:00 | „Devstral ist auf 24 GB nicht nutzbar" *(veröffentlicht)* | Gemessen war LM Studio, zugeschrieben dem Modell. MLX schafft 13.728 Token |
| 19:15 | „GGUF ist unerträglich langsam" | Drei Timeouts, verursacht durch meinen eigenen 24.000-Token-Prompt |
| 20:06 | „807 Sekunden Reasoning auf einer Anfrage" *(veröffentlicht)* | Kumulativer Zähler. Später las er 36.646 s — die Serverlaufzeit |

**Das Muster.** Drei davon waren mein eigenes Werkzeug, das ich als Modellverhalten gelesen
habe: das Backgrounden von `opencode run` (EOF auf stdin, sofortiger Exit 0), die
Permission-Abfrage (stiller Hänger) und die Verifikationslogik (korrekter Code als
Fehlschlag gewertet). Jedes sah exakt wie ein Modellversagen aus.

Bei einem Harness, das man selbst geschrieben hat, sollte die erste Hypothese für ein
überraschendes Ergebnis das Harness sein — nicht das Modell. Ich habe jedes Mal zum Modell
gegriffen, weil das die interessantere Antwort war.

Die anderen haben eine andere Form: einen echten Effekt an einem Modell gemessen und als
allgemeines Prinzip formuliert. Das Kontrollexperiment, das alle drei gefunden hätte —
dieselbe kaputte Konfiguration gegen ein zweites Modell — dauerte elf Minuten, als ich es
endlich machte.

---

## Was offen bleibt

- Ob macOS 26.6 die `IOGPUGroupMemory`-Race behebt. Die gepatchten GPU-Treiber-CVEs sind
  plausible Kandidaten, nennen sie aber nicht.
- Warum das Qwen-MoE unter langem Systemprompt einbricht und gpt-oss nicht. Das *Was* ist
  gemessen, der Mechanismus nicht.
- Ob die Sliding-Window-Modelle bei wirklich langen Kontexten standhalten. Alles hier lief
  bei 32k oder darunter; mlx #3186 reproduziert seinen Panic bei ~173k Prefill.
- Wie sich das über eine einzelne Datei hinaus skaliert. Die Reparaturaufgabe ist echt,
  aber klein.
- Ob große Toolcall-Argumente das Schema-Fehler-Risiko treiben. Ein Vorkommnis bei 202 ist
  eine Hypothese, kein Ergebnis.
- Warum `opencode run` vor der Session-Erstellung hängt, während der TUI funktioniert.

---

*Alle Zahlen gemessen auf einer Maschine an einem Tag. Sechs Läufe pro Konfiguration —
genug, um 3/6 von 6/6 zu unterscheiden, nicht genug für 5/6 gegen 6/6.*
