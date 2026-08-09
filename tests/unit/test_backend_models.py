"""Unit tests for input validation on apps/backend's Pydantic request/response
models (main.py, models.py) -- the "input validation" line item from the
assignment's unit test list.
"""

import pytest
from pydantic import ValidationError

from apps.backend.main import ChatRequest, ChatResponse, ConfirmRequest
from apps.backend.models import IntentClassification, McpTraceEntry


class TestChatRequest:
    def test_valid_request_parses(self):
        req = ChatRequest(message="Hello", thread_id="t-1")
        assert req.message == "Hello"
        assert req.thread_id == "t-1"

    def test_missing_message_is_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(thread_id="t-1")

    def test_missing_thread_id_is_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="Hello")


class TestConfirmRequest:
    def test_valid_request_parses(self):
        req = ConfirmRequest(thread_id="t-1", approved=True)
        assert req.approved is True
        assert req.edited_args is None

    def test_edited_args_optional_and_defaults_to_none(self):
        req = ConfirmRequest(thread_id="t-1", approved=False)
        assert req.edited_args is None

    def test_edited_args_accepted_when_present(self):
        req = ConfirmRequest(thread_id="t-1", approved=True, edited_args={"req": {"summary": "edited"}})
        assert req.edited_args == {"req": {"summary": "edited"}}

    def test_missing_approved_is_rejected(self):
        with pytest.raises(ValidationError):
            ConfirmRequest(thread_id="t-1")


class TestChatResponse:
    def test_defaults_are_empty_not_none_for_list_fields(self):
        resp = ChatResponse(thread_id="t-1")
        assert resp.answer is None
        assert resp.requires_confirmation is False
        assert resp.citations == []
        assert resp.mcp_trace == []

    def test_citations_and_trace_are_plain_dicts_not_validated_models(self):
        # ChatResponse stores already-serialized dicts (model_dump'd in
        # main.py's _to_response), not typed sub-models -- confirm loose
        # dicts round-trip untouched.
        resp = ChatResponse(thread_id="t-1", citations=[{"source": "doc.md", "score": 0.9}])
        assert resp.citations == [{"source": "doc.md", "score": 0.9}]


class TestMcpTraceEntry:
    def test_valid_entry_parses(self):
        entry = McpTraceEntry(name="search_assets", args={"query": "x"}, duration=0.1, status="success", retry_count=0)
        assert entry.result is None

    def test_invalid_status_literal_is_rejected(self):
        with pytest.raises(ValidationError):
            McpTraceEntry(name="search_assets", args={}, duration=0.1, status="pending", retry_count=0)

    def test_result_field_accepts_string_or_none(self):
        entry = McpTraceEntry(name="get_ticket", args={}, duration=0.1, status="success", retry_count=0, result="ok")
        assert entry.result == "ok"


class TestIntentClassification:
    def test_valid_intent_parses(self):
        assert IntentClassification(intent="prepare_incident").intent == "prepare_incident"

    def test_invalid_intent_literal_is_rejected(self):
        with pytest.raises(ValidationError):
            IntentClassification(intent="not_a_real_intent")
