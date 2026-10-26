"""Model backends.

`VLLMBackend` runs open-weight models on a GPU with vLLM and controls reasoning
with budget forcing: the model thinks inside <think>...</think> for at most
`budget` tokens; if it has not finished, the thinking is closed for it and it
must answer (Muennighoff et al., 2025). A budget of 0 closes the thinking block
before any thinking happens, which is the same as Qwen3's non-thinking mode.

`DeepInfraBackend` runs the same budget forcing on models hosted by DeepInfra,
so no GPU is needed, and stops before a run can cost more than a set limit.

`DryRunBackend` fakes plausible model behaviour so the whole pipeline can be
tested without a GPU.
"""

from __future__ import annotations

import json
import math
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .parsing import strip_think

THINK_OPEN = "<think>\n"
THINK_CLOSE = "\n</think>\n\n"
FORCED_CLOSE = "\n\nI have to give my final answer now.\n</think>\n\n"


def chat_prompt(tokenizer, user_message: str) -> str:
    """Chat-formatted prompt that ends with an open <think> block."""
    text = tokenizer.apply_chat_template(
        [{"role": "user", "content": user_message}],
        tokenize=False, add_generation_prompt=True, enable_thinking=True,
    )
    if not text.rstrip().endswith("<think>"):
        text += THINK_OPEN
    elif not text.endswith("\n"):
        text += "\n"
    return text


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
        return chat_prompt(self.tokenizer, user_message)

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


class SpendLimitReached(RuntimeError):
    """Raised before a batch that could take a paid run past its spending limit."""


def load_tokenizer(hf_id: str):
    from transformers import AutoTokenizer  # only the tokenizer files are downloaded

    return AutoTokenizer.from_pretrained(hf_id)


