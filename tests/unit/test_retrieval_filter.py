"""Unit tests for rag/retrieval/retriever.py's _build_filter -- pure
translation from a RetrievalQuery's asset_id/doc_type into a Qdrant Filter.
No network, no Qdrant, no embeddings.
"""

from qdrant_client.models import FieldCondition, MatchValue

from rag.retrieval.models import RetrievalQuery
from rag.retrieval.retriever import _build_filter


class TestBuildFilter:
    def test_no_asset_id_or_doc_type_returns_none(self):
        query = RetrievalQuery(query="high vibration alarm")
        assert _build_filter(query) is None

    def test_asset_id_only_builds_single_condition_on_assets_field(self):
        query = RetrievalQuery(query="high vibration alarm", asset_id="AST-0001")
        filt = _build_filter(query)
        assert filt is not None
        assert filt.must == [FieldCondition(key="assets", match=MatchValue(value="AST-0001"))]

    def test_doc_type_only_builds_single_condition_on_doc_type_field(self):
        query = RetrievalQuery(query="high vibration alarm", doc_type="troubleshooting_manual")
        filt = _build_filter(query)
        assert filt is not None
        assert filt.must == [FieldCondition(key="doc_type", match=MatchValue(value="troubleshooting_manual"))]

    def test_both_asset_id_and_doc_type_build_both_conditions_in_order(self):
        query = RetrievalQuery(query="q", asset_id="AST-0002", doc_type="safety_instruction")
        filt = _build_filter(query)
        assert filt is not None
        assert filt.must == [
            FieldCondition(key="assets", match=MatchValue(value="AST-0002")),
            FieldCondition(key="doc_type", match=MatchValue(value="safety_instruction")),
        ]

    def test_empty_string_asset_id_is_falsy_but_still_none_check_based(self):
        # asset_id defaults to None, not "" -- explicitly passing None must
        # behave identically to omitting it (no condition added).
        query = RetrievalQuery(query="q", asset_id=None, doc_type=None)
        assert _build_filter(query) is None
