"""Model backends.

`VLLMBackend` runs open-weight models on a GPU with vLLM and controls reasoning
with budget forcing: the model thinks inside <think>...</think> for at most
`budget` tokens; if it has not finished, the thinking is closed for it and it
must answer (Muennighoff et al., 2025). A budget of 0 closes the thinking block
before any thinking happens, which is the same as Qwen3's non-thinking mode.

`DryRunBackend` fakes plausible model behaviour so the whole pipeline can be
tested without a GPU.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Optional

from .parsing import strip_think

THINK_OPEN = "<think>\n"
THINK_CLOSE = "\n</think>\n\n"
FORCED_CLOSE = "\n\nI have to give my final answer now.\n</think>\n\n"


@dataclass
class Request:
    cell_id: str
    prompt: str
    budget: int            # maximum thinking tokens; 0 = no thinking
    n: int                 # number of samples
    seed: int
    meta: dict[str, Any] = field(default_factory=dict)  # used only by the dry-run backend


@dataclass
class Completion:
    thinking: str
    answer: str
    thinking_tokens: int
    answer_tokens: int
    thinking_truncated: bool
    answer_finish_reason: Optional[str]


class VLLMBackend:
    name = "vllm"

    def __init__(self, hf_id: str, dtype: str = "bfloat16", max_model_len: int = 8192,
                 gpu_memory_utilization: float = 0.9, temperature: float = 0.7,
                 top_p: float = 0.95, answer_max_tokens: int = 512, seed: int = 0):
        from vllm import LLM  # imported here so the package works without vLLM

        self.hf_id = hf_id
        self.temperature = temperature
        self.top_p = top_p
        self.answer_max_tokens = answer_max_tokens
        self.llm = LLM(model=hf_id, dtype=dtype, max_model_len=max_model_len,
                       gpu_memory_utilization=gpu_memory_utilization, seed=seed)
        self.tokenizer = self.llm.get_tokenizer()

    def build_prompt(self, user_message: str) -> str:
        """Chat-formatted prompt that ends with an open <think> block."""
        text = self.tokenizer.apply_chat_template(
            [{"role": "user", "content": user_message}],
            tokenize=False, add_generation_prompt=True, enable_thinking=True,
        )
        if not text.rstrip().endswith("<think>"):
            text += THINK_OPEN
        elif not text.endswith("\n"):
            text += "\n"
        return text

    def _tokens(self, text: str) -> dict:
        # The chat template already contains any BOS token, so add no special tokens.
        return {"prompt_token_ids": self.tokenizer.encode(text, add_special_tokens=False)}

    def _params(self, n: int, max_tokens: int, seed: int, stop=None):
        from vllm import SamplingParams

        return SamplingParams(n=n, temperature=self.temperature, top_p=self.top_p,
                              max_tokens=max_tokens, seed=seed, stop=stop)

    def generate(self, requests: list[Request]) -> list[list[Completion]]:
        base = [self.build_prompt(r.prompt) for r in requests]

        # Phase A: thinking, for requests with a budget.
        thinking: dict[int, list[tuple[str, int, bool]]] = {}
        think_idx = [i for i, r in enumerate(requests) if r.budget > 0]
        if think_idx:
            outs = self.llm.generate(
                [self._tokens(base[i]) for i in think_idx],
                [self._params(requests[i].n, requests[i].budget, requests[i].seed, stop=["</think>"])
                 for i in think_idx],
                use_tqdm=False,
            )
            for i, out in zip(think_idx, outs):
                thinking[i] = [
                    (o.text, len(o.token_ids), o.finish_reason == "length") for o in out.outputs
                ]

        # Phase B: the answer, after a closed thinking block.
        cont_prompts, cont_params, owners = [], [], []
        for i, r in enumerate(requests):
            if r.budget > 0:
                for j, (text, _, truncated) in enumerate(thinking[i]):
                    close = FORCED_CLOSE if truncated else THINK_CLOSE
                    cont_prompts.append(base[i] + text.rstrip() + close)
                    cont_params.append(self._params(1, self.answer_max_tokens, r.seed + 1000 + j))
                    owners.append((i, j))
            else:
                cont_prompts.append(base[i] + THINK_CLOSE)
                cont_params.append(self._params(r.n, self.answer_max_tokens, r.seed))
                owners.append((i, None))
        outs = self.llm.generate([self._tokens(t) for t in cont_prompts], cont_params, use_tqdm=False)

        results: list[list[Completion]] = [[] for _ in requests]
        for (i, j), out in zip(owners, outs):
            if j is None:
                for o in out.outputs:
                    results[i].append(Completion("", strip_think(o.text).strip(), 0,
                                                 len(o.token_ids), False, o.finish_reason))
            else:
                text, n_tok, truncated = thinking[i][j]
                o = out.outputs[0]
                results[i].append(Completion(text.strip(), strip_think(o.text).strip(), n_tok,
                                             len(o.token_ids), truncated, o.finish_reason))
        return results


class DryRunBackend:
    """Simulated model for testing. Anchors pull estimates; thinking pulls less."""

    name = "dryrun"
    hf_id = "dry-run"

    def __init__(self, seed: int = 0, **_: Any):
        self.seed = seed

    def generate(self, requests: list[Request]) -> list[list[Completion]]:
        results = []
        for r in requests:
            rnd = random.Random(f"{self.seed}|{r.cell_id}")
            truth = r.meta.get("truth") or 100.0
            anchor = r.meta.get("anchor")
            comps = []
            for _ in range(r.n):
                belief = truth * math.exp(rnd.gauss(0.15, 0.35)) if truth > 0 else truth + rnd.gauss(0, 5)
                tokens = 0 if r.budget == 0 else min(r.budget, int(rnd.uniform(0.4, 1.3) * r.budget))
                pull = 0.45 - 0.15 * (tokens / 2048)
                if anchor is not None and belief > 0 and anchor > 0:
                    est = belief * (anchor / belief) ** pull
                elif anchor is not None:
                    est = belief + pull * (anchor - belief)
                else:
                    est = belief
                thinking = ""
                if r.budget > 0:
                    start = anchor if anchor is not None else belief
                    thinking = (f"Let me think. A natural starting point is {start:.4g}. "
                                f"Adjusting, maybe {0.5 * (start + est):.4g}, so about {est:.4g}.")
                comparison = ""
                if anchor is not None:
                    comparison = f"Comparison: {'higher' if est > anchor else 'lower'}\n"
                answer = f"My best guess.\n{comparison}Estimate: {est:,.4g}"
                comps.append(Completion(thinking, answer, tokens, 20, tokens >= r.budget > 0, "stop"))
            results.append(comps)
        return results


def make_backend(kind: str, model_cfg: dict, cfg: dict):
    if kind == "dryrun":
        return DryRunBackend(seed=cfg["sampling"]["seed"])
    s, e = cfg["sampling"], cfg["engine"]
    return VLLMBackend(
        hf_id=model_cfg["hf_id"], dtype=model_cfg.get("dtype", "bfloat16"),
        max_model_len=e["max_model_len"], gpu_memory_utilization=e["gpu_memory_utilization"],
        temperature=s["temperature"], top_p=s["top_p"],
        answer_max_tokens=s["answer_max_tokens"], seed=s["seed"],
    )
