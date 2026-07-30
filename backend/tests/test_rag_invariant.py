"""Unit tests: RAG must never call the LLM without retrieved evidence (P6-DB-003)."""

from __future__ import annotations

import unittest
import uuid
from unittest.mock import MagicMock, patch

from app.core.constants import DatasetStatus
from app.models import Dataset, Report
from app.services.research import ResearchError, run_research


class _FakeDB:
    """Minimal session stand-in for research flow."""

    def __init__(self, dataset: Dataset):
        self.dataset = dataset
        self.reports: dict[uuid.UUID, Report] = {}
        self.added: list[object] = []

    def get(self, model, obj_id):  # noqa: ANN001
        if model is Dataset and obj_id == self.dataset.id:
            return self.dataset
        if model is Report and obj_id in self.reports:
            return self.reports[obj_id]
        return None

    def add(self, obj) -> None:  # noqa: ANN001
        self.added.append(obj)
        if isinstance(obj, Report):
            self.reports[obj.id] = obj

    def commit(self) -> None:
        return None

    def refresh(self, obj) -> None:  # noqa: ANN001
        return None

    def rollback(self) -> None:
        return None

    def scalar(self, _stmt):  # noqa: ANN001
        return None


class RagInvariantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset = Dataset(
            id=uuid.uuid4(),
            name="test",
            source="csv",
            conversation_count=1,
            status=DatasetStatus.READY,
        )
        self.db = _FakeDB(self.dataset)

    @patch("app.services.research.write_log")
    @patch("app.services.research.get_effective_settings", return_value={"top_k": 12, "ai_provider": "openrouter", "ai_model": "test"})
    @patch("app.services.research.chat")
    @patch("app.services.research._call_llm")
    @patch("app.services.research.retrieve_similar", return_value=[])
    def test_empty_retrieval_never_calls_llm(
        self,
        _retrieve: MagicMock,
        call_llm: MagicMock,
        chat: MagicMock,
        _settings: MagicMock,
        _log: MagicMock,
    ) -> None:
        report = run_research(
            self.db,  # type: ignore[arg-type]
            dataset_id=self.dataset.id,
            question="What are the most common delivery pain points?",
        )
        self.assertEqual(report.status, "failed")
        self.assertIn("Insufficient evidence", report.error_message or "")
        call_llm.assert_not_called()
        chat.assert_not_called()

    @patch("app.services.research.write_log")
    @patch("app.services.research.get_effective_settings", return_value={"top_k": 12, "ai_provider": "openrouter", "ai_model": "test"})
    @patch("app.services.research.chat")
    @patch("app.services.research._call_llm")
    @patch(
        "app.services.research.retrieve_similar",
        return_value=[
            {
                "chunk_id": str(uuid.uuid4()),
                "conversation_id": str(uuid.uuid4()),
                "content": "unrelated",
                "distance": 0.99,
                "source": None,
                "url": None,
            }
        ],
    )
    def test_low_relevance_never_calls_llm(
        self,
        _retrieve: MagicMock,
        call_llm: MagicMock,
        chat: MagicMock,
        _settings: MagicMock,
        _log: MagicMock,
    ) -> None:
        report = run_research(
            self.db,  # type: ignore[arg-type]
            dataset_id=self.dataset.id,
            question="What are the most common delivery pain points?",
        )
        self.assertEqual(report.status, "failed")
        self.assertIn("not relevant", (report.error_message or "").lower())
        call_llm.assert_not_called()
        chat.assert_not_called()

    def test_empty_question_raises_before_report(self) -> None:
        with self.assertRaises(ResearchError) as ctx:
            run_research(
                self.db,  # type: ignore[arg-type]
                dataset_id=self.dataset.id,
                question="   ",
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(len(self.db.reports), 0)

    @patch("app.services.research.write_log")
    @patch("app.services.research.get_effective_settings", return_value={"top_k": 12, "ai_provider": "openrouter", "ai_model": "test"})
    @patch("app.services.research.chat")
    @patch("app.services.research._call_llm")
    @patch("app.services.research.retrieve_similar")
    def test_out_of_scope_grocery_list_never_calls_llm(
        self,
        retrieve: MagicMock,
        call_llm: MagicMock,
        chat: MagicMock,
        _settings: MagicMock,
        _log: MagicMock,
    ) -> None:
        from app.services.research import is_out_of_scope_question

        self.assertTrue(is_out_of_scope_question("Can you create a grocery list for me?"))
        report = run_research(
            self.db,  # type: ignore[arg-type]
            dataset_id=self.dataset.id,
            question="Can you create a grocery list for me please?",
        )
        self.assertEqual(report.status, "completed")
        self.assertIn("only meant to analyze", (report.executive_summary or "").lower())
        self.assertEqual(report.evidence, [])
        retrieve.assert_not_called()
        call_llm.assert_not_called()
        chat.assert_not_called()

    def test_in_scope_research_question_not_flagged(self) -> None:
        from app.services.research import is_out_of_scope_question

        self.assertFalse(
            is_out_of_scope_question(
                "What are the most common delivery pain points in customer reviews?"
            )
        )


if __name__ == "__main__":
    unittest.main()
