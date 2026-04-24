from unittest.mock import MagicMock

import pytest

from app.candidate.api.service import CandidateService
from app.shared.errors import ValidationError as AppValidationError


@pytest.mark.unit
class TestPracticeFlashcardsFallback:
    def _build_service(self) -> CandidateService:
        service = CandidateService.__new__(CandidateService)
        service._repo = MagicMock()
        service._practice_generator = MagicMock()
        service._question_generation_service = MagicMock()
        service._to_practice_deck_response = lambda deck: deck
        return service

    def test_uses_direct_generation_when_pool_is_empty(self):
        service = self._build_service()

        service._repo.get_active_practice_deck.return_value = None
        service._repo.get_practice_question_pool.return_value = []
        service._generate_and_persist_practice_questions = MagicMock(
            return_value=[
                {
                    "id": 101,
                    "question_text": "What is CAP theorem?",
                    "answer_text": "Consistency, Availability, Partition tolerance tradeoffs.",
                    "question_type": "technical",
                    "difficulty": "medium",
                    "estimated_time_minutes": 5,
                    "completed": False,
                }
            ]
        )
        service._practice_generator.generate_flashcards.return_value = (
            [
                {
                    "question": "What is CAP theorem?",
                    "answer": "Consistency, Availability, Partition tolerance tradeoffs.",
                    "hint": "Think distributed systems",
                    "sourceQuestionId": 101,
                }
            ],
            "ai",
            "groq",
            "llama",
        )
        service._repo.create_active_practice_deck.return_value = {
            "deck_id": 9,
            "role": "Backend Engineer",
            "industry": "Fintech",
            "question_type": "technical",
            "difficulty": "medium",
            "card_count": 1,
            "source_question_ids": [101],
            "flashcards": [
                {
                    "question": "What is CAP theorem?",
                    "answer": "Consistency, Availability, Partition tolerance tradeoffs.",
                    "hint": "Think distributed systems",
                    "sourceQuestionId": 101,
                }
            ],
            "bookmarked_indices": [],
            "mastered_indices": [],
            "current_card_index": 0,
            "progress_percent": 0,
            "is_active": True,
            "generation_source": "direct_generation",
            "model_provider": "groq",
            "model_name": "llama",
            "created_at": None,
            "updated_at": None,
        }

        result = service.generate_practice_flashcards(
            user_id=77,
            role="Backend Engineer",
            industry="Fintech",
            card_count=1,
            question_type="technical",
            difficulty="medium",
            use_cached=False,
        )

        assert result["generation_source"] == "direct_generation"
        service._generate_and_persist_practice_questions.assert_called_once()
        service._repo.create_active_practice_deck.assert_called_once()

    def test_keeps_default_source_when_pool_exists(self):
        service = self._build_service()

        service._repo.get_active_practice_deck.return_value = None
        service._repo.get_practice_question_pool.return_value = [
            {
                "id": 11,
                "question_text": "Explain indexing in SQL.",
                "answer_text": "Indexes improve lookup by reducing scans.",
                "question_type": "technical",
                "difficulty": "easy",
                "estimated_time_minutes": 5,
                "completed": False,
            }
        ]
        service._generate_and_persist_practice_questions = MagicMock(return_value=[])
        service._practice_generator.generate_flashcards.return_value = (
            [
                {
                    "question": "Explain indexing in SQL.",
                    "answer": "Indexes improve lookup by reducing scans.",
                    "hint": "Think B-tree",
                    "sourceQuestionId": 11,
                }
            ],
            "db",
            None,
            None,
        )
        service._repo.create_active_practice_deck.return_value = {
            "deck_id": 10,
            "generation_source": "db",
            "flashcards": [
                {
                    "question": "Explain indexing in SQL.",
                    "answer": "Indexes improve lookup by reducing scans.",
                    "hint": "Think B-tree",
                    "sourceQuestionId": 11,
                }
            ],
            "created_at": None,
            "updated_at": None,
        }

        result = service.generate_practice_flashcards(
            user_id=77,
            role="Backend Engineer",
            industry="Fintech",
            card_count=1,
            question_type="technical",
            difficulty="easy",
            use_cached=False,
        )

        assert result["generation_source"] == "db"
        service._generate_and_persist_practice_questions.assert_not_called()

    def test_raises_validation_when_pool_and_generation_are_empty(self):
        service = self._build_service()

        service._repo.get_active_practice_deck.return_value = None
        service._repo.get_practice_question_pool.return_value = []
        service._generate_and_persist_practice_questions = MagicMock(return_value=[])

        with pytest.raises(AppValidationError, match="No practice questions are available"):
            service.generate_practice_flashcards(
                user_id=77,
                role="Backend Engineer",
                industry="Fintech",
                card_count=2,
                question_type="technical",
                difficulty="medium",
                use_cached=False,
            )
