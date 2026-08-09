import json
import uuid

import gradio as gr

from apps.frontend import client
from apps.frontend.audit_reader import read_audit_trail
from apps.frontend.config import get_settings

STATUS_CHOICES = ["open", "in_progress", "resolved", "closed"]
PRIORITY_CHOICES = ["low", "medium", "high", "critical"]
WRITE_TOOLS_WITH_TICKET_FIELDS = {"create_ticket", "update_ticket"}

TRACE_HEADERS = ["Tool", "Args", "Duration (s)", "Status", "Retries"]
CITATION_HEADERS = ["Document", "Section", "Score", "Snippet"]
SIMILAR_TICKETS_HEADERS = ["Tool", "Query Args", "Status", "Result"]
OPS_HEADERS = ["id", "thread_id", "event_type", "name", "status", "duration_s", "prompt_version", "created_at", "payload"]

# gr.State resets on every WebSocket reconnect (backgrounded tab, laptop
# sleep, network blip -- all common, none of them an actual crash), which
# would otherwise hand out a brand-new random thread_id and silently orphan
# the conversation still sitting in the backend's checkpoint. Persisting the
# id in the browser itself survives a reconnect; only an explicit "New
# conversation" click should ever mint a new one.
LOAD_THREAD_ID_JS = """
() => {
    let tid = window.localStorage.getItem('copilot_thread_id');
    if (!tid) {
        tid = crypto.randomUUID();
        window.localStorage.setItem('copilot_thread_id', tid);
    }
    return [tid, tid];
}
"""
NEW_THREAD_ID_JS = """
() => {
    const tid = crypto.randomUUID();
    window.localStorage.setItem('copilot_thread_id', tid);
    return [tid, tid];
}
"""
# Gradio's dark mode is a CSS variant toggled by a `__theme` URL query param,
# not something `theme=` on Blocks() can force by itself. A one-time redirect
# is the standard way to pin it regardless of the visitor's OS/browser
# preference; once the param is present this is a no-op.
FORCE_DARK_JS = """
() => {
    const url = new URL(window.location);
    if (url.searchParams.get('__theme') !== 'dark') {
        url.searchParams.set('__theme', 'dark');
        window.location.href = url.href;
    }
}
"""


def new_thread_id() -> str:
    """Generate a fresh conversation thread id.

    Args:
        None

    Returns:
        str: a new random thread id.
    """
    return str(uuid.uuid4())


def format_trace(mcp_trace: list[dict]) -> list[list]:
    """Format mcp_trace entries as rows for the MCP execution trace table.

    Args:
        mcp_trace (list[dict]): McpTraceEntry dicts from a ChatResponse.

    Returns:
        list[list]: one row per trace entry, matching TRACE_HEADERS.
    """
    return [
        [
            entry.get("name"),
            json.dumps(entry.get("args", {})),
            round(entry.get("duration", 0.0), 3),
            entry.get("status"),
            entry.get("retry_count", 0),
        ]
        for entry in mcp_trace
    ]


def format_citations(citations: list[dict]) -> list[list]:
    """Format citations as rows for the citations table.

    Args:
        citations (list[dict]): Citation dicts from a ChatResponse.

    Returns:
        list[list]: one row per citation, matching CITATION_HEADERS.
    """
    return [
        [c.get("source"), c.get("section") or "-", round(c.get("score", 0.0), 3), c.get("snippet") or "-"]
        for c in citations
    ]


def format_similar_tickets(mcp_trace: list[dict]) -> list[list]:
    """Similar-tickets panel, derived from the MCP trace.

    Args:
        mcp_trace (list[dict]): McpTraceEntry dicts from a ChatResponse.

    Returns:
        list[list]: one row per matching tool call, matching SIMILAR_TICKETS_HEADERS.
    """
    return [
        [entry.get("name"), json.dumps(entry.get("args", {})), entry.get("status"), entry.get("result") or "-"]
        for entry in mcp_trace
        if entry.get("name") in ("search_similar_tickets", "list_open_tickets_for_assets")
    ]


