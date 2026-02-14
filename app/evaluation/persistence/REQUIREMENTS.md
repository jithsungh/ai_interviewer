# Evaluation Persistence - Repositories for Evaluations & Results Tables

## 1. Purpose

The **Persistence** layer is responsible for:

- Managing database operations for evaluation-related tables
- Enforcing invariants at database level (UNIQUE constraints, foreign keys)
- Providing repository pattern for evaluations, dimension scores, results
- Handling transactions and concurrency
- Supporting audit trail and versioning

**Critical responsibility:** This is the **data integrity boundary**. It must:

- Enforce "one exchange = one evaluation" via UNIQUE constraint
- Prevent duplicate evaluations
- Support versioning (is_final, is_current flags)
- Handle concurrent access safely
- Maintain referential integrity

---

## 2. Owned Tables

### evaluations

```sql
CREATE TABLE evaluations (
    id SERIAL PRIMARY KEY,
    interview_exchange_id INTEGER NOT NULL REFERENCES interview_exchanges(id) ON DELETE CASCADE,
    rubric_id INTEGER REFERENCES rubrics(id),
    evaluator_type VARCHAR(20) NOT NULL CHECK (evaluator_type IN ('ai', 'human', 'hybrid')),
    total_score NUMERIC(5, 2) NOT NULL,
    explanation TEXT,
    is_final BOOLEAN DEFAULT true,
    evaluated_at TIMESTAMP DEFAULT NOW(),
    evaluated_by INTEGER REFERENCES users(id),  -- Human evaluator (if applicable)
    model_id VARCHAR(100),  -- AI model (e.g., 'gpt-4-turbo')
    scoring_version VARCHAR(20),  -- Algorithm version
    UNIQUE(interview_exchange_id, is_final) WHERE is_final = true
);

CREATE INDEX idx_evaluations_exchange ON evaluations(interview_exchange_id);
CREATE INDEX idx_evaluations_rubric ON evaluations(rubric_id);
CREATE INDEX idx_evaluations_final ON evaluations(is_final) WHERE is_final = true;
```

### evaluation_dimension_scores

```sql
CREATE TABLE evaluation_dimension_scores (
    id SERIAL PRIMARY KEY,
    evaluation_id INTEGER NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    rubric_dimension_id INTEGER NOT NULL REFERENCES rubric_dimensions(id),
    score NUMERIC(4, 2) NOT NULL,
    max_score NUMERIC(4, 2) NOT NULL,
    justification TEXT,
    UNIQUE(evaluation_id, rubric_dimension_id)
);

CREATE INDEX idx_dimension_scores_evaluation ON evaluation_dimension_scores(evaluation_id);
CREATE INDEX idx_dimension_scores_rubric_dimension ON evaluation_dimension_scores(rubric_dimension_id);
```

### interview_results

```sql
CREATE TABLE interview_results (
    id SERIAL PRIMARY KEY,
    interview_id INTEGER NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    final_score NUMERIC(6, 2) NOT NULL,
    normalized_score NUMERIC(5, 2) NOT NULL CHECK (normalized_score >= 0 AND normalized_score <= 100),
    result_status VARCHAR(20) NOT NULL CHECK (result_status IN ('pending', 'completed', 'flagged', 'invalidated')),
    recommendation VARCHAR(20) NOT NULL CHECK (recommendation IN ('strong_hire', 'hire', 'review', 'no_hire')),

    -- Audit snapshots (JSONB)
    rubric_snapshot JSONB NOT NULL,
    template_weight_snapshot JSONB NOT NULL,
    section_scores JSONB NOT NULL,

    -- Generated content
    strengths TEXT[],
    weaknesses TEXT[],
    summary_notes TEXT,

    -- Metadata
    generated_by VARCHAR(20) NOT NULL CHECK (generated_by IN ('ai', 'human', 'hybrid')),
    model_id VARCHAR(100),
    is_current BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(interview_id, is_current) WHERE is_current = true
);

CREATE INDEX idx_interview_results_interview ON interview_results(interview_id);
CREATE INDEX idx_interview_results_current ON interview_results(interview_id, is_current);
CREATE INDEX idx_interview_results_recommendation ON interview_results(recommendation);
```

