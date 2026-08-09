"""Generation eval: runs golden_set.yaml's *generation* assertions
(expected_tools / answer_must_contain / answer_must_not_contain) through the
real compiled LangGraph agent (apps.backend.graph.build.graph) -- the whole
plan -> tool-call -> synthesize pipeline, not just retrieval in isolation.
Complements eval_retrieval.py, which only exercises rag.retrieval.retriever.

This is a manual/local script, not part of CI (see
.github/workflows/ci.yml's job list): every case is a real, billed LLM call,
and needs a live stack reachable at the configured URLs -- the
alarm-management/ticketing MCP servers and the Qdrant vector store (with the
real corpus already ingested), e.g. via `docker compose up`. Run it the same
way you'd run eval_retrieval.py:

    python -m rag.tests.eval_generation

Most golden_set.yaml rows deliberately leave expected_tools/
answer_must_contain/answer_must_not_contain empty -- see that file's header
comment: "don't hand-write expected answers before the orchestration layer
exists to produce them." Now that it does, GS-11 (the adversarial row) is
the one case with real assertions filled in: the embedded prompt-injection
text in the vendor bulletin document must not change the agent's answer.
Rows without any of the three fields set are skipped here rather than
counted as a vacuous pass -- fill them in as you're ready to pin down
expected agent behavior for them.
"""

import asyncio
import uuid
from pathlib import Path

import yaml
from langchain_core.messages import HumanMessage

from apps.backend.graph.build import graph

GOLDEN_SET_PATH = Path(__file__).resolve().parent / "golden_set.yaml"


def load_golden_set(path: Path = GOLDEN_SET_PATH) -> list[dict]:
    """Load the golden set's rows.

    Args:
        path (Path): path to golden_set.yaml.

    Returns:
        list[dict]: the parsed golden set rows.
    """
    return yaml.safe_load(path.read_text())


def has_generation_assertions(case: dict) -> bool:
    """Whether a golden_set.yaml row has any generation-level assertion to run.

    Args:
        case (dict): one golden_set.yaml row.

    Returns:
        bool: True if expected_tools/answer_must_contain/answer_must_not_contain
            is non-empty for this row.
    """
    return bool(case.get("expected_tools") or case.get("answer_must_contain") or case.get("answer_must_not_contain"))


async def evaluate_case(case: dict) -> dict:
    """Run one golden-set question through the real agent and score it.

    Args:
        case (dict): one golden_set.yaml row.

    Returns:
        dict: per-case result -- the agent's answer, the tool names it
            actually called, which must_contain/must_not_contain/
            expected_tools checks failed (if any), and an overall "passed".
    """
    # Fresh thread per case -- graph.py's checkpointer is process-wide
    # (MemorySaver), so reusing a thread id would leak prior cases' history
    # into this one's planning context.
    thread_id = f"eval-{case['id']}-{uuid.uuid4().hex[:8]}"
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=case["question"])],
            "tool_call_count": 0,
            "confirmed": None,
            "ticket_draft": None,
            "pending_write": None,
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    answer = (result["messages"][-1].content if result.get("messages") else "") or ""
    answer_lower = answer.lower()
    called_tools = {t.name for t in result.get("mcp_trace", [])}

    must_contain = case.get("answer_must_contain") or []
    must_not_contain = case.get("answer_must_not_contain") or []
    expected_tools = case.get("expected_tools") or []

    missing_contains = [s for s in must_contain if s.lower() not in answer_lower]
    leaked_forbidden = [s for s in must_not_contain if s.lower() in answer_lower]
    missing_tools = [t for t in expected_tools if t not in called_tools]

    passed = not missing_contains and not leaked_forbidden and not missing_tools

    return {
        "id": case["id"],
        "passed": passed,
        "answer": answer,
        "called_tools": sorted(called_tools),
        "missing_contains": missing_contains,
        "leaked_forbidden": leaked_forbidden,
        "missing_tools": missing_tools,
        "adversarial_test": case.get("adversarial_test", False),
    }


async def run_evaluation(path: Path = GOLDEN_SET_PATH) -> dict:
    """Run every golden_set.yaml row that has a generation assertion through the real agent.

    Args:
        path (Path): path to golden_set.yaml.

    Returns:
        dict: {"results": [...], "summary": {...}}.
    """
    cases = [c for c in load_golden_set(path) if has_generation_assertions(c)]
    results = [await evaluate_case(case) for case in cases]

    summary = {"total_cases": len(results), "passed": sum(r["passed"] for r in results)}
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
        tag = " [ADVERSARIAL]" if r["adversarial_test"] else ""
        print(f"[{status}] {r['id']}{tag} tools_called={r['called_tools']}")
        if not r["passed"]:
            if r["missing_contains"]:
                print(f"         missing required phrases: {r['missing_contains']}")
            if r["leaked_forbidden"]:
                print(f"         leaked forbidden phrases: {r['leaked_forbidden']}")
            if r["missing_tools"]:
                print(f"         missing expected tool calls: {r['missing_tools']}")
            print(f"         answer: {r['answer'][:300]!r}")

    summary = evaluation["summary"]
    print(f"\nTotal cases: {summary['total_cases']}")
    print(f"Passed: {summary['passed']}/{summary['total_cases']}")
    if summary["total_cases"] == 0:
        print(
            "(No golden_set.yaml rows currently have expected_tools/answer_must_contain/"
            "answer_must_not_contain filled in -- nothing to run. See GS-11 for the one example.)"
        )


if __name__ == "__main__":
    print_report(asyncio.run(run_evaluation()))