def ticket_fields_from_pending(pending_write: dict | None) -> dict:
    """Extract the editable ticket fields implied by a pending_write payload.

    Args:
        pending_write (dict | None): {"name", "args", ...} for create_ticket or update_ticket.

    Returns:
        dict: normalized field values (empty strings for anything absent),
            plus "mode" ("create", "update", or "unknown") and "is_create"/"is_update" flags.
    """
    empty = {
        "mode": "unknown", "is_create": False, "is_update": False,
        "summary": "", "description": "", "status": "open", "priority": "",
        "labels": "", "asset_id": "", "alarm_id": "", "ticket_id": "", "resolution_notes": "",
    }
    if not pending_write:
        return empty

    name = pending_write.get("name")
    args = pending_write.get("args") or {}
    req = args.get("req") or {}

    if name == "create_ticket":
        return {
            **empty,
            "mode": "create", "is_create": True,
            "summary": req.get("summary", ""),
            "description": req.get("description", ""),
            "status": req.get("status") or "open",
            "priority": req.get("priority") or "",
            "labels": ", ".join(req.get("labels") or []),
            "asset_id": req.get("asset_id") or "",
            "alarm_id": req.get("alarm_id") or "",
        }
    if name == "update_ticket":
        return {
            **empty,
            "mode": "update", "is_update": True,
            "ticket_id": args.get("ticket_id", ""),
            "status": req.get("status") or "",
            "priority": req.get("priority") or "",
            "labels": ", ".join(req.get("labels") or []),
            "resolution_notes": req.get("resolution_notes") or "",
        }
    return empty


def build_edited_args(pending_write: dict | None, summary, description, status, priority, labels, asset_id,
                       alarm_id, ticket_id, resolution_notes) -> dict | None:
    """Rebuild a pending_write's args from the (possibly edited) form fields.

    Args:
        pending_write (dict | None): the original pending_write, to read which tool this is for.
        summary, description, status, priority, labels, asset_id, alarm_id, ticket_id, resolution_notes:
            current form field values.

    Returns:
        dict | None: the edited args in the same shape the backend expects
            ({"req": {...}} for create_ticket, {"ticket_id", "req": {...}} for
            update_ticket), or None if there's no pending write to edit.
    """
    if not pending_write:
        return None
    name = pending_write.get("name")
    labels_list = [label.strip() for label in labels.split(",") if label.strip()] if labels else []

    if name == "create_ticket":
        return {
            "req": {
                "summary": summary,
                "description": description,
                "status": status,
                "priority": priority or None,
                "labels": labels_list,
                "asset_id": asset_id or None,
                "alarm_id": alarm_id or None,
            }
        }
    if name == "update_ticket":
        return {
            "ticket_id": ticket_id,
            "req": {
                "status": status or None,
                "priority": priority or None,
                "labels": labels_list or None,
                "resolution_notes": resolution_notes or None,
            },
        }
    return pending_write.get("args")


def format_ops_rows(rows: list[dict]) -> list[list]:
    """Format audit_log rows for the Ops tab table.

    Args:
        rows (list[dict]): rows from audit_reader.read_audit_trail.

    Returns:
        list[list]: one row per audit entry, matching OPS_HEADERS.
    """
    formatted = []
    for row in rows:
        duration = row.get("duration_seconds")
        payload = row.get("payload")
        formatted.append(
            [
                row.get("id"),
                row.get("thread_id"),
                row.get("event_type"),
                row.get("name"),
                row.get("status"),
                round(duration, 3) if duration is not None else None,
                row.get("prompt_version"),
                row.get("created_at"),
                json.dumps(payload) if payload is not None else "",
            ]
        )
    return formatted


def new_conversation() -> tuple:
    """Reset the whole Copilot tab for a fresh conversation thread.

    thread_id/thread_display are deliberately left unchanged here -- a
    sibling JS-only click handler (see LOAD_THREAD_ID_JS/NEW_THREAD_ID_JS)
    owns generating and persisting the thread id in the browser's
    localStorage, so a page reload (WebSocket reconnect, tab backgrounded,
    laptop sleep -- all of which reset every gr.State) resumes the same
    thread instead of silently orphaning it in favor of a random new one.

    Args:
        None

    Returns:
        tuple: cleared chat history, no-op for thread id (state + display),
            cleared status/panels, and a hidden ticket group.
    """
    return (
        [],
        gr.update(),
        gr.update(),
        "",
        gr.update(visible=False),
        None,
        [],
        [],
        [],
    )


