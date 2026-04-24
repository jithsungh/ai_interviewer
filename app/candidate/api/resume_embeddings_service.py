"""
Resume Embeddings Service

Generates embeddings for resumes using the configured embedding provider.
Falls back to a deterministic hashed embedding when the provider is unavailable.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import re
from typing import Any, Dict, List, Optional

from app.ai.llm import EmbeddingRequest
from app.ai.llm.provider_factory import ProviderFactory
from app.config import settings as global_settings

logger = logging.getLogger(__name__)


class ResumeEmbeddingsService:
    """Service for generating resume embeddings."""

    def __init__(self):
        self.settings = global_settings
        self.embedding_provider = None
        self.embedding_dimension = 768

        if self.settings is not None:
            try:
                self.embedding_provider = ProviderFactory.create_embedding_provider(
                    service_url=self.settings.llm.embedding_model_url,
                )
                self.embedding_dimension = self.embedding_provider.get_embedding_dimension(
                    getattr(self.settings.llm, "default_embedding_model", "all-mpnet-base-v2")
                )
            except Exception as e:
                logger.warning(f"Failed to initialize embedding provider: {e}")
                self.embedding_provider = None

    def generate_embeddings(
        self,
        parsed_text: str,
        structured_json: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate embeddings for a resume.
        """
        embeddings_dict: Dict[str, Any] = {}

        if parsed_text:
            embeddings_dict["full_resume"] = self._get_embedding(parsed_text)

        if structured_json:
            section_embeddings = self._generate_section_embeddings(structured_json)
            if section_embeddings:
                embeddings_dict["sections"] = section_embeddings

        if not embeddings_dict:
            return None

        return embeddings_dict

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text using provider or fallback."""
        if not text:
            return []

        provider_embedding = self._get_provider_embedding(text)
        if provider_embedding:
            return provider_embedding

        return self._hash_embedding(text)

    def _get_provider_embedding(self, text: str) -> Optional[List[float]]:
        if not self.embedding_provider:
            return None

        try:
            request = EmbeddingRequest(
                text=text[:8000],
                model=getattr(self.settings.llm, "default_embedding_model", "all-mpnet-base-v2") if self.settings else "all-mpnet-base-v2",
                timeout_seconds=self.settings.llm.embedding_timeout_seconds if self.settings else 30,
            )
            response = asyncio.run(self.embedding_provider.generate_embedding(request))
            if response.success and response.embedding:
                return response.embedding
        except RuntimeError:
            logger.warning("Embedding call skipped because an event loop is already running")
        except Exception as e:
            logger.warning(f"Embedding provider failed, falling back to hash embeddings: {e}")
        return None

    def _generate_section_embeddings(
        self,
        structured_json: Dict[str, Any],
    ) -> Optional[Dict[str, List[float]]]:
        section_texts = self._extract_section_texts(structured_json)
        embeddings = {}
        for section_name, text in section_texts.items():
            if text:
                embeddings[section_name] = self._get_embedding(text)
        return embeddings if embeddings else None

    def _extract_section_texts(self, structured_json: Dict[str, Any]) -> Dict[str, str]:
        sections: Dict[str, str] = {}

        summary = structured_json.get("summary")
        if isinstance(summary, str) and summary.strip():
            sections["summary"] = summary.strip()

        if isinstance(structured_json.get("experience"), list) and structured_json["experience"]:
            exp_text = "\n".join([
                f"{e.get('title', '')} at {e.get('company', '')} - {e.get('description', '')}"
                for e in structured_json["experience"] if isinstance(e, dict)
            ])
            if exp_text.strip():
                sections["experience"] = exp_text

        if isinstance(structured_json.get("education"), list) and structured_json["education"]:
            edu_text = "\n".join([
                f"{e.get('degree', '')} in {e.get('field', '')} from {e.get('school', '')}"
                for e in structured_json["education"] if isinstance(e, dict)
            ])
            if edu_text.strip():
                sections["education"] = edu_text

        if isinstance(structured_json.get("skills"), list) and structured_json["skills"]:
            skills_text = "\n".join([
                f"{s.get('category', '')}: {', '.join(s.get('items', []))}"
                for s in structured_json["skills"] if isinstance(s, dict)
            ])
            if skills_text.strip():
                sections["skills"] = skills_text

        if isinstance(structured_json.get("certifications"), list) and structured_json["certifications"]:
            cert_text = "\n".join([
                f"{c.get('name', '')} from {c.get('issuer', '')}"
                for c in structured_json["certifications"] if isinstance(c, dict)
            ])
            if cert_text.strip():
                sections["certifications"] = cert_text

        if isinstance(structured_json.get("projects"), list) and structured_json["projects"]:
            proj_text = "\n".join([
                f"{p.get('title', '')}: {p.get('description', '')} ({', '.join(p.get('technologies', []))})"
                for p in structured_json["projects"] if isinstance(p, dict)
            ])
            if proj_text.strip():
                sections["projects"] = proj_text

        return sections

    def _hash_embedding(self, text: str, dimensions: Optional[int] = None) -> List[float]:
        """Deterministic local fallback embedding using hashed token counts."""
        dims = dimensions or self.embedding_dimension or 768
        vector = [0.0] * dims

        tokens = re.findall(r"[A-Za-z0-9_+#.-]+", text.lower())
        if not tokens:
            return vector

        for token in tokens:
            idx = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % dims
            vector[idx] += 1.0

        # Add a few bigram signals for slightly better locality.
        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]} {tokens[i + 1]}"
            idx = int(hashlib.md5(bigram.encode("utf-8")).hexdigest(), 16) % dims
            vector[idx] += 0.5

        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [round(v / norm, 6) for v in vector]


# Singleton instance
_resume_embeddings_service: Optional[ResumeEmbeddingsService] = None


def get_resume_embeddings_service() -> ResumeEmbeddingsService:
    """Get or create the resume embeddings service."""
    global _resume_embeddings_service
    if _resume_embeddings_service is None:
        _resume_embeddings_service = ResumeEmbeddingsService()
    return _resume_embeddings_service
