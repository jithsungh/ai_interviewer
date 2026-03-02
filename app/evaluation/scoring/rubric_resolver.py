"""
Rubric Resolver

Resolves the correct rubric for an exchange.

Resolution Logic:
    interview_exchange
    → interview_submission_id
    → interview_submissions.template_id
    → interview_template_rubrics (lookup)
    → rubric_id
    → rubric_dimensions (fetch all)

Design:
- Rubric is frozen at interview creation (not re-fetched dynamically)
- Returns all dimensions with weights and max_scores
- Raises typed errors for resolution failures
- No business logic beyond resolution
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.evaluation.scoring.contracts import RubricDimensionDTO, RubricDTO
from app.evaluation.scoring.errors import (
    ExchangeNotFoundError,
    InvalidRubricError,
    RubricNotFoundError,
)
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


class RubricResolver:
    """
    Resolves rubric for interview exchanges.
    
    Uses the rubric linked to the exchange's interview template.
    """
    
    def __init__(self, session: Session) -> None:
        self._session = session
    
    def resolve_rubric(
        self,
        interview_exchange_id: int
    ) -> Tuple[int, List[RubricDimensionDTO]]:
        """
        Resolve rubric for an exchange.
        
        Args:
            interview_exchange_id: Exchange to resolve rubric for.
        
        Returns:
            Tuple of (rubric_id, list of RubricDimensionDTO)
        
        Raises:
            ExchangeNotFoundError: Exchange does not exist.
            RubricNotFoundError: No rubric linked to template.
            InvalidRubricError: Rubric has 0 dimensions.
        """
        # Step 1: Get exchange and validate existence
        exchange_data = self._get_exchange_data(interview_exchange_id)
        if exchange_data is None:
            raise ExchangeNotFoundError(exchange_id=interview_exchange_id)
        
        submission_id = exchange_data["submission_id"]
        
        # Step 2: Get template_id from submission
        template_id = self._get_template_id(submission_id)
        if template_id is None:
            logger.error(
                "Submission not found for exchange",
                extra={"exchange_id": interview_exchange_id, "submission_id": submission_id}
            )
            raise ExchangeNotFoundError(exchange_id=interview_exchange_id)
        
        # Step 3: Get rubric_id from template
        rubric_id = self._get_rubric_for_template(template_id)
        if rubric_id is None:
            logger.warning(
                "No rubric found for template",
                extra={"template_id": template_id, "exchange_id": interview_exchange_id}
            )
            raise RubricNotFoundError(template_id=template_id)
        
        # Step 4: Fetch all dimensions for rubric
        dimensions = self._get_rubric_dimensions(rubric_id)
        if not dimensions:
            logger.error(
                "Rubric has no dimensions",
                extra={"rubric_id": rubric_id, "exchange_id": interview_exchange_id}
            )
            raise InvalidRubricError(
                rubric_id=rubric_id,
                reason="Rubric has 0 dimensions"
            )
        
        logger.info(
            "Rubric resolved for exchange",
            extra={
                "exchange_id": interview_exchange_id,
                "rubric_id": rubric_id,
                "dimension_count": len(dimensions)
            }
        )
        
        return rubric_id, dimensions
    
    def get_full_rubric(
        self,
        interview_exchange_id: int
    ) -> RubricDTO:
        """
        Get full rubric DTO with name and dimensions.
        
        Args:
            interview_exchange_id: Exchange to resolve rubric for.
        
        Returns:
            RubricDTO with complete rubric information.
        
        Raises:
            ExchangeNotFoundError: Exchange does not exist.
            RubricNotFoundError: No rubric linked to template.
            InvalidRubricError: Rubric has 0 dimensions.
        """
        rubric_id, dimensions = self.resolve_rubric(interview_exchange_id)
        rubric_name = self._get_rubric_name(rubric_id)
        
        return RubricDTO(
            rubric_id=rubric_id,
            rubric_name=rubric_name or f"Rubric {rubric_id}",
            dimensions=dimensions
        )
    
    def _get_exchange_data(self, exchange_id: int) -> Optional[dict]:
        """Fetch exchange submission_id."""
        query = text("""
            SELECT id, interview_submission_id as submission_id
            FROM interview_exchanges
            WHERE id = :exchange_id
        """)
        result = self._session.execute(query, {"exchange_id": exchange_id}).fetchone()
        if result:
            return {"id": result[0], "submission_id": result[1]}
        return None
    
    def _get_template_id(self, submission_id: int) -> Optional[int]:
        """Get template_id from submission."""
        query = text("""
            SELECT template_id
            FROM interview_submissions
            WHERE id = :submission_id
        """)
        result = self._session.execute(query, {"submission_id": submission_id}).scalar()
        return result
    
    def _get_rubric_for_template(self, template_id: int) -> Optional[int]:
        """
        Get rubric_id for template.
        
        Returns the first rubric linked to the template.
        Templates may have multiple rubrics for different sections,
        but for exchange-level scoring we use the primary rubric.
        """
        query = text("""
            SELECT rubric_id
            FROM interview_template_rubrics
            WHERE interview_template_id = :template_id
            ORDER BY id ASC
            LIMIT 1
        """)
        result = self._session.execute(query, {"template_id": template_id}).scalar()
        return result
    
    def _get_rubric_dimensions(self, rubric_id: int) -> List[RubricDimensionDTO]:
        """Fetch all dimensions for rubric."""
        query = text("""
            SELECT 
                id as rubric_dimension_id,
                dimension_name,
                weight,
                max_score,
                description,
                criteria as scoring_criteria,
                sequence_order
            FROM rubric_dimensions
            WHERE rubric_id = :rubric_id
            ORDER BY sequence_order ASC, id ASC
        """)
        results = self._session.execute(query, {"rubric_id": rubric_id}).fetchall()
        
        dimensions = []
        for row in results:
            # Extract scoring criteria from JSONB if present
            scoring_criteria = None
            if row[5]:
                # criteria is JSONB, extract as string or use specific field
                if isinstance(row[5], dict):
                    scoring_criteria = row[5].get("criteria_text", str(row[5]))
                else:
                    scoring_criteria = str(row[5])
            
            dimensions.append(RubricDimensionDTO(
                rubric_dimension_id=row[0],
                dimension_name=row[1],
                weight=Decimal(str(row[2])) if row[2] is not None else Decimal("1.0"),
                max_score=Decimal(str(row[3])) if row[3] is not None else Decimal("5.0"),
                description=row[4],
                scoring_criteria=scoring_criteria,
                sequence_order=row[6] if row[6] is not None else 0
            ))
        
        return dimensions
    
    def _get_rubric_name(self, rubric_id: int) -> Optional[str]:
        """Get rubric name."""
        query = text("""
            SELECT name
            FROM rubrics
            WHERE id = :rubric_id
        """)
        return self._session.execute(query, {"rubric_id": rubric_id}).scalar()


def resolve_rubric(
    session: Session,
    interview_exchange_id: int
) -> Tuple[int, List[RubricDimensionDTO]]:
    """
    Convenience function for rubric resolution.
    
    Args:
        session: Database session.
        interview_exchange_id: Exchange to resolve rubric for.
    
    Returns:
        Tuple of (rubric_id, list of RubricDimensionDTO)
    """
    resolver = RubricResolver(session)
    return resolver.resolve_rubric(interview_exchange_id)