### supplementary_reports

```sql
CREATE TABLE supplementary_reports (
    id SERIAL PRIMARY KEY,
    interview_result_id INTEGER NOT NULL REFERENCES interview_results(id) ON DELETE CASCADE,
    report_type VARCHAR(50) NOT NULL CHECK (report_type IN ('technical_breakdown', 'behavioral_analysis', 'proctoring_risk', 'custom')),
    report_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_supplementary_reports_result ON supplementary_reports(interview_result_id);
CREATE INDEX idx_supplementary_reports_type ON supplementary_reports(report_type);
```

---

## 3. Repository Pattern

### EvaluationRepository

**Responsibilities:**

- Create evaluation
- Fetch evaluation by ID
- Fetch evaluation by exchange (with is_final filter)
- Mark evaluation as non-final (re-evaluation flow)
- List evaluations for interview

#### Methods

```python
from typing import Optional, List
from sqlalchemy.orm import Session
from decimal import Decimal

class EvaluationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        interview_exchange_id: int,
        rubric_id: int,
        evaluator_type: str,
        total_score: Decimal,
        explanation: Optional[str] = None,
        evaluated_by: Optional[int] = None,
        model_id: Optional[str] = None,
        scoring_version: Optional[str] = None
    ) -> Evaluation:
        """
        Create evaluation.

        Raises:
            IntegrityError: If UNIQUE constraint violated (duplicate evaluation)
        """
        evaluation = Evaluation(
            interview_exchange_id=interview_exchange_id,
            rubric_id=rubric_id,
            evaluator_type=evaluator_type,
            total_score=total_score,
            explanation=explanation,
            is_final=True,
            evaluated_by=evaluated_by,
            model_id=model_id,
            scoring_version=scoring_version
        )
        self.db.add(evaluation)
        self.db.commit()
        self.db.refresh(evaluation)
        return evaluation

    def get_by_id(self, evaluation_id: int) -> Optional[Evaluation]:
        """Fetch evaluation by ID."""
        return self.db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()

    def get_by_exchange(
        self,
        interview_exchange_id: int,
        is_final: bool = True
    ) -> Optional[Evaluation]:
        """Fetch evaluation for exchange (optionally filter by is_final)."""
        query = self.db.query(Evaluation).filter(
            Evaluation.interview_exchange_id == interview_exchange_id
        )
        if is_final is not None:
            query = query.filter(Evaluation.is_final == is_final)
        return query.first()

    def mark_non_final(self, evaluation_id: int) -> None:
        """Mark evaluation as non-final (re-evaluation flow)."""
        evaluation = self.get_by_id(evaluation_id)
        if evaluation:
            evaluation.is_final = False
            self.db.commit()

    def list_by_interview(
        self,
        interview_id: int,
        is_final: Optional[bool] = None
    ) -> List[Evaluation]:
        """List all evaluations for interview."""
        # Join with exchanges to filter by interview
        query = self.db.query(Evaluation).join(
            InterviewExchange,
            Evaluation.interview_exchange_id == InterviewExchange.id
        ).filter(InterviewExchange.interview_id == interview_id)

        if is_final is not None:
            query = query.filter(Evaluation.is_final == is_final)

        return query.all()

    def exists_for_exchange(self, interview_exchange_id: int) -> bool:
        """Check if evaluation exists for exchange (is_final=true)."""
        return self.db.query(
            self.db.query(Evaluation)
            .filter(
                Evaluation.interview_exchange_id == interview_exchange_id,
                Evaluation.is_final == True
            )
            .exists()
        ).scalar()
```

---

### EvaluationDimensionScoreRepository

**Responsibilities:**

- Create dimension scores (batch insert)
- Fetch dimension scores by evaluation
- Calculate average score per dimension across interview