def send_message(message: str, history: list, thread_id: str):
    """Send a user message to the backend and render the resulting turn.

    A generator so the UI can show a loading state immediately (the user
    message + "Thinking...") before the (potentially slow, LLM + MCP calls)
    backend response arrives.

    Args:
        message (str): the text box's current content.
        history (list): the chatbot's current message list.
        thread_id (str): this session's conversation thread id.

    Returns:
        Generator yielding (history, textbox_clear, status, ticket_group_visible,
            pending_write_state, trace_rows, citation_rows, similar_ticket_rows) tuples.
    """
    message = (message or "").strip()
    if not message:
        yield history, message, "", gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
        return

    history = [*history, {"role": "user", "content": message}]
    yield history, "", "_Thinking..._", gr.update(visible=False), None, gr.update(), gr.update(), gr.update()

    try:
        result = client.chat(message, thread_id)
    except client.CopilotClientError as exc:
        history = [*history, {"role": "assistant", "content": f"⚠️ {exc}"}]
        yield history, "", f"Error: {exc}", gr.update(visible=False), None, gr.update(), gr.update(), gr.update()
        return

    trace_rows = format_trace(result.get("mcp_trace", []))
    citation_rows = format_citations(result.get("citations", []))
    similar_rows = format_similar_tickets(result.get("mcp_trace", []))

    if result.get("requires_confirmation"):
        pending_write = result.get("pending_write")
        tool_name = (pending_write or {}).get("name", "a write")
        history = [*history, {"role": "assistant", "content": f"This turn needs approval before I run `{tool_name}`. Review the draft on the right, then Approve or Reject."}]
        yield history, "", "Awaiting confirmation.", gr.update(visible=True), pending_write, trace_rows, citation_rows, similar_rows
        return

    answer = result.get("answer") or "(no answer text returned)"
    history = [*history, {"role": "assistant", "content": answer}]
    yield history, "", "", gr.update(visible=False), None, trace_rows, citation_rows, similar_rows


def resolve_confirmation(approved: bool, thread_id: str, pending_write: dict | None, history: list,
                          summary, description, status, priority, labels, asset_id, alarm_id, ticket_id,
                          resolution_notes):
    """Approve or reject a pending write and render the outcome.

    Args:
        approved (bool): True for Approve, False for Reject.
        thread_id (str): this session's conversation thread id.
        pending_write (dict | None): the pending write being decided, from state.
        history (list): the chatbot's current message list.
        summary, description, status, priority, labels, asset_id, alarm_id, ticket_id, resolution_notes:
            current (possibly edited) form field values.

    Returns:
        tuple: (history, status, ticket_group_visible, pending_write_state, trace_rows).
    """
    edited_args = build_edited_args(
        pending_write, summary, description, status, priority, labels, asset_id, alarm_id, ticket_id,
        resolution_notes,
    )
    try:
        result = client.confirm(thread_id, approved, edited_args=edited_args)
    except client.CopilotClientError as exc:
        history = [*history, {"role": "assistant", "content": f"⚠️ {exc}"}]
        return history, f"Error: {exc}", gr.update(visible=True), pending_write, gr.update()

    trace_rows = format_trace(result.get("mcp_trace", []))
    if not approved:
        message = "Rejected -- nothing was written."
    else:
        message = result.get("answer") or "Approved -- write executed."
    history = [*history, {"role": "assistant", "content": message}]
    return history, "", gr.update(visible=False), None, trace_rows


def refresh_ops_table(thread_filter: str | None) -> list[list]:
    """Read the audit trail and format it for the Ops tab table.

    Args:
        thread_filter (str | None): optional thread_id to restrict rows to.
            None on the very first demo.load(), before the textbox has a value.

    Returns:
        list[list]: formatted rows, matching OPS_HEADERS.
    """
    rows = read_audit_trail(thread_id=(thread_filter or "").strip() or None)
    return format_ops_rows(rows)


