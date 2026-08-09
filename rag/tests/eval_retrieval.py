import statistics
from pathlib import Path

import yaml

from rag.retrieval.models import RetrievalQuery
from rag.retrieval.retriever import retrieve

GOLDEN_SET_PATH = Path(__file__).resolve().parent / "golden_set.yaml"


def load_golden_set(path: Path = GOLDEN_SET_PATH) -> list[dict]:
    """Load the golden set's rows.

    Args:
        path (Path): path to golden_set.yaml.

    Returns:
        list[dict]: the parsed golden set rows.
    """
    return yaml.safe_load(path.read_text())


def evaluate_case(case: dict) -> dict:
    """Run one golden-set question through retrieval and score it.

    expect_no_confident_match rows are scored as a pass/fail confidence-gate
    check (confident must be False), matching golden_set.yaml's own
    documented eval procedure. Every other row is scored by whether the
    retrieved chunks' source filename stems cover expected_doc_ids.

    Args:
        case (dict): one golden_set.yaml row.

    Returns:
        dict: per-case result (precision_at_k/recall_at_k/reciprocal_rank/passed
            for retrieval rows, or confident/passed for no-match rows).
    """
    result = retrieve(RetrievalQuery(query=case["question"], top_k=case["top_k"]))

    if case.get("expect_no_confident_match"):
        return {
            "id": case["id"],
            "type": "no_match",
            "passed": result.confident is False,
            "confident": result.confident,
        }

    expected = set(case["expected_doc_ids"])
    retrieved_stems = [Path(chunk.metadata.source).stem for chunk in result.chunks]
    retrieved_set = set(retrieved_stems)

    hits = expected & retrieved_set
    precision_at_k = (
        sum(1 for stem in retrieved_stems if stem in expected) / len(retrieved_stems) if retrieved_stems else 0.0
    )
    recall_at_k = len(hits) / len(expected) if expected else 1.0
    full_match = expected.issubset(retrieved_set)

    rank = next((i + 1 for i, stem in enumerate(retrieved_stems) if stem in expected), None)
    reciprocal_rank = 1 / rank if rank else 0.0

    return {
        "id": case["id"],
        "type": "retrieval",
        "passed": full_match,
        "precision_at_k": precision_at_k,
        "recall_at_k": recall_at_k,
        "reciprocal_rank": reciprocal_rank,
        "expected": sorted(expected),
        "retrieved": retrieved_stems,
        "adversarial_test": case.get("adversarial_test", False),
    }


def run_evaluation(path: Path = GOLDEN_SET_PATH) -> dict:
    """Run the full golden set through retrieval and aggregate metrics.

    Args:
        path (Path): path to golden_set.yaml.

    Returns:
        dict: {"results": [...], "summary": {...}} -- per-case results plus
            aggregate precision@k/recall@k/MRR/full-match-rate for retrieval
            rows and confidence-gate accuracy for no-match rows.
    """
    cases = load_golden_set(path)
    results = [evaluate_case(case) for case in cases]

    retrieval_results = [r for r in results if r["type"] == "retrieval"]
    no_match_results = [r for r in results if r["type"] == "no_match"]

    summary = {
        "total_cases": len(results),
        "retrieval_cases": len(retrieval_results),
        "no_match_cases": len(no_match_results),
    }
    if retrieval_results:
        summary["mean_precision_at_k"] = statistics.mean(r["precision_at_k"] for r in retrieval_results)
        summary["mean_recall_at_k"] = statistics.mean(r["recall_at_k"] for r in retrieval_results)
        summary["mean_reciprocal_rank"] = statistics.mean(r["reciprocal_rank"] for r in retrieval_results)
        summary["full_match_rate"] = sum(r["passed"] for r in retrieval_results) / len(retrieval_results)
    if no_match_results:
        summary["no_match_accuracy"] = sum(r["passed"] for r in no_match_results) / len(no_match_results)

    return {"results": results, "summary": summary}


def print_report(evaluation: dict) -> None:
    """Print a human-readable report of an evaluation's results.

    Args:
        evaluation (dict): the dict returned by run_evaluation.

    Returns:
        None
    """
    for r in evaluation["results"]:
        status = "PASS" if r["passed"] else "FAIL"
        if r["type"] == "no_match":
            print(f"[{status}] {r['id']} (no-match gate) confident={r['confident']}")
            continue

        tag = " [ADVERSARIAL]" if r["adversarial_test"] else ""
        print(
            f"[{status}] {r['id']}{tag} precision@k={r['precision_at_k']:.2f} "
            f"recall@k={r['recall_at_k']:.2f} rr={r['reciprocal_rank']:.2f}"
        )
        if not r["passed"]:
            print(f"         expected={r['expected']} retrieved={r['retrieved']}")

    summary = evaluation["summary"]
    print(f"\nTotal cases: {summary['total_cases']}")
    if "mean_precision_at_k" in summary:
        print(f"Mean precision@k: {summary['mean_precision_at_k']:.3f}")
        print(f"Mean recall@k:    {summary['mean_recall_at_k']:.3f}")
        print(f"Mean reciprocal rank (MRR): {summary['mean_reciprocal_rank']:.3f}")
        print(f"Full-match rate:  {summary['full_match_rate']:.3f} ({summary['retrieval_cases']} cases)")
    if "no_match_accuracy" in summary:
        print(f"No-match gate accuracy: {summary['no_match_accuracy']:.3f} ({summary['no_match_cases']} cases)")


if __name__ == "__main__":
    print_report(run_evaluation())
