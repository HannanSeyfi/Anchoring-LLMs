# Which models to test, and why

The study asks how a model arrives at an anchored answer, so every model we analyse must
(1) show its raw reasoning, (2) let us set how much it reasons, and (3) be cheap enough to sample
thousands of times. That rules out closed models for the main analyses: their reasoning is hidden
or summarised. They can still be used later for behaviour-only checks.

## Pilot: two models

| Key in `configs/pilot.yaml` | Model | Why |
| --- | --- | --- |
| `qwen3-8b` | [Qwen/Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) | Hybrid model: the same weights can think or not think, so "reasoning off vs on" is a clean comparison with nothing else changing. Open weights (Apache 2.0), readable traces, fits one A100 or L4 in bfloat16. |
| `r1-distill-llama-8b` | [deepseek-ai/DeepSeek-R1-Distill-Llama-8B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Llama-8B) | A reasoning model from a different family (Llama 3.1 base trained on DeepSeek-R1 reasoning). If both models show the same pattern, it is not a Qwen quirk. Same size, so differences are not just scale. |

**Caveat for R1-Distill.** It was never trained to answer without thinking. Its "off" level
closes the thinking block immediately, which it handles but was not designed for. If its "off"
answers look odd in the pilot (low parse rate, strange estimates), we compare only its low and
high levels.

**If only a free T4 GPU is available**, use `qwen3-4b` (same family, smaller) and
`r1-distill-qwen-1.5b`. The 1.5B model knows few facts, so treat its results as a pipeline check,
not as data.

## Main study: candidates to discuss after the pilot

These are suggestions to decide with the professors once the pilot shows the method works.
Check for newer releases of the same families before starting; models change quickly.

1. **A size ladder within Qwen3** (4B, 8B, 14B, 32B). Same training recipe and the same thinking
   switch, so we can ask whether the mechanism changes with scale. 32B in bfloat16 does not fit a
   40 GB A100; it needs a quantised version, a larger GPU or a hosted API.
2. **gpt-oss-20b** (OpenAI, open weights). Has built-in low/medium/high reasoning effort, so we can
   check that our forced budgets give the same picture as a model's own effort settings. Fits a
   single A100.
3. **Full DeepSeek-R1 through an API**. A frontier-scale model whose reasoning is visible.
4. **One closed frontier model, behaviour only**. Shows whether the headline effect generalises,
   without trace analysis.

## Settings shared by all models

Sampling is identical across models and reasoning levels (temperature 0.7, top-p 0.95), so that
differences come from the condition, not from decoding. These are not each vendor's recommended
settings; we chose one setting to keep comparisons fair. Reasoning levels are budgets of
0 / 512 / 2048 thinking tokens, enforced by stopping the thinking and asking for the answer
(budget forcing). The realised number of thinking tokens is logged for every answer.