def restore_session(thread_id: str) -> tuple:
    """Rebuild the Copilot tab from the backend's stored state for a thread.

    Runs after every page load (a fresh tab, or a WebSocket reconnect that
    reset thread_id_state to LOAD_THREAD_ID_JS's restored value) so the UI
    reflects the backend's actual state instead of each component's
    construction-time default -- a resumed thread shows its real chat
    history/citations/trace, and a genuinely new thread (no prior state)
    comes back empty. This is also what fixes the trace/citations panels
    not resetting for a new thread: every load now explicitly sets them from
    backend truth rather than leaving whatever was last rendered in place.

    Args:
        thread_id (str): this session's conversation thread id.

    Returns:
        tuple: (chatbot_history, status, ticket_group_visible, pending_write_state,
            trace_rows, citation_rows, similar_ticket_rows).
    """
    if not thread_id:
        return [], "", gr.update(visible=False), None, [], [], []

    try:
        result = client.get_history(thread_id)
    except client.CopilotClientError as exc:
        return [], f"Error: {exc}", gr.update(visible=False), None, [], [], []

    history = [{"role": m["role"], "content": m["content"]} for m in result.get("messages", [])]
    trace_rows = format_trace(result.get("mcp_trace", []))
    citation_rows = format_citations(result.get("citations", []))
    similar_rows = format_similar_tickets(result.get("mcp_trace", []))

    if result.get("requires_confirmation"):
        pending_write = result.get("pending_write")
        return history, "Awaiting confirmation.", gr.update(visible=True), pending_write, trace_rows, citation_rows, similar_rows

    return history, "", gr.update(visible=False), None, trace_rows, citation_rows, similar_rows


