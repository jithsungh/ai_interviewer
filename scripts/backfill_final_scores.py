#!/usr/bin/env python
"""
Backfill script to calculate final_score for completed submissions.

Runs aggregation for all submissions where status='completed' and final_score IS NULL.
"""

import asyncio
import logging
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def backfill_scores():
    """Calculate and store final_score for all completed submissions without scores."""
    from app.persistence.postgres.session import init_session_factory, get_session_factory
    from app.interview.session.persistence.models import InterviewSubmissionModel
    from app.evaluation.aggregation.service import AggregationService
    
    # Initialize session factory
    init_session_factory()
    SessionLocal = get_session_factory()
    
    db = SessionLocal()
    try:
        # Find all completed submissions without scores
        missing_score_subs = db.query(InterviewSubmissionModel).filter(
            InterviewSubmissionModel.status == 'completed',
            InterviewSubmissionModel.final_score.is_(None),
        ).order_by(InterviewSubmissionModel.id.desc()).all()
        
        logger.info(f"Found {len(missing_score_subs)} submissions needing score calculation")
        
        if not missing_score_subs:
            logger.info("No submissions to process!")
            return
        
        # Process each submission
        success_count = 0
        error_count = 0
        
        for sub in missing_score_subs:
            logger.info(f"Processing submission {sub.id}...")
            
            try:
                # Create aggregation service
                agg_service = AggregationService(db=db)
                
                # Get result from aggregation
                result_data = await agg_service.aggregate_interview_result(
                    submission_id=sub.id,
                    generated_by="system:backfill",
                )
                
                # Update final_score
                sub.final_score = result_data.normalized_score
                db.commit()
                
                logger.info(
                    f"✓ Submission {sub.id}: final_score = {result_data.normalized_score}"
                )
                success_count += 1
                
            except Exception as e:
                logger.error(f"✗ Submission {sub.id}: {str(e)}")
                error_count += 1
                db.rollback()
            
            # Small delay to avoid overwhelming the system
            await asyncio.sleep(0.5)
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info(f"BACKFILL COMPLETE")
        logger.info(f"  Successful: {success_count}")
        logger.info(f"  Errors:     {error_count}")
        logger.info("="*60)
        
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(backfill_scores())
