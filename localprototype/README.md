# localprototype — local-model variant

A copy of `../prototype` that **defaults to a small local model** (no API, free,
offline) so you can A/B it against the API version. Same code; only the defaults
differ:

- `--backend` defaults to **`ollama`** (not `auto`)
- default Ollama model is **`gemma3:4b`** (~0.9s/line warm on CPU after the
  speed tuning below; `gemma3:1b` is ~0.75s if you want even faster)
- shares the parent's venv and voice models (`data/voices` is a symlink to
  `../prototype/data/voices`), so nothing is duplicated

### Speed tuning (baked into OllamaLLM)
- `num_thread=8` — the P-core sweet spot here; 12 oversubscribes the E-cores
- `keep_alive=30m` — model stays resident between runs (cold load ~7.5s hits once)
- trimmed prompt — prompt-eval was ~half the latency; fewer tokens = big win
Tune in `services/llm.py` (`OLLAMA_NUM_THREAD`, `OLLAMA_KEEP_ALIVE`).

## Run

```bash
cd localprototype
./run.sh                              # gemma3:4b, audio on
./run.sh --show-text                  # also print the lines
./run.sh --model dolphin-mistral      # uncensored 7B (slower, more RP flavor)
./run.sh --model mannix/llama3.1-8b-abliterated:q5_K_M   # the 8B (slowest)
./run.sh --backend deepseek           # borrow the API backend for comparison
```

Switch models with `--model <name>` (any model pulled in `ollama list`). Pull more
with e.g. `ollama pull llama3.2:3b`.

## How it compares to ../prototype

| | localprototype | prototype |
|---|---|---|
| Default brain | `gemma3:4b` (local, free) | `deepseek-v4-flash` (API, ~$0.00003/line) |
| Latency | ~0.9s/line warm (CPU, tuned) | ~1.2s/line |
| Quality | good for size; less consistent | stronger, more in-character |
| Cost | $0 | a few cents/hour |

Everything else (subconscious drift, mutating memory, divergence/tangents,
per-agent speech registers, Piper voices) is identical to the parent — see
`../prototype/README.md` for the full design.
