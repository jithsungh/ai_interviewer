from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.ai.llm.contracts import LLMRequest
from app.ai.llm.provider_factory import ProviderFactory
from app.config.settings import settings

logger = logging.getLogger(__name__)

_ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}


class PracticePrepGenerator:
    def __init__(self) -> None:
        self._provider = None
        try:
            self._provider = ProviderFactory.create_text_provider()
        except Exception as exc:
            logger.warning("PracticePrepGenerator running in DB-only mode: %s", exc)

    def generate_flashcards(
        self,
        *,
        role: str,
        industry: str,
        source_questions: Sequence[Dict[str, Any]],
        card_count: int,
        question_type: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], str, Optional[str], Optional[str]]:
        normalized_sources = [q for q in source_questions if isinstance(q, dict) and q.get("id")]
        if not normalized_sources:
            raise RuntimeError("No source questions available to build an interview prep deck")

        limit = min(max(card_count, 1), len(normalized_sources))
        selected_sources = normalized_sources[:limit]

        if self._provider is None:
            return self._build_db_cards(selected_sources, role, industry), "db", None, None

        prompt = (
            "You are an expert interview coach. Create concise interview prep flashcards using ONLY the provided "
            "source questions from the database. Do not invent new questions. Return ONLY valid JSON array with exactly "
            f"{limit} objects. Each object must follow this schema: "
            '{"sourceQuestionId": number, "topic": string, "difficulty": "Easy"|"Medium"|"Hard", '
            '"question": string, "answer": string, "tags": [string, string], "hint": string}. '
            "Keep answers to 2-3 short sentences. Use the role and industry context to tailor wording, but preserve "
            "the original source meaning. "
            f"Role: {role}. Industry: {industry}. "
            f"Preferred question type: {question_type or 'mixed'}. Preferred difficulty: {difficulty or 'mixed'}. "
            f"Source questions JSON: {json.dumps(selected_sources, ensure_ascii=False)}"
        )
        req = LLMRequest(
            prompt=prompt,
            model=settings.llm.llm_model_question_generation,
            temperature=0.65,
            max_tokens=1800,
            json_mode=True,
            timeout_seconds=35,
        )

        try:
            response = _run_async(self._provider.generate_structured(req))
            if response.success and response.text:
                parsed = _extract_json(response.text)
                normalized = self._normalize_flashcards(parsed, selected_sources, role, industry)
                if len(normalized) >= limit:
                    return normalized[:limit], "ai", self._provider.get_provider_name(), req.model
                logger.warning("Practice flashcards could not be normalized; falling back to DB-backed cards")
            else:
                logger.warning(
                    "Practice flashcard generation failed: %s",
                    response.error.message if response.error else "unknown error",
                )
        except Exception as exc:
            logger.warning("Practice flashcard generation failed, using DB-backed cards: %s", exc)

        return self._build_db_cards(selected_sources, role, industry), "db", None, None

    def _build_db_cards(
        self,
        source_questions: Sequence[Dict[str, Any]],
        role: str,
        industry: str,
    ) -> List[Dict[str, Any]]:
        cards: List[Dict[str, Any]] = []
        for item in source_questions:
            raw_difficulty = str(item.get("difficulty") or "medium").lower()
            difficulty = raw_difficulty if raw_difficulty in _ALLOWED_DIFFICULTIES else "medium"
            question_text = str(item.get("question_text") or item.get("title") or "").strip()
            answer_text = str(item.get("answer_text") or "").strip()
            topic = str(item.get("question_type") or role).replace("_", " ").title()
            if not question_text:
                continue
            cards.append(
                {
                    "sourceQuestionId": int(item["id"]),
                    "topic": topic,
                    "difficulty": difficulty.capitalize(),
                    "question": question_text,
                    "answer": answer_text or f"Focus on the core concept behind {topic.lower()} in {industry}.",
                    "tags": [str(item.get("question_type") or "practice"), industry, role][:3],
                    "hint": f"Connect the question to {industry} expectations for a {role} role.",
                }
            )
        return cards

    def _normalize_flashcards(
        self,
        payload: Any,
        source_questions: Sequence[Dict[str, Any]],
        role: str,
        industry: str,
    ) -> List[Dict[str, Any]]:
        if isinstance(payload, dict):
            for key in ["flashcards", "cards", "items", "data", "results"]:
                if isinstance(payload.get(key), list):
                    payload = payload[key]
                    break

        if not isinstance(payload, list):
            logger.warning("Expected list for flashcards but got %s", type(payload).__name__)
            return []

        source_map = {int(item["id"]): item for item in source_questions if item.get("id") is not None}
        normalized: List[Dict[str, Any]] = []
        for item in payload[: len(source_map) or len(payload)]:
            if not isinstance(item, dict):
                continue
            source_id = _to_int(item.get("sourceQuestionId"), -1)
            if source_id not in source_map:
                continue
            question = str(item.get("question") or "").strip()
            answer = str(item.get("answer") or "").strip()
            topic = str(item.get("topic") or source_map[source_id].get("question_type") or role).strip()
            difficulty = str(item.get("difficulty") or source_map[source_id].get("difficulty") or "Medium").strip()
            if difficulty.lower() not in {"easy", "medium", "hard"}:
                difficulty = source_map[source_id].get("difficulty") or "Medium"
            tags = item.get("tags") if isinstance(item.get("tags"), list) else []
            hint = str(item.get("hint") or "").strip() or None
            if not question or not answer:
                continue
            normalized.append(
                {
                    "sourceQuestionId": source_id,
                    "topic": topic,
                    "difficulty": difficulty.capitalize(),
                    "question": question,
                    "answer": answer,
                    "tags": [str(tag).strip() for tag in tags if str(tag).strip()][:4],
                    "hint": hint,
                }
            )
        return normalized


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result(timeout=40)
        return asyncio.run(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _extract_json(text: str) -> Any:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        list_match = re.search(r"\[[\s\S]*\]", cleaned)
        if list_match:
            return json.loads(list_match.group(0))
        obj_match = re.search(r"\{[\s\S]*\}", cleaned)
        if obj_match:
            return json.loads(obj_match.group(0))
        raise


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
