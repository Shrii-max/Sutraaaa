"""Candidate LLM Benchmark Evaluation CLI for Indian Legal Reasoning.

Follows v2 Reliability Requirement 1(e):
`scripts/benchmark_models.py`: runs candidate models on /tests/eval set,
prints Markdown comparison table.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

from app.config import get_settings
from app.llm.client import FakeLLMClient, OpenAICompatClient, LLMClient
from tests.eval.runner import EvaluationHarness


def run_benchmark_for_model(model_name: str, dataset_path: Path, use_fake: bool = False) -> Dict[str, Any]:
    """Run benchmark evaluation suite for a single model candidate."""
    start_time = time.perf_counter()
    if use_fake:
        # High-accuracy deterministic fake
        client = FakeLLMClient()
    else:
        client = OpenAICompatClient(model=model_name)

    harness = EvaluationHarness(dataset_path=dataset_path, llm_client=client)
    report = harness.run()
    elapsed = time.perf_counter() - start_time

    return {
        "model": model_name,
        "elapsed_sec": round(elapsed, 2),
        "fact_precision": round(report.fact_precision * 100, 1),
        "fact_recall": round(report.fact_recall * 100, 1),
        "snippet_pass_rate": round(report.snippet_pass_rate * 100, 1),
        "timeline_accuracy": round(report.timeline_date_accuracy * 100, 1),
        "hallucinated_rate": round(report.hallucinated_citation_rate * 100, 1),
        "passed": report.hallucinated_citation_rate == 0.0,
    }


def main():
    parser = argparse.ArgumentParser(description="LexAgent Local Model Benchmark CLI")
    parser.add_argument(
        "--models",
        type=str,
        default="qwen2.5:14b-instruct,deepseek-r1:14b,mistral-7b-instruct",
        help="Comma-separated candidate model names",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="tests/eval/dataset.json",
        help="Path to evaluation dataset JSON",
    )
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Use deterministic offline fake client for testing",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Error: Dataset not found at {dataset_path}", file=sys.stderr)
        sys.exit(1)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    results = []

    print(f"\n================================================================================")
    print(f"BENCHMARKING {len(models)} CANDIDATE MODELS ON DATASET: {dataset_path}")
    print(f"================================================================================")

    for m in models:
        print(f"-> Testing model: {m} ...", flush=True)
        try:
            res = run_benchmark_for_model(m, dataset_path, use_fake=args.fake)
            results.append(res)
        except Exception as err:
            print(f"   [!] Failed testing {m}: {err}")
            results.append({
                "model": m,
                "elapsed_sec": 0.0,
                "fact_precision": 0.0,
                "fact_recall": 0.0,
                "snippet_pass_rate": 0.0,
                "timeline_accuracy": 0.0,
                "hallucinated_rate": 100.0,
                "passed": False,
            })

    # Print Markdown table
    print("\n### Candidate Model Benchmark Results (Markdown)\n")
    print("| Model Name | Fact Precision | Fact Recall | Snippet Pass Rate | Timeline Accuracy | Hallucinated Precedents | Latency (s) | Gate Status |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for r in results:
        status_badge = "PASS" if r["passed"] else "FAIL (Hallucination > 0)"
        print(
            f"| `{r['model']}` | {r['fact_precision']}% | {r['fact_recall']}% | "
            f"{r['snippet_pass_rate']}% | {r['timeline_accuracy']}% | {r['hallucinated_rate']}% | "
            f"{r['elapsed_sec']}s | **{status_badge}** |"
        )
    print("\n")


if __name__ == "__main__":
    main()

