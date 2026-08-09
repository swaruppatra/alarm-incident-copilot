"""Unit tests for apps/frontend/app.py's pure formatting/parsing helpers --
no Gradio runtime, no network. Covers "citation formatting" and part of
"payload construction"/"response parsing" from the assignment's unit test list.
"""

from apps.frontend.app import (
    build_edited_args,
    format_citations,
    format_ops_rows,
    format_similar_tickets,
    format_trace,
    ticket_fields_from_pending,
)


class TestFormatTrace:
    def test_formats_one_row_per_entry(self):
        trace = [
            {"name": "search_assets", "args": {"query": "Boiler"}, "duration": 0.1234, "status": "success", "retry_count": 0},
            {"name": "get_alarms", "args": {"asset_id": "AST-0001"}, "duration": 0.5, "status": "error", "retry_count": 2},
        ]
        rows = format_trace(trace)
        assert rows == [
            ["search_assets", '{"query": "Boiler"}', 0.123, "success", 0],
            ["get_alarms", '{"asset_id": "AST-0001"}', 0.5, "error", 2],
        ]

    def test_empty_trace_gives_empty_rows(self):
        assert format_trace([]) == []

    def test_missing_optional_fields_default_sanely(self):
        rows = format_trace([{"name": "get_ticket"}])
        assert rows == [["get_ticket", "{}", 0.0, None, 0]]


class TestFormatCitations:
    def test_formats_and_rounds_score(self):
        citations = [{"source": "rag/documents/troubleshooting/x.md", "section": "Symptom", "score": 0.87654, "snippet": "High vibration..."}]
        rows = format_citations(citations)
        assert rows == [["rag/documents/troubleshooting/x.md", "Symptom", 0.877, "High vibration..."]]

    def test_missing_section_and_snippet_fall_back_to_dash(self):
        rows = format_citations([{"source": "doc.md", "score": 0.5}])
        assert rows == [["doc.md", "-", 0.5, "-"]]

    def test_empty_citations_gives_empty_rows(self):
        assert format_citations([]) == []


class TestFormatSimilarTickets:
    def test_filters_to_ticket_search_tools_only(self):
        trace = [
            {"name": "search_assets", "args": {}, "status": "success"},
            {"name": "search_similar_tickets", "args": {"query": "vibration"}, "status": "success", "result": "2 tickets found"},
            {"name": "list_open_tickets_for_assets", "args": {"asset_ids": ["AST-0001"]}, "status": "success", "result": "1 ticket"},
        ]
        rows = format_similar_tickets(trace)
        assert len(rows) == 2
        assert rows[0][0] == "search_similar_tickets"
        assert rows[1][0] == "list_open_tickets_for_assets"

    def test_no_matching_tools_gives_empty_rows(self):
        trace = [{"name": "search_assets", "args": {}, "status": "success"}]
        assert format_similar_tickets(trace) == []

    def test_missing_result_falls_back_to_dash(self):
        trace = [{"name": "search_similar_tickets", "args": {}, "status": "success"}]
        rows = format_similar_tickets(trace)
        assert rows[0][3] == "-"


