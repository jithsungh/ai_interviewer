"""
Resume Analysis Service

Handles LLM-based resume analysis and ATS scoring.
Generates structured JSON, feedback, and ATS compatibility scores.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.ai.llm import LLMRequest
from app.ai.llm.provider_factory import ProviderFactory
from app.config import settings as global_settings

logger = logging.getLogger(__name__)


class ResumeAnalysisService:
    """Service for LLM-based resume analysis."""

    def __init__(self):
        self.settings = global_settings
        self.llm_provider = None
        self.model_name = None

        if self.settings is not None:
            try:
                self.llm_provider = ProviderFactory.create_text_provider()
                self.model_name = self._select_model_name()
            except Exception as e:
                logger.warning(f"Failed to initialize LLM provider: {e}")
                self.llm_provider = None
                self.model_name = None

    def analyze_resume(
        self,
        parsed_text: str,
        file_name: Optional[str] = None,
        extracted_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze resume using LLM with heuristic fallback.

        Returns:
            Dict with structured_json, llm_feedback, ats_score, ats_feedback
        """
        structured_json = None
        llm_feedback = None
        ats_score = None
        ats_feedback = None
        analysis_source = "heuristic"

        heuristic_structured = self._build_heuristic_structured_json(parsed_text, extracted_data, file_name)

        compact_text = (parsed_text or "")[:4500]

        if self.llm_provider:
            try:
                structured_json = self._generate_structured_json(compact_text, extracted_data, file_name)
                analysis_source = "llm" if structured_json is not None else "heuristic"
            except Exception as e:
                logger.warning(f"LLM analysis failed, falling back to heuristics: {e}")

        if structured_json is None:
            structured_json = heuristic_structured
        ats_analysis = self._build_ats_analysis(compact_text, structured_json, extracted_data)

        if llm_feedback is None:
            llm_feedback = self._build_heuristic_feedback(compact_text, structured_json, extracted_data, ats_analysis)
        if ats_score is None or ats_feedback is None:
            ats_score, ats_feedback = self._calculate_ats_fallback(compact_text, structured_json, extracted_data)

        if isinstance(llm_feedback, dict):
            llm_feedback["ats_analysis"] = ats_analysis

        return {
            "structured_json": structured_json,
            "llm_feedback": llm_feedback,
            "ats_score": ats_score,
            "ats_feedback": ats_feedback,
            "analysis_source": analysis_source,
        }

    def _generate_structured_json(
        self,
        parsed_text: str,
        extracted_data: Optional[Dict[str, Any]] = None,
        file_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate structured JSON representation of resume."""
        compact_text = (parsed_text or "")[:4500]
        prompt = f"""
You are a resume parsing engine. Extract the resume into concise JSON.

Rules:
- Return ONLY JSON.
- Do not invent missing data.
- Prefer concise arrays.
- Use the provided extracted data as hints when helpful.

File name: {file_name or "unknown"}

Parsed text:
---
{compact_text}
---

Existing extracted hints:
{json.dumps(extracted_data or {}, indent=2)}

Return a JSON object with these sections (all optional):
{{
  "contact": {{
    "name": "string",
    "email": "string",
    "phone": "string",
    "location": "string",
    "linkedin": "string",
    "website": "string"
  }},
  "summary": "string",
  "experience": [{{
    "title": "string",
    "company": "string",
    "duration": "string",
    "start_date": "string",
    "end_date": "string",
    "description": "string",
    "key_achievements": ["string"]
  }}],
  "education": [{{
    "degree": "string",
    "field": "string",
    "school": "string",
    "graduation_date": "string",
    "gpa": "string",
    "honors": "string"
  }}],
  "skills": [{{
    "category": "string",
    "items": ["string"]
  }}],
  "certifications": [{{
    "name": "string",
    "issuer": "string",
    "date": "string",
    "credential_id": "string"
  }}],
  "languages": ["string"],
    "projects": [{{
    "title": "string",
    "description": "string",
    "technologies": ["string"],
    "date": "string"
  }}]
}}
"""
        try:
            response_text = self._call_llm(prompt, json_mode=True)
            if not response_text:
                return None
            return self._safe_json_loads(response_text)
        except Exception as e:
            logger.warning(f"Structured JSON generation failed: {e}")
            return None

    def _generate_llm_feedback(
        self,
        parsed_text: str,
        structured_json: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Generate feedback on resume content and recommendations."""
        prompt = f"""
Analyze the following resume and provide constructive feedback.

Resume text:
---
{parsed_text}
---

Structured data:
{json.dumps(structured_json, indent=2)}

Return ONLY JSON with:
{{
  "strengths": ["string"],
  "weaknesses": ["string"],
  "suggestions": ["string"],
  "overall_assessment": "string",
  "estimated_experience_years": number,
  "role_suitability": {{
    "technical_role": number,
    "leadership_role": number,
    "entry_level": number
  }}
}}
"""
        try:
            response_text = self._call_llm(prompt, json_mode=True)
            if not response_text:
                return None
            return self._safe_json_loads(response_text)
        except Exception as e:
            logger.warning(f"LLM feedback generation failed: {e}")
            return None

    def _calculate_ats_score(
        self,
        parsed_text: str,
        structured_json: Dict[str, Any],
        extracted_data: Optional[Dict[str, Any]] = None,
    ) -> tuple[Optional[int], Optional[str]]:
        """Calculate ATS compatibility score using LLM when available."""
        prompt = f"""
Evaluate this resume for ATS compatibility and provide a score.

Resume text:
---
{parsed_text}
---

Structured data:
{json.dumps(structured_json, indent=2)}

Existing extracted hints:
{json.dumps(extracted_data or {}, indent=2)}

Return ONLY JSON:
{{
  "score": number,
  "reasoning": "string",
  "deductions": ["string"],
  "improvements": ["string"]
}}
"""
        try:
            response_text = self._call_llm(prompt, json_mode=True)
            if not response_text:
                return None, None
            result = self._safe_json_loads(response_text)
            if not isinstance(result, dict):
                return None, None
            score = int(result.get("score", 75))
            score = max(0, min(100, score))
            reasoning = str(result.get("reasoning", ""))
            return score, reasoning
        except Exception as e:
            logger.warning(f"ATS scoring via LLM failed: {e}")
            return None, None

    def _calculate_ats_fallback(
        self,
        parsed_text: str,
        structured_json: Dict[str, Any],
        extracted_data: Optional[Dict[str, Any]] = None,
    ) -> tuple[int, str]:
        """Heuristic ATS scoring fallback that always returns a score."""
        analysis = self._build_ats_analysis(parsed_text, structured_json, extracted_data)
        return int(analysis.get("overall_score", 60)), str(analysis.get("summary", "Resume analyzed with heuristic ATS scoring."))

    def _build_ats_analysis(
        self,
        parsed_text: str,
        structured_json: Dict[str, Any],
        extracted_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        text = parsed_text or ""
        lower = text.lower()
        extracted_data = extracted_data or {}
        skills = self._flatten_skills(extracted_data, structured_json)

        experience_entries = structured_json.get("experience") if isinstance(structured_json.get("experience"), list) else []
        education_entries = structured_json.get("education") if isinstance(structured_json.get("education"), list) else []
        summary = structured_json.get("summary")
        contact = structured_json.get("contact") if isinstance(structured_json.get("contact"), dict) else {}

        has_email = bool(contact.get("email") or re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text))
        has_phone = bool(contact.get("phone") or re.search(r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3}\)?[\s-]?)?\d{3}[\s-]?\d{4}", text))
        has_location = bool(contact.get("location"))
        has_bullets = any(marker in text for marker in ["•", "- ", "* "])
        text_len = len(text)
        quantified_hits = len(re.findall(r"\b\d+(?:\.\d+)?\s?(?:%|x|\+|k|m|yr|yrs|years|months?)\b", lower))
        has_experience_heading = any(token in lower for token in ["experience", "work history", "employment"])
        has_education_heading = any(token in lower for token in ["education", "university", "college", "school"])
        has_skills_heading = "skills" in lower

        formatting_score = 35
        formatting_reasons = []
        if has_bullets:
            formatting_score += 28
            formatting_reasons.append("bullet points found")
        else:
            formatting_reasons.append("few explicit bullet points")
        if 900 <= text_len <= 6500:
            formatting_score += 22
            formatting_reasons.append("resume length is ATS-friendly")
        elif text_len < 900:
            formatting_score -= 8
            formatting_reasons.append("resume appears too short")
        else:
            formatting_score -= 4
            formatting_reasons.append("resume may be too long for quick parsing")
        if "|" in text or "\t" in text:
            formatting_score -= 4
            formatting_reasons.append("complex layout symbols detected")
        formatting_score = max(0, min(100, formatting_score))

        keyword_score = 30
        keyword_reasons = []
        if len(skills) >= 12:
            keyword_score += 50
            keyword_reasons.append(f"{len(skills)} technical keywords identified")
        elif len(skills) >= 8:
            keyword_score += 36
            keyword_reasons.append(f"{len(skills)} technical keywords identified")
        elif len(skills) >= 4:
            keyword_score += 22
            keyword_reasons.append(f"{len(skills)} technical keywords identified")
        else:
            keyword_reasons.append("limited explicit technical keywords")
        if has_skills_heading:
            keyword_score += 8
            keyword_reasons.append("skills section label present")
        keyword_score = max(0, min(100, keyword_score))

        experience_score = 30
        experience_reasons = []
        if experience_entries:
            experience_score += min(45, len(experience_entries) * 15)
            experience_reasons.append(f"{len(experience_entries)} experience entries parsed")
        elif has_experience_heading:
            experience_score += 20
            experience_reasons.append("experience section detected")
        else:
            experience_reasons.append("experience section is not clearly structured")
        if quantified_hits >= 3:
            experience_score += 12
            experience_reasons.append("multiple measurable outcomes found")
        experience_score = max(0, min(100, experience_score))

        impact_score = 25
        impact_reasons = []
        if quantified_hits >= 6:
            impact_score += 60
            impact_reasons.append(f"{quantified_hits} quantified impact signals detected")
        elif quantified_hits >= 3:
            impact_score += 42
            impact_reasons.append(f"{quantified_hits} quantified impact signals detected")
        elif quantified_hits >= 1:
            impact_score += 25
            impact_reasons.append("some quantified achievements detected")
        else:
            impact_reasons.append("few quantified achievements found")
        impact_score = max(0, min(100, impact_score))

        section_score = 20
        section_reasons = []
        present_sections = 0
        if has_email:
            present_sections += 1
            section_reasons.append("email present")
        if has_phone:
            present_sections += 1
            section_reasons.append("phone present")
        if has_location:
            present_sections += 1
            section_reasons.append("location present")
        if summary and isinstance(summary, str) and summary.strip():
            present_sections += 1
            section_reasons.append("summary present")
        if experience_entries or has_experience_heading:
            present_sections += 1
            section_reasons.append("experience present")
        if education_entries or has_education_heading:
            present_sections += 1
            section_reasons.append("education present")
        if len(skills) >= 3 or has_skills_heading:
            present_sections += 1
            section_reasons.append("skills present")
        section_score += present_sections * 11
        section_score = max(0, min(100, section_score))

        contact_items_present = []
        if has_email:
            contact_items_present.append("email")
        if has_phone:
            contact_items_present.append("phone")
        if has_location:
            contact_items_present.append("location")
        contact_phrase = self._format_presence_phrase(contact_items_present)
        section_reason_summary = contact_phrase if contact_phrase else "; ".join(section_reasons[:3])

        dimensions = [
            {
                "id": "formatting",
                "label": "Formatting",
                "score": formatting_score,
                "reason": "; ".join(formatting_reasons[:2]),
            },
            {
                "id": "keyword_match",
                "label": "Keyword Match",
                "score": keyword_score,
                "reason": "; ".join(keyword_reasons[:2]),
            },
            {
                "id": "experience_strength",
                "label": "Experience Strength",
                "score": experience_score,
                "reason": "; ".join(experience_reasons[:2]),
            },
            {
                "id": "impact",
                "label": "Impact",
                "score": impact_score,
                "reason": "; ".join(impact_reasons[:2]),
            },
            {
                "id": "section_completeness",
                "label": "Section Completeness",
                "score": section_score,
                "reason": section_reason_summary,
            },
        ]

        weighted_score = (
            formatting_score * 0.20
            + keyword_score * 0.25
            + experience_score * 0.25
            + impact_score * 0.20
            + section_score * 0.10
        )
        overall_score = int(max(0, min(100, round(weighted_score))))

        highlights = []
        if len(skills) >= 8:
            highlights.append(f"Strong keyword coverage with {len(skills)} explicit skills.")
        if quantified_hits >= 3:
            highlights.append(f"Contains {quantified_hits} quantified achievements, improving recruiter confidence.")
        if has_email and has_phone:
            highlights.append("Core contact fields are present for recruiter outreach.")
        if experience_entries:
            highlights.append("Structured experience entries improve parser readability.")

        issues = []
        if len(skills) < 6:
            issues.append("Skill list is thin for broad ATS keyword matching.")
        if quantified_hits < 2:
            issues.append("Few measurable outcomes; impact is mostly qualitative.")
        if not has_experience_heading and not experience_entries:
            issues.append("Experience section is not clearly labeled.")
        if not has_education_heading and not education_entries:
            issues.append("Education details are not clearly surfaced.")
        if text_len < 900:
            issues.append("Resume content is short and may miss screening context.")

        next_steps = []
        if len(skills) < 8:
            next_steps.append("Add 5-8 role-relevant tools, frameworks, and platform keywords.")
        if quantified_hits < 3:
            next_steps.append("Rewrite bullets with numbers: %, latency, revenue, users, or delivery time.")
        if not has_experience_heading:
            next_steps.append("Create a dedicated Experience section with role, company, and dates.")
        if not has_education_heading:
            next_steps.append("Add an Education section with degree, institution, and year.")
        if not has_phone:
            next_steps.append("Add a phone number in the top contact block.")

        if overall_score >= 80:
            grade = "Strong"
        elif overall_score >= 65:
            grade = "Moderate"
        else:
            grade = "Needs Work"

        top_gap = issues[0].rstrip(".") if issues else "resume impact statements need stronger quantification"
        summary = (
            f"Your resume currently has an ATS compatibility score of {overall_score}/100, "
            f"which places it in the {grade.lower()} range. "
            f"The strongest areas are {dimensions[1]['label']} ({keyword_score}/100) and "
            f"{dimensions[2]['label']} ({experience_score}/100). "
            f"The top improvement area is {top_gap.lower()}."
        )

        return {
            "overall_score": overall_score,
            "grade": grade,
            "dimensions": dimensions,
            "highlights": highlights[:4],
            "issues": issues[:4],
            "next_steps": next_steps[:4],
            "summary": summary,
        }

    @staticmethod
    def _format_presence_phrase(items: list[str]) -> str:
        clean_items = [item.strip().lower() for item in items if isinstance(item, str) and item.strip()]
        if not clean_items:
            return ""
        if len(clean_items) == 1:
            subject = clean_items[0].capitalize()
            return f"{subject} is present."
        elif len(clean_items) == 2:
            subject = f"{clean_items[0].capitalize()} and {clean_items[1]}"
        else:
            subject = f"{', '.join(clean_items[:-1]).capitalize()}, and {clean_items[-1]}"
        return f"{subject} are present."

    def _build_heuristic_structured_json(
        self,
        parsed_text: str,
        extracted_data: Optional[Dict[str, Any]] = None,
        file_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a reasonable structured JSON payload without LLM support."""
        extracted_data = extracted_data or {}
        lines = [line.strip() for line in (parsed_text or "").splitlines() if line.strip()]
        lower = (parsed_text or "").lower()
        skill_items = self._flatten_skills(extracted_data, {})
        if not skill_items:
            skill_items = self._infer_skills(lower)

        contact = {
            "name": extracted_data.get("name") or (lines[0] if lines else None),
            "email": extracted_data.get("email"),
            "phone": extracted_data.get("phone"),
            "location": extracted_data.get("location"),
            "linkedin": extracted_data.get("linkedin") or extracted_data.get("linkedin_url"),
            "website": extracted_data.get("website") or extracted_data.get("portfolio_url"),
        }
        if contact["name"] and isinstance(contact["name"], str):
            contact["name"] = contact["name"].strip()

        summary = extracted_data.get("summary") or " ".join(lines[:4])[:500]

        experience = []
        if extracted_data.get("work_experience"):
            experience = extracted_data["work_experience"]
        elif any(k in lower for k in ["experience", "work experience", "employment"]):
            experience = [
                {
                    "title": "Professional Experience",
                    "company": "",
                    "duration": "",
                    "start_date": None,
                    "end_date": None,
                    "description": "Resume contains an experience section with relevant work history.",
                    "key_achievements": [],
                }
            ]

        education = extracted_data.get("education") or []
        projects = extracted_data.get("projects") or []
        certifications = extracted_data.get("certifications") or []

        structured: Dict[str, Any] = {
            "contact": contact,
            "summary": summary,
            "experience": experience,
            "education": education,
            "skills": [{"category": "Technical Skills", "items": skill_items}] if skill_items else [],
            "certifications": certifications,
            "languages": extracted_data.get("languages") or [],
            "projects": projects,
        }
        if file_name:
            structured["source_file"] = file_name
        return structured

    def _build_heuristic_feedback(
        self,
        parsed_text: str,
        structured_json: Dict[str, Any],
        extracted_data: Optional[Dict[str, Any]] = None,
        ats_analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build practical feedback when the LLM cannot be used."""
        extracted_data = extracted_data or {}
        ats_analysis = ats_analysis or self._build_ats_analysis(parsed_text, structured_json, extracted_data)
        skills = self._flatten_skills(extracted_data, structured_json)
        strengths = []
        weaknesses = []
        suggestions = []

        if extracted_data.get("name") or structured_json.get("contact", {}).get("name"):
            strengths.append("Clear candidate identity detected")
        if extracted_data.get("email") or structured_json.get("contact", {}).get("email"):
            strengths.append("Contact email is present")
        if extracted_data.get("phone") or structured_json.get("contact", {}).get("phone"):
            strengths.append("Contact phone is present")
        if len(skills) >= 8:
            strengths.append("Strong technical skill coverage")
        elif len(skills) >= 4:
            strengths.append("Relevant technical skills identified")

        for item in ats_analysis.get("highlights", [])[:2]:
            if isinstance(item, str):
                strengths.append(item)

        text = (parsed_text or "").lower()
        if "experience" not in text and "work experience" not in text:
            weaknesses.append("Experience section could be more clearly structured")
            suggestions.append("Add a dedicated experience section with role, company, dates, and achievements")
        if "education" not in text and "university" not in text and "college" not in text:
            weaknesses.append("Education section is not clearly visible")
            suggestions.append("Add a clearly labeled education section")
        if len(skills) < 6:
            weaknesses.append("Skill section is too small for strong ATS matching")
            suggestions.append("Expand skills with tools, frameworks, cloud, databases, and core CS concepts")
        if len((parsed_text or "").splitlines()) < 20:
            weaknesses.append("Resume looks short or condensed")
            suggestions.append("Add bullet points with measurable outcomes and project impact")

        for item in ats_analysis.get("issues", [])[:2]:
            if isinstance(item, str):
                weaknesses.append(item)
        for item in ats_analysis.get("next_steps", [])[:2]:
            if isinstance(item, str):
                suggestions.append(item)

        if not strengths:
            strengths.append("Basic resume text was extracted successfully")
        if not suggestions:
            suggestions.append("Add quantified achievements and role-specific keywords")

        return {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "suggestions": suggestions,
            "overall_assessment": ats_analysis.get("summary") or self._build_overall_assessment(strengths, weaknesses),
            "estimated_experience_years": extracted_data.get("experience_years"),
            "role_suitability": {
                "technical_role": min(100, 40 + int(ats_analysis.get("overall_score", 60) * 0.7)),
                "leadership_role": min(100, 35 + int(next((d.get("score", 45) for d in ats_analysis.get("dimensions", []) if d.get("id") == "experience_strength"), 45) * 0.5)),
                "entry_level": min(100, 55 + int(next((d.get("score", 55) for d in ats_analysis.get("dimensions", []) if d.get("id") == "section_completeness"), 55) * 0.4)),
            },
        }

    def _build_overall_assessment(self, strengths: list[str], weaknesses: list[str]) -> str:
        if strengths and weaknesses:
            return f"Resume shows useful strengths such as {strengths[0].lower()}, but needs improvement in {weaknesses[0].lower()}."
        if strengths:
            return f"Resume is reasonably strong, with {strengths[0].lower()} as a positive signal."
        return "Resume could benefit from clearer structure and more role-specific detail."

    def _flatten_skills(
        self,
        extracted_data: Optional[Dict[str, Any]],
        structured_json: Dict[str, Any],
    ) -> list[str]:
        skills: list[str] = []
        extracted_data = extracted_data or {}

        for raw in [extracted_data.get("skills"), structured_json.get("skills")]:
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, str):
                        value = item.strip()
                        if value:
                            skills.append(value)
                    elif isinstance(item, dict):
                        for sub in item.get("items", []):
                            if isinstance(sub, str) and sub.strip():
                                skills.append(sub.strip())
        # de-duplicate preserving order
        seen = set()
        result = []
        for skill in skills:
            key = skill.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(skill)
        return result

    def _infer_skills(self, lower_text: str) -> list[str]:
        skill_bank = [
            "python", "java", "javascript", "typescript", "react", "node.js", "node", "sql",
            "postgresql", "aws", "azure", "docker", "kubernetes", "fastapi", "django", "flask",
            "machine learning", "data structures", "algorithms", "system design", "git", "redis",
            "mongodb", "html", "css", "linux", "flask", "pandas", "numpy",
        ]
        found = []
        for skill in skill_bank:
            if skill in lower_text:
                found.append(skill if skill != "node" else "Node.js")
        return list(dict.fromkeys(found))

    def _select_model_name(self) -> Optional[str]:
        if not self.llm_provider:
            return None
        configured = getattr(self.settings.llm, "llm_model_resume_parsing", None) if self.settings else None
        if configured and hasattr(self.llm_provider, "supports_model"):
            try:
                if self.llm_provider.supports_model(configured):
                    return configured
            except Exception:
                pass
        try:
            supported = self.llm_provider.get_supported_models()
            return supported[0] if supported else configured
        except Exception:
            return configured

    def _call_llm(self, prompt: str, json_mode: bool = False) -> Optional[str]:
        if not self.llm_provider:
            return None
        model_name = self.model_name or self._select_model_name()
        if not model_name:
            return None

        request = LLMRequest(
            prompt=prompt,
            system_prompt="You are an expert resume analyst. Return precise, useful, structured output.",
            model=model_name,
            temperature=0.1 if json_mode else (self.settings.llm.llm_temperature if self.settings else 0.2),
            max_tokens=self.settings.llm.llm_max_tokens if self.settings else 2000,
            timeout_seconds=self.settings.llm.llm_timeout_seconds if self.settings else 30,
            json_mode=json_mode,
            deterministic=json_mode,
        )
        try:
            response = asyncio.run(
                self.llm_provider.generate_structured(request) if json_mode else self.llm_provider.generate_text(request)
            )
            if response.success and response.text:
                return self._strip_code_fences(response.text)
            return None
        except RuntimeError:
            # Fallback in case an event loop is already running.
            logger.warning("LLM call skipped because an event loop is already running")
            return None
        except Exception as e:
            logger.warning(f"LLM call failed: {e}")
            return None

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return text.strip()

    @staticmethod
    def _safe_json_loads(text: str) -> Any:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return json.loads(text)


# Singleton instance
_resume_analysis_service: Optional[ResumeAnalysisService] = None


def get_resume_analysis_service() -> ResumeAnalysisService:
    """Get or create the resume analysis service."""
    global _resume_analysis_service
    if _resume_analysis_service is None:
        _resume_analysis_service = ResumeAnalysisService()
    return _resume_analysis_service
