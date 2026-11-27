# Ollama tests

Laptop: 16 GB RAM, Intel i5-1245U, no dedicated GPU

| Model | eval rate (tokens/s) | total duration (s) | Comment |
|---|---|---|---|
| llama3.2:3b | 12.94 | 6.9 | 80 tokens, model already loaded |

## Observations

- Simple SQL question (average of valeur for machine_3): correct on the first try.
- Harder question (highest temperature in the last 7 days): valid SQL, but two errors:
  1. missing filter capteur = 'temperature' (valeur mixes all three sensors);
  2. used AVG instead of MAX.
  Cause: the model only knew the column names, not what the values mean.
  Planned fix: schema description, rules and examples in the prompt (Step 5).
- Speed: about 13 tokens per second on CPU, so about 5 to 15 seconds per full answer.