#### Methods

```python
from typing import List

class EvaluationDimensionScoreRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_batch(
        self,
        evaluation_id: int,
        dimension_scores: List[dict]
    ) -> List[EvaluationDimensionScore]:
        """
        Create dimension scores in batch.

        Args:
            evaluation_id: Evaluation ID
            dimension_scores: List of {rubric_dimension_id, score, max_score, justification}

        Raises:
            IntegrityError: If UNIQUE constraint violated (duplicate dimension)
        """
        scores = [
            EvaluationDimensionScore(
                evaluation_id=evaluation_id,
                rubric_dimension_id=ds['rubric_dimension_id'],
                score=ds['score'],
                max_score=ds['max_score'],
                justification=ds['justification']
            )
            for ds in dimension_scores
        ]
        self.db.add_all(scores)
        self.db.commit()
        return scores

    def get_by_evaluation(self, evaluation_id: int) -> List[EvaluationDimensionScore]:
        """Fetch all dimension scores for evaluation."""
        return self.db.query(EvaluationDimensionScore).filter(
            EvaluationDimensionScore.evaluation_id == evaluation_id
        ).all()

    def get_average_by_dimension(
        self,
        interview_id: int,
        rubric_dimension_id: int
    ) -> Optional[float]:
        """
        Calculate average score for dimension across all exchanges in interview.

        Used for summary generation.
        """
        result = self.db.query(
            func.avg(EvaluationDimensionScore.score)
        ).join(
            Evaluation,
            EvaluationDimensionScore.evaluation_id == Evaluation.id
        ).join(
            InterviewExchange,
            Evaluation.interview_exchange_id == InterviewExchange.id
        ).filter(
            InterviewExchange.interview_id == interview_id,
            EvaluationDimensionScore.rubric_dimension_id == rubric_dimension_id,
            Evaluation.is_final == True
        ).scalar()

        return float(result) if result else None
```

---

### InterviewResultRepository

**Responsibilities:**

- Create interview result
- Fetch result by ID
- Fetch current result for interview
- Mark result as non-current (versioning)
- List all results for interview (audit trail)

#### Methods

```python
from typing import Dict, List

class InterviewResultRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        interview_id: int,
        final_score: Decimal,
        normalized_score: Decimal,
        result_status: str,
        recommendation: str,
        rubric_snapshot: dict,
        template_weight_snapshot: dict,
        section_scores: dict,
        strengths: List[str],
        weaknesses: List[str],
        summary_notes: str,
        generated_by: str,
        model_id: Optional[str] = None
    ) -> InterviewResult:
        """
        Create interview result.

        Raises:
            IntegrityError: If UNIQUE constraint violated (duplicate current result)
        """
        result = InterviewResult(
            interview_id=interview_id,
            final_score=final_score,
            normalized_score=normalized_score,
            result_status=result_status,
            recommendation=recommendation,
            rubric_snapshot=rubric_snapshot,
            template_weight_snapshot=template_weight_snapshot,
            section_scores=section_scores,
            strengths=strengths,
            weaknesses=weaknesses,
            summary_notes=summary_notes,
            generated_by=generated_by,
            model_id=model_id,
            is_current=True
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result

    def get_by_id(self, result_id: int) -> Optional[InterviewResult]:
        """Fetch result by ID."""
        return self.db.query(InterviewResult).filter(InterviewResult.id == result_id).first()

    def get_current_by_interview(self, interview_id: int) -> Optional[InterviewResult]:
        """Fetch current result for interview (is_current=true)."""
        return self.db.query(InterviewResult).filter(
            InterviewResult.interview_id == interview_id,
            InterviewResult.is_current == True
        ).first()

    def mark_non_current(self, result_id: int) -> None:
        """Mark result as non-current (versioning flow)."""
        result = self.get_by_id(result_id)
        if result:
            result.is_current = False
            self.db.commit()

    def list_by_interview(self, interview_id: int) -> List[InterviewResult]:
        """List all results for interview (audit trail)."""
        return self.db.query(InterviewResult).filter(
            InterviewResult.interview_id == interview_id
        ).order_by(InterviewResult.created_at.desc()).all()

    def exists_for_interview(self, interview_id: int) -> bool:
        """Check if current result exists for interview."""
        return self.db.query(
            self.db.query(InterviewResult)
            .filter(
                InterviewResult.interview_id == interview_id,
                InterviewResult.is_current == True
            )
            .exists()
        ).scalar()
```

