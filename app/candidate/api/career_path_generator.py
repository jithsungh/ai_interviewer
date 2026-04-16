from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.ai.llm.contracts import LLMRequest
from app.ai.llm.provider_factory import ProviderFactory
from app.config.settings import settings

logger = logging.getLogger(__name__)

_LEVELS = ["INTERN", "JUNIOR", "SENIOR", "EXECUTIVE"]
_ICON_DEFAULT = "engineering"
_ALLOWED_ICONS = {
    "smart_toy",
    "account_balance",
    "security",
    "school",
    "shopping_cart",
    "local_hospital",
    "sports_esports",
    "currency_bitcoin",
    "engineering",
    "analytics",
}

class CareerPathGenerator:
    def __init__(self) -> None:
        self._provider = None
        try:
            self._provider = ProviderFactory.create_text_provider()
        except Exception as exc:
            logger.warning("CareerPathGenerator falling back to deterministic mode: %s", exc)

    def generate_market_insights(
        self,
        industry: str,
        seniority: str,
    ) -> Tuple[List[Dict[str, Any]], str, Optional[str], Optional[str]]:
        if self._provider is None:
            raise RuntimeError(
                "Career path generation requires a configured LLM provider. Set DEFAULT_LLM_PROVIDER and the matching API key."
            )

        if self._provider is not None:
            try:
                prompt = (
                    "You are a career market analyst. Return ONLY valid JSON array with exactly 5 objects. "
                    "Schema: {\"role\": str, \"industryTag\": str, \"icon\": one of "
                    "smart_toy|account_balance|security|school|shopping_cart|local_hospital|sports_esports|"
                    "currency_bitcoin|engineering|analytics, \"skills\": [str, str], \"minPackage\": number, "
                    "\"maxPackage\": number, \"growth\": int(5-30), \"trend\": \"up\"|\"stable\"|\"down\"}. "
                    f"Generate for industry '{industry}' and seniority '{seniority}' for Indian market salaries in LPA."
                )
                req = LLMRequest(
                    prompt=prompt,
                    model=settings.llm.llm_model_question_generation,
                    temperature=0.5,
                    max_tokens=1200,
                    json_mode=True,
                    timeout_seconds=30,
                )
                response = _run_async(self._provider.generate_structured(req))
                if response.success and response.text:
                    parsed = _extract_json(response.text)
                    logger.info(f"LLM parsed response for insights: {parsed}")
                    normalized = self._normalize_insights(parsed, industry, seniority)
                    logger.info(f"Normalized insights: {normalized}")
                    if normalized:
                        return normalized, "ai", self._provider.get_provider_name(), req.model
                    raise RuntimeError(f"Career path insights response could not be normalized. Parsed: {parsed}")
                raise RuntimeError(
                    response.error.message if response.error else "Career path insight generation failed"
                )
            except Exception as exc:
                logger.error("AI market insight generation failed: %s", exc)
                raise

    def generate_role_roadmap(
        self,
        role: str,
        industry: str,
    ) -> Tuple[List[Dict[str, Any]], str, Optional[str], Optional[str]]:
        if self._provider is None:
            raise RuntimeError(
                "Career path generation requires a configured LLM provider. Set DEFAULT_LLM_PROVIDER and the matching API key."
            )

        if self._provider is not None:
            try:
                prompt = (
                    "You are a career progression expert. Return ONLY valid JSON array with exactly 4 objects for levels "
                    "INTERN, JUNIOR, SENIOR, EXECUTIVE. Schema: {\"level\": 1-4, \"levelLabel\": one of "
                    "INTERN|JUNIOR|SENIOR|EXECUTIVE, \"roleTitle\": str, \"requiredCourses\": [str, str, str], "
                    "\"keyLearning\": str, \"certification\": str}. "
                    f"Generate roadmap for role '{role}' in industry '{industry}'."
                )
                req = LLMRequest(
                    prompt=prompt,
                    model=settings.llm.llm_model_question_generation,
                    temperature=0.4,
                    max_tokens=1400,
                    json_mode=True,
                    timeout_seconds=30,
                )
                response = _run_async(self._provider.generate_structured(req))
                if response.success and response.text:
                    parsed = _extract_json(response.text)
                    normalized = self._normalize_roadmap(parsed, role, industry)
                    if normalized:
                        return normalized, "ai", self._provider.get_provider_name(), req.model
                    raise RuntimeError("Career path roadmap response could not be normalized")
                raise RuntimeError(
                    response.error.message if response.error else "Career path roadmap generation failed"
                )
            except Exception as exc:
                logger.error("AI roadmap generation failed: %s", exc)
                raise

    def _normalize_insights(self, payload: Any, industry: str, seniority: str) -> List[Dict[str, Any]]:
        # Handle case where LLM wraps the array in an object with a key like "roles", "insights", etc.
        if isinstance(payload, dict):
            for key in ["roles", "insights", "data", "results", "items"]:
                if key in payload and isinstance(payload[key], list):
                    payload = payload[key]
                    break
        
        if not isinstance(payload, list):
            logger.warning(f"Expected array but got {type(payload).__name__}: {payload}")
            return []

        normalized: List[Dict[str, Any]] = []
        for idx, item in enumerate(payload[:5]):
            if not isinstance(item, dict):
                logger.debug(f"Item {idx} is not a dict: {item}")
                continue
            
            role = str(item.get("role") or "").strip()
            if not role:
                logger.debug(f"Item {idx} has no role field: {item}")
                continue

            icon = str(item.get("icon") or _ICON_DEFAULT).strip()
            if icon not in _ALLOWED_ICONS:
                icon = _ICON_DEFAULT
            skills = item.get("skills") if isinstance(item.get("skills"), list) else []
            trend = str(item.get("trend") or "stable").lower()
            if trend not in {"up", "stable", "down"}:
                trend = "stable"

            min_package = _to_int(item.get("minPackage"), 0)
            max_package = _to_int(item.get("maxPackage"), min_package)
            if max_package < min_package:
                max_package = min_package

            growth = min(max(_to_int(item.get("growth"), 0), 5), 30)

            normalized.append(
                {
                    "role": role,
                    "industryTag": str(item.get("industryTag") or industry).strip(),
                    "icon": icon,
                    "skills": [str(skill).strip() for skill in skills][:3],
                    "minPackage": min_package,
                    "maxPackage": max_package,
                    "growth": growth,
                    "trend": trend,
                }
            )

        if not normalized:
            logger.warning(f"No valid insights found in payload. Original: {payload}")
        return normalized[:5]

    def _normalize_roadmap(self, payload: Any, role: str, industry: str) -> List[Dict[str, Any]]:
        # Handle case where LLM wraps the array in an object
        if isinstance(payload, dict):
            for key in ["roadmap", "steps", "levels", "data", "results", "items"]:
                if key in payload and isinstance(payload[key], list):
                    payload = payload[key]
                    break
        
        if not isinstance(payload, list):
            logger.warning(f"Expected array for roadmap but got {type(payload).__name__}: {payload}")
            return []
        
        if len(payload) < 4:
            logger.warning(f"Expected at least 4 levels but got {len(payload)}")
            return []
        
        normalized: List[Dict[str, Any]] = []

        for idx in range(4):
            item = payload[idx] if idx < len(payload) and isinstance(payload[idx], dict) else {}
            level_label = str(item.get("levelLabel") or _LEVELS[idx]).upper()
            if level_label not in _LEVELS:
                logger.warning(f"Level {idx}: Invalid levelLabel '{level_label}', expected one of {_LEVELS}")
                return []

            courses = item.get("requiredCourses") if isinstance(item.get("requiredCourses"), list) else []
            role_title = str(item.get("roleTitle") or "").strip()
            key_learning = str(item.get("keyLearning") or "").strip()
            certification = str(item.get("certification") or "").strip()
            
            if not role_title or not key_learning or not certification or len(courses) < 1:
                logger.warning(
                    f"Level {idx} missing required fields. "
                    f"roleTitle={bool(role_title)}, keyLearning={bool(key_learning)}, "
                    f"certification={bool(certification)}, courses={len(courses)}"
                )
                return []

            normalized.append(
                {
                    "level": idx + 1,
                    "levelLabel": level_label,
                    "roleTitle": role_title,
                    "requiredCourses": [str(course).strip() for course in courses][:3],
                    "keyLearning": key_learning,
                    "certification": certification,
                }
            )

        return normalized


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result(timeout=35)
        return asyncio.run(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _extract_json(text: str) -> Any:
    if not text:
        raise ValueError("Empty text provided to _extract_json")
    
    cleaned = text.strip()
    
    # Remove markdown code blocks
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    
    logger.debug(f"Cleaned JSON text: {cleaned[:200]}")

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.debug(f"Direct JSON parse failed: {e}")
        # Try to extract array
        list_match = re.search(r"\[[\s\S]*\]", cleaned)
        if list_match:
            try:
                result = json.loads(list_match.group(0))
                logger.debug("Successfully extracted array from response")
                return result
            except json.JSONDecodeError as e2:
                logger.debug(f"Array extraction failed: {e2}")
        
        # Try to extract object
        obj_match = re.search(r"\{[\s\S]*\}", cleaned)
        if obj_match:
            try:
                result = json.loads(obj_match.group(0))
                logger.debug("Successfully extracted object from response")
                return result
            except json.JSONDecodeError as e2:
                logger.debug(f"Object extraction failed: {e2}")
        
        logger.error(f"Failed to extract JSON. Original text: {text[:500]}, Cleaned: {cleaned[:500]}")
        raise


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
