"""
Proctoring Module

Advisory integrity signal collection, rule-based severity assignment,
deterministic risk scoring, and admin review queue.

This module OBSERVES. It does NOT DECIDE.
Signals are ADVISORY. Humans make consequential decisions.

Submodules:
- ingestion/: Event intake, validation, deduplication
- rules/: Severity & weight assignment, clustering detection
- risk_model/: Aggregated risk score computation, classification
- persistence/: Immutable event storage & retrieval
"""