class TestTicketFieldsFromPending:
    def test_none_pending_returns_unknown_empty_defaults(self):
        fields = ticket_fields_from_pending(None)
        assert fields["mode"] == "unknown"
        assert fields["is_create"] is False
        assert fields["is_update"] is False
        assert fields["summary"] == ""

    def test_create_ticket_extracts_req_fields(self):
        pending = {
            "name": "create_ticket",
            "args": {
                "req": {
                    "summary": "High vibration on BFP-101",
                    "description": "Recurring vibration alarm",
                    "status": "open",
                    "priority": "high",
                    "labels": ["vibration", "pump"],
                    "asset_id": "AST-0001",
                    "alarm_id": "ALM-00042",
                }
            },
        }
        fields = ticket_fields_from_pending(pending)
        assert fields["mode"] == "create"
        assert fields["is_create"] is True
        assert fields["is_update"] is False
        assert fields["summary"] == "High vibration on BFP-101"
        assert fields["labels"] == "vibration, pump"
        assert fields["asset_id"] == "AST-0001"
        assert fields["alarm_id"] == "ALM-00042"

    def test_update_ticket_extracts_ticket_id_and_req_fields(self):
        pending = {
            "name": "update_ticket",
            "args": {"ticket_id": "TKT-0001", "req": {"status": "resolved", "resolution_notes": "Bearing replaced"}},
        }
        fields = ticket_fields_from_pending(pending)
        assert fields["mode"] == "update"
        assert fields["is_update"] is True
        assert fields["is_create"] is False
        assert fields["ticket_id"] == "TKT-0001"
        assert fields["status"] == "resolved"
        assert fields["resolution_notes"] == "Bearing replaced"

    def test_unrecognized_tool_name_returns_unknown_defaults(self):
        fields = ticket_fields_from_pending({"name": "search_assets", "args": {}})
        assert fields["mode"] == "unknown"

    def test_create_ticket_missing_optional_fields_default_to_empty(self):
        pending = {"name": "create_ticket", "args": {"req": {"summary": "S", "description": "D"}}}
        fields = ticket_fields_from_pending(pending)
        assert fields["priority"] == ""
        assert fields["labels"] == ""
        assert fields["status"] == "open"


class TestBuildEditedArgs:
    def test_none_pending_returns_none(self):
        assert build_edited_args(None, *([""] * 9)) is None

    def test_create_ticket_rebuilds_req_with_edits(self):
        pending = {"name": "create_ticket", "args": {"req": {"summary": "old"}}}
        result = build_edited_args(
            pending,
            "new summary", "new description", "in_progress", "high", "a, b, c",
            "AST-0002", "ALM-99", "", "",
        )
        assert result == {
            "req": {
                "summary": "new summary",
                "description": "new description",
                "status": "in_progress",
                "priority": "high",
                "labels": ["a", "b", "c"],
                "asset_id": "AST-0002",
                "alarm_id": "ALM-99",
            }
        }

    def test_update_ticket_rebuilds_ticket_id_and_req(self):
        pending = {"name": "update_ticket", "args": {"ticket_id": "TKT-0005", "req": {}}}
        result = build_edited_args(
            pending, "", "", "closed", "low", "", "", "", "TKT-0005", "Fixed via reseat",
        )
        assert result == {
            "ticket_id": "TKT-0005",
            "req": {"status": "closed", "priority": "low", "labels": None, "resolution_notes": "Fixed via reseat"},
        }

    def test_empty_labels_string_becomes_empty_list_not_list_with_blank(self):
        pending = {"name": "create_ticket", "args": {}}
        result = build_edited_args(pending, "s", "d", "open", "", "", "", "", "", "")
        assert result["req"]["labels"] == []

    def test_unrecognized_tool_returns_original_args_unchanged(self):
        pending = {"name": "some_other_tool", "args": {"foo": "bar"}}
        result = build_edited_args(pending, *([""] * 9))
        assert result == {"foo": "bar"}


class TestFormatOpsRows:
    def test_formats_and_rounds_duration_and_dumps_payload(self):
        rows = format_ops_rows([{
            "id": 1, "thread_id": "t1", "event_type": "tool_call", "name": "search_assets",
            "status": "success", "duration_seconds": 0.12345, "prompt_version": "v1",
            "created_at": "2026-08-09T00:00:00Z", "payload": {"args": {"query": "x"}},
        }])
        assert rows[0][0] == 1
        assert rows[0][5] == 0.123
        assert '"query": "x"' in rows[0][8]

    def test_none_duration_and_payload_handled_without_crashing(self):
        rows = format_ops_rows([{
            "id": 2, "thread_id": "t1", "event_type": "confirmation", "name": "create_ticket",
            "status": "approved", "duration_seconds": None, "prompt_version": "v1",
            "created_at": "2026-08-09T00:00:01Z", "payload": None,
        }])
        assert rows[0][5] is None
        assert rows[0][8] == ""