---

### SupplementaryReportRepository

**Responsibilities:**

- Create supplementary report
- Fetch reports by result
- Fetch reports by type

#### Methods

```python
class SupplementaryReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        interview_result_id: int,
        report_type: str,
        report_data: dict
    ) -> SupplementaryReport:
        """Create supplementary report."""
        report = SupplementaryReport(
            interview_result_id=interview_result_id,
            report_type=report_type,
            report_data=report_data
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def get_by_result(self, interview_result_id: int) -> List[SupplementaryReport]:
        """Fetch all reports for result."""
        return self.db.query(SupplementaryReport).filter(
            SupplementaryReport.interview_result_id == interview_result_id
        ).all()

    def get_by_type(
        self,
        interview_result_id: int,
        report_type: str
    ) -> Optional[SupplementaryReport]:
        """Fetch specific report type for result."""
        return self.db.query(SupplementaryReport).filter(
            SupplementaryReport.interview_result_id == interview_result_id,
            SupplementaryReport.report_type == report_type
        ).first()
```

---

## 4. Transaction Management

### Re-Evaluation Flow (Atomicity Required)

```python
from sqlalchemy.exc import IntegrityError

def reevaluate_exchange(
    db: Session,
    interview_exchange_id: int,
    new_evaluation_data: dict
) -> Evaluation:
    """
    Re-evaluate exchange (atomic transaction).

    Steps:
    1. Mark old evaluation is_final = false
    2. Create new evaluation with is_final = true
    3. Create new dimension scores

    Must be atomic (single transaction).
    """
    try:
        # Start transaction (implicit with SQLAlchemy Session)

        # Step 1: Mark old as non-final
        old_evaluation = db.query(Evaluation).filter(
            Evaluation.interview_exchange_id == interview_exchange_id,
            Evaluation.is_final == True
        ).first()

        if old_evaluation:
            old_evaluation.is_final = False

        # Step 2: Create new evaluation
        new_evaluation = Evaluation(
            interview_exchange_id=interview_exchange_id,
            is_final=True,
            **new_evaluation_data
        )
        db.add(new_evaluation)
        db.flush()  # Get ID without committing

        # Step 3: Create dimension scores
        dimension_scores = [
            EvaluationDimensionScore(
                evaluation_id=new_evaluation.id,
                **score_data
            )
            for score_data in new_evaluation_data['dimension_scores']
        ]
        db.add_all(dimension_scores)

        # Commit transaction
        db.commit()
        db.refresh(new_evaluation)
        return new_evaluation

    except IntegrityError as e:
        db.rollback()
        raise DuplicateEvaluationError("Duplicate evaluation detected") from e
    except Exception as e:
        db.rollback()
        raise
```

---

### Finalization Flow (Atomic)

```python
def finalize_interview(
    db: Session,
    interview_id: int,
    result_data: dict
) -> InterviewResult:
    """
    Finalize interview result (atomic transaction).

    Steps:
    1. Mark old result is_current = false
    2. Create new result with is_current = true
    3. Create supplementary reports

    Must be atomic.
    """
    try:
        # Step 1: Mark old as non-current
        old_result = db.query(InterviewResult).filter(
            InterviewResult.interview_id == interview_id,
            InterviewResult.is_current == True
        ).first()

        if old_result:
            old_result.is_current = False

        # Step 2: Create new result
        new_result = InterviewResult(
            interview_id=interview_id,
            is_current=True,
            **result_data
        )
        db.add(new_result)
        db.flush()

        # Step 3: Create supplementary reports (if any)
        if 'supplementary_reports' in result_data:
            reports = [
                SupplementaryReport(
                    interview_result_id=new_result.id,
                    **report_data
                )
                for report_data in result_data['supplementary_reports']
            ]
            db.add_all(reports)

        # Commit
        db.commit()
        db.refresh(new_result)
        return new_result

    except IntegrityError as e:
        db.rollback()
        raise DuplicateResultError("Duplicate current result detected") from e
    except Exception as e:
        db.rollback()
        raise
```