class DeepInfraBackend:
    """Models hosted by DeepInfra (https://deepinfra.com), with the same budget forcing.

    DeepInfra's raw-text completions endpoint uses the prompt exactly as sent, so the
    prompt is built with the model's own chat template and thinking is limited exactly
    as in `VLLMBackend`. Each sample is one request (two when it thinks), sent in
    parallel. The API takes no seed, so samples cannot be reproduced exactly.

    Every reply reports its cost. The running total is saved in `spend_path`, so it
    carries over when a run is resumed, and a batch only starts if even its most
    expensive outcome stays within `max_spend_usd`.
    """

    name = "deepinfra"
    url = "https://api.deepinfra.com/v1/openai/completions"

    def __init__(self, hf_id: str, api_model: str, api_key: Optional[str], price_in: float,
                 price_out: float, max_spend_usd: float, spend_path: Optional[Path] = None,
                 temperature: float = 0.7, top_p: float = 0.95, answer_max_tokens: int = 512,
                 workers: int = 32, timeout: float = 300, max_retries: int = 6,
                 tokenizer=None, post: Optional[Callable[[dict], dict]] = None):
        if not api_key and post is None:
            raise SystemExit("No DeepInfra API key. Set the DEEPINFRA_API_KEY environment variable "
                             "(on Colab: a secret named DEEPINFRA_API_KEY).")
        self.hf_id = hf_id
        self.api_model = api_model
        self.tokenizer = tokenizer if tokenizer is not None else load_tokenizer(hf_id)
        self.price_in = price_in / 1e6    # dollars per token
        self.price_out = price_out / 1e6
        self.max_spend = max_spend_usd
        self.spend_path = Path(spend_path) if spend_path else None
        self.spent = self._load_spend()
        self.temperature = temperature
        self.top_p = top_p
        self.answer_max_tokens = answer_max_tokens
        self.workers = workers
        self.timeout = timeout
        self.max_retries = max_retries
        self._key = api_key
        self._post = post or self._http_post
        self._lock = threading.Lock()

    # -- spending

    def _load_spend(self) -> float:
        if self.spend_path and self.spend_path.exists():
            return float(json.loads(self.spend_path.read_text())["spent_usd"])
        return 0.0

    def _save_spend(self) -> None:
        if self.spend_path:
            self.spend_path.parent.mkdir(parents=True, exist_ok=True)
            self.spend_path.write_text(json.dumps(
                {"spent_usd": round(self.spent, 6), "max_spend_usd": self.max_spend}) + "\n")

    def worst_case_cost(self, requests: list[Request]) -> float:
        """Cost of a batch if every sample thinks up to its budget and writes the longest answer."""
        total = 0.0
        for r in requests:
            p = len(self.tokenizer.encode(self.build_prompt(r.prompt), add_special_tokens=False))
            inputs = p + (p + r.budget + 20 if r.budget else 0)  # the answer call resends the thinking
            outputs = r.budget + self.answer_max_tokens
            total += r.n * (inputs * self.price_in + outputs * self.price_out)
        return total

    # -- requests

    def _http_post(self, payload: dict) -> dict:
        import requests

        delay = 2.0
        for attempt in range(self.max_retries + 1):
            try:
                r = requests.post(self.url, json=payload, timeout=self.timeout,
                                  headers={"Authorization": f"Bearer {self._key}"})
            except requests.RequestException as e:
                problem = type(e).__name__
            else:
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (401, 402, 403):
                    raise SystemExit(f"DeepInfra refused the request ({r.status_code}). Check the API "
                                     f"key and the account balance. {r.text[:300]}")
                if r.status_code != 429 and r.status_code < 500:
                    raise RuntimeError(f"DeepInfra error {r.status_code}: {r.text[:300]}")
                problem = f"HTTP {r.status_code}"
            if attempt == self.max_retries:
                raise RuntimeError(f"DeepInfra did not answer after {attempt + 1} tries ({problem}).")
            time.sleep(delay + random.random())
            delay = min(2 * delay, 60.0)
        raise AssertionError("unreachable")

    def _complete(self, prompt: str, max_tokens: int, stop=None) -> tuple[str, int, Optional[str]]:
        payload = {"model": self.api_model, "prompt": prompt, "max_tokens": max_tokens,
                   "temperature": self.temperature, "top_p": self.top_p}
        if stop:
            payload["stop"] = stop
        out = self._post(payload)
        choice = out["choices"][0]
        text = choice.get("text") or ""
        usage = out.get("usage") or {}
        n_out = usage.get("completion_tokens")
        if n_out is None:
            n_out = len(self.tokenizer.encode(text, add_special_tokens=False))
        cost = usage.get("estimated_cost")
        if cost is None:
            cost = usage.get("prompt_tokens", 0) * self.price_in + n_out * self.price_out
        with self._lock:
            self.spent += float(cost)
        return text, int(n_out), choice.get("finish_reason")

    def build_prompt(self, user_message: str) -> str:
        return chat_prompt(self.tokenizer, user_message)

    def _sample(self, base: str, budget: int) -> Completion:
        if budget == 0:
            text, n_tok, finish = self._complete(base + THINK_CLOSE, self.answer_max_tokens)
            return Completion("", strip_think(text).strip(), 0, n_tok, False, finish)
        thinking, t_tok, t_finish = self._complete(base, budget, stop=["</think>"])
        if "</think>" in thinking:  # the server returned past the stop string
            thinking = thinking.split("</think>")[0]
            t_tok = len(self.tokenizer.encode(thinking, add_special_tokens=False))
            t_finish = "stop"
        truncated = t_finish == "length"
        close = FORCED_CLOSE if truncated else THINK_CLOSE
        text, a_tok, finish = self._complete(base + thinking.rstrip() + close, self.answer_max_tokens)
        return Completion(thinking.strip(), strip_think(text).strip(), t_tok, a_tok, truncated, finish)

    def generate(self, requests: list[Request]) -> list[list[Completion]]:
        worst = self.worst_case_cost(requests)
        if self.spent + worst > self.max_spend:
            raise SpendLimitReached(
                f"Spent ${self.spent:.2f} so far. The next batch could cost up to ${worst:.2f}, which "
                f"could pass the ${self.max_spend:.2f} limit, so the run stopped here. Everything saved "
                f"so far is kept; raise the limit and run again to continue.")
        base = [self.build_prompt(r.prompt) for r in requests]
        jobs = [(i, j) for i, r in enumerate(requests) for j in range(r.n)]
        try:
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                done = list(pool.map(lambda job: self._sample(base[job[0]], requests[job[0]].budget), jobs))
        finally:
            self._save_spend()
        results: list[list[Completion]] = [[] for _ in requests]
        for (i, _), c in zip(jobs, done):
            results[i].append(c)
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


def make_backend(kind: str, model_cfg: dict, cfg: dict, spend_path: Optional[Path] = None):
    if kind == "dryrun":
        return DryRunBackend(seed=cfg["sampling"]["seed"])
    s, e = cfg["sampling"], cfg["engine"]
    if kind == "deepinfra":
        api, price = cfg["api"], model_cfg["price_per_million"]
        return DeepInfraBackend(
            hf_id=model_cfg["hf_id"], api_model=model_cfg.get("api_model", model_cfg["hf_id"]),
            api_key=os.environ.get("DEEPINFRA_API_KEY"), price_in=price["input"],
            price_out=price["output"], max_spend_usd=api["max_spend_usd"], spend_path=spend_path,
            temperature=s["temperature"], top_p=s["top_p"], answer_max_tokens=s["answer_max_tokens"],
            workers=api["workers"], timeout=api["timeout_seconds"], max_retries=api["max_retries"],
        )
    return VLLMBackend(
        hf_id=model_cfg["hf_id"], dtype=model_cfg.get("dtype", "bfloat16"),
        max_model_len=e["max_model_len"], gpu_memory_utilization=e["gpu_memory_utilization"],
        temperature=s["temperature"], top_p=s["top_p"],
        answer_max_tokens=s["answer_max_tokens"], seed=s["seed"],
    )