with gr.Blocks(title="Incident and Ticket Enrichment Copilot") as demo:
    thread_id_state = gr.State("")
    pending_write_state = gr.State(None)

    gr.Markdown("# Incident and Ticket Enrichment Copilot")

    # Gradio layout nesting, not resource management -- can't be one `with`.
    with gr.Tab("Copilot"):  # noqa: SIM117
        with gr.Row():
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(label="Conversation", height=480)
                msg_box = gr.Textbox(placeholder="Ask about an alarm, asset, ticket, or documentation...", label="Message", lines=1)
                with gr.Row():
                    send_btn = gr.Button("Send", variant="primary")
                    new_conv_btn = gr.Button("New conversation")
                status_md = gr.Markdown("")
                thread_display = gr.Textbox(label="Thread ID", interactive=False)

            with gr.Column(scale=1):
                gr.Markdown("### Ticket Draft")
                with gr.Group(visible=False) as ticket_group:
                    ticket_mode_md = gr.Markdown()
                    summary_tb = gr.Textbox(label="Summary")
                    description_tb = gr.Textbox(label="Description", lines=3)
                    with gr.Row():
                        status_dd = gr.Dropdown(STATUS_CHOICES, label="Status", allow_custom_value=True)
                        priority_dd = gr.Dropdown(PRIORITY_CHOICES, label="Priority", allow_custom_value=True)
                    labels_tb = gr.Textbox(label="Labels (comma-separated)")
                    with gr.Row():
                        asset_id_tb = gr.Textbox(label="Asset ID")
                        alarm_id_tb = gr.Textbox(label="Alarm ID")
                    ticket_id_tb = gr.Textbox(label="Ticket ID (update_ticket only)", interactive=False)
                    resolution_notes_tb = gr.Textbox(label="Resolution Notes", lines=2)
                    with gr.Row():
                        approve_btn = gr.Button("Approve", variant="primary")
                        reject_btn = gr.Button("Reject", variant="stop")
                    with gr.Accordion("Raw pending_write", open=False):
                        pending_json_view = gr.JSON()

                gr.Markdown("### Similar Tickets")
                similar_tickets_df = gr.Dataframe(headers=SIMILAR_TICKETS_HEADERS, interactive=False, wrap=True, value=[])

                gr.Markdown("### Citations")
                citations_df = gr.Dataframe(headers=CITATION_HEADERS, interactive=False, wrap=True, value=[])

                gr.Markdown("### MCP Execution Trace")
                trace_df = gr.Dataframe(headers=TRACE_HEADERS, interactive=False, wrap=True, value=[])

    with gr.Tab("Ops"):
        gr.Markdown("### Audit Trail\nEvery MCP tool call and write-confirmation decision, from `audit_trail.sqlite3`.")
        with gr.Row():
            ops_thread_filter = gr.Textbox(label="Filter by thread_id (optional)", value="", scale=3)
            ops_refresh_btn = gr.Button("Refresh", scale=1)
        ops_df = gr.Dataframe(headers=OPS_HEADERS, interactive=False, wrap=True, value=[])
        ops_timer = gr.Timer(5)

    # Populate the ticket draft form whenever pending_write_state changes.
    def render_pending(pending_write):
        fields = ticket_fields_from_pending(pending_write)
        mode_label = {
            "create": "**Pending approval: create_ticket**",
            "update": "**Pending approval: update_ticket**",
            "unknown": "**Pending approval**",
        }[fields["mode"]]
        return (
            mode_label,
            gr.update(value=fields["summary"], visible=fields["is_create"]),
            gr.update(value=fields["description"], visible=fields["is_create"]),
            gr.update(value=fields["status"]),
            gr.update(value=fields["priority"]),
            gr.update(value=fields["labels"]),
            gr.update(value=fields["asset_id"], visible=fields["is_create"]),
            gr.update(value=fields["alarm_id"], visible=fields["is_create"]),
            gr.update(value=fields["ticket_id"], visible=fields["is_update"]),
            gr.update(value=fields["resolution_notes"], visible=fields["is_update"]),
            pending_write,
        )

    pending_write_state.change(
        render_pending,
        inputs=[pending_write_state],
        outputs=[
            ticket_mode_md, summary_tb, description_tb, status_dd, priority_dd, labels_tb, asset_id_tb, alarm_id_tb,
            ticket_id_tb, resolution_notes_tb, pending_json_view,
        ],
    )

    demo.load(fn=None, inputs=None, js=FORCE_DARK_JS)
    load_thread_event = demo.load(fn=None, inputs=None, outputs=[thread_id_state, thread_display], js=LOAD_THREAD_ID_JS)
    load_thread_event.then(
        restore_session,
        inputs=[thread_id_state],
        outputs=[chatbot, status_md, ticket_group, pending_write_state, trace_df, citations_df, similar_tickets_df],
    )

    send_outputs = [chatbot, msg_box, status_md, ticket_group, pending_write_state, trace_df, citations_df, similar_tickets_df]
    send_btn.click(send_message, inputs=[msg_box, chatbot, thread_id_state], outputs=send_outputs)
    msg_box.submit(send_message, inputs=[msg_box, chatbot, thread_id_state], outputs=send_outputs)

    new_conv_btn.click(
        new_conversation,
        inputs=None,
        outputs=[chatbot, thread_id_state, thread_display, status_md, ticket_group, pending_write_state, trace_df, citations_df, similar_tickets_df],
    )
    new_conv_btn.click(fn=None, inputs=None, outputs=[thread_id_state, thread_display], js=NEW_THREAD_ID_JS)

    confirm_inputs = [
        thread_id_state, pending_write_state, chatbot,
        summary_tb, description_tb, status_dd, priority_dd, labels_tb, asset_id_tb, alarm_id_tb, ticket_id_tb,
        resolution_notes_tb,
    ]
    confirm_outputs = [chatbot, status_md, ticket_group, pending_write_state, trace_df]
    approve_btn.click(lambda *args: resolve_confirmation(True, *args), inputs=confirm_inputs, outputs=confirm_outputs)
    reject_btn.click(lambda *args: resolve_confirmation(False, *args), inputs=confirm_inputs, outputs=confirm_outputs)

    ops_refresh_btn.click(refresh_ops_table, inputs=[ops_thread_filter], outputs=[ops_df])
    ops_timer.tick(refresh_ops_table, inputs=[ops_thread_filter], outputs=[ops_df])
    demo.load(refresh_ops_table, inputs=[ops_thread_filter], outputs=[ops_df])


if __name__ == "__main__":
    settings = get_settings()
    demo.queue().launch(server_name="0.0.0.0", server_port=settings.server_port)