---

## 5. Concurrency Handling

### Row-Level Locking (SELECT FOR UPDATE)

**When needed:**

- Re-evaluation: Prevent two workers from marking same evaluation non-final
- Finalization: Prevent two workers from creating duplicate current result

**Example:**

```python
def reevaluate_exchange_with_lock(
    db: Session,
    interview_exchange_id: int,
    new_evaluation_data: dict
) -> Evaluation:
    """Re-evaluate with row-level locking."""
    try:
        # Acquire lock on old evaluation
        old_evaluation = db.query(Evaluation).filter(
            Evaluation.interview_exchange_id == interview_exchange_id,
            Evaluation.is_final == True
        ).with_for_update().first()

        if old_evaluation:
            old_evaluation.is_final = False

        # Create new evaluation
        new_evaluation = Evaluation(
            interview_exchange_id=interview_exchange_id,
            is_final=True,
            **new_evaluation_data
        )
        db.add(new_evaluation)
        db.commit()
        return new_evaluation

    except Exception as e:
        db.rollback()
        raise
```

---

## 6. Exception Handling

### Custom Exceptions

```python
class PersistenceError(Exception):
    """Base exception for persistence errors."""
    pass

class DuplicateEvaluationError(PersistenceError):
    """Duplicate evaluation (UNIQUE constraint violation)."""
    pass

class DuplicateResultError(PersistenceError):
    """Duplicate current result (UNIQUE constraint violation)."""
    pass

class EvaluationNotFoundError(PersistenceError):
    """Evaluation not found."""
    pass

class ResultNotFoundError(PersistenceError):
    """Interview result not found."""
    pass
```

---

## 7. Testing Requirements

### Unit Tests (Repository Methods)

1. **Create evaluation:** Valid data → evaluation created
2. **Create duplicate:** UNIQUE constraint → IntegrityError
3. **Mark non-final:** is_final updated to false
4. **Fetch by exchange:** Returns correct evaluation
5. **Create dimension scores:** Batch insert succeeds
6. **Create result:** Valid data → result created
7. **Fetch current result:** Returns correct result

### Integration Tests (Transactions)

1. **Re-evaluation flow:** Old marked non-final, new created atomically
2. **Finalization flow:** Old marked non-current, new created atomically
3. **Concurrent re-evaluation:** Second transaction blocked by lock
4. **Rollback on error:** Transaction rolled back, no partial data

### Concurrency Tests

1. **Simultaneous evaluation:** Second INSERT fails with IntegrityError
2. **Simultaneous finalization:** Second INSERT fails with IntegrityError
3. **Row-level locking:** Second transaction waits for lock release

---

## 8. Critical Risks

1. **No UNIQUE constraint:** Duplicate evaluations created
2. **No transaction:** Partial data persisted on error
3. **No row locking:** Race condition in re-evaluation
4. **No CASCADE delete:** Orphaned dimension scores
5. **No CHECK constraint:** Invalid values persisted (normalized_score > 100)

---

## 9. Future Enhancements

1. **Soft delete:** Mark evaluations as deleted instead of CASCADE
2. **Audit log:** Track all changes to evaluations/results
3. **Read replicas:** Offload reads to replica database
4. **Partitioning:** Partition interview_results by date
5. **Indexing optimization:** Add indexes for common queries

---

**End of Evaluation Persistence Requirements**
