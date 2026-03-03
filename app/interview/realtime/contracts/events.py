"""
WebSocket Event Pydantic Models

Strict schemas for client→server and server→client WebSocket events.
Follows the protocol defined in interview/realtime/REQUIREMENTS.md.

All events are Pydantic BaseModel subclasses with Literal event_type fields.
Client events are validated via parse_client_event() before dispatch.
Server events are serialized via .model_dump() for JSON transmission.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Type, Union

from pydantic import BaseModel, Field


# ============================================================================
# Client → Server Events
# ============================================================================


class ClientEvent(BaseModel):
    """Base model for all client-to-server WebSocket events."""

    event_type: str


class JoinSessionEvent(ClientEvent):
    """
    Client requests to join interview session.

    Sent immediately after WebSocket connection is established.
    Server responds with SessionJoinedEvent or closes connection.
    """

    event_type: Literal["join_session"] = "join_session"
    submission_id: int


class RequestNextQuestionEvent(ClientEvent):
    """
    Client requests next question in sequence.

    Server resolves next question from template snapshot and delivers
    QuestionPayloadEvent, or InterviewCompletedEvent if all questions done.
    """

    event_type: Literal["request_next_question"] = "request_next_question"
    submission_id: int


class SubmitAnswerEvent(ClientEvent):
    """
    Client submits text answer for current question.

    exchange_id: Sequence order correlation from QuestionPayloadEvent.
    response_text: Candidate's text response (may be empty for skipped).
    response_time_ms: Time taken to answer in milliseconds (must be > 0).
    """

    event_type: Literal["submit_answer"] = "submit_answer"
    exchange_id: int
    response_text: str
    response_time_ms: int = Field(gt=0)


class SubmitCodeEvent(ClientEvent):
    """
    Client submits code answer for coding question.

    exchange_id: Sequence order correlation from QuestionPayloadEvent.
    response_code: Source code (1–100,000 chars).
    response_language: Programming language (python, java, cpp).
    response_time_ms: Time taken in milliseconds (must be > 0).
    """

    event_type: Literal["submit_code"] = "submit_code"
    exchange_id: int
    response_code: str = Field(min_length=1, max_length=100_000)
    response_language: Literal["python", "java", "cpp"]
    response_time_ms: int = Field(gt=0)


class HeartbeatEvent(ClientEvent):
    """
    Client heartbeat to keep WebSocket connection alive.

    Refreshes Redis TTL for active_websocket key (60s).
    Server responds with HeartbeatAckEvent.
    """

    event_type: Literal["heartbeat"] = "heartbeat"
    timestamp: str


# ============================================================================
# Server → Client Events
# ============================================================================


class ServerEvent(BaseModel):
    """Base model for all server-to-client WebSocket events."""

    event_type: str


class ConnectionEstablishedEvent(ServerEvent):
    """Sent after successful WebSocket connection acceptance."""

    event_type: Literal["connection_established"] = "connection_established"
    submission_id: int
    connection_id: str
    server_time: str


class SessionJoinedEvent(ServerEvent):
    """Sent after client sends join_session, returns current session state."""

    event_type: Literal["session_joined"] = "session_joined"
    submission_id: int
    submission_status: str
    current_sequence: int
    total_questions: int
    progress_percentage: float
    time_remaining_seconds: Optional[int] = None
    started_at: Optional[str] = None
    expires_at: Optional[str] = None


class QuestionPayloadEvent(ServerEvent):
    """
    Delivers next question to candidate.

    exchange_id: Sequence order (protocol-level correlation identifier).
    For coding questions, starter_code and test_cases are populated.
    """

    event_type: Literal["question_payload"] = "question_payload"
    exchange_id: int  # Sequence order used as protocol-level correlation
    sequence_order: int
    question_text: str
    question_type: str  # "behavioral" | "technical" | "situational" | "coding"
    question_difficulty: str  # "easy" | "medium" | "hard"
    section_name: str
    time_limit_seconds: Optional[int] = None
    is_final_question: bool = False
    # Coding-specific
    starter_code: Optional[str] = None
    test_cases: Optional[List[Dict[str, str]]] = None


class AnswerAcceptedEvent(ServerEvent):
    """Sent after text answer is accepted and exchange is created."""

    event_type: Literal["answer_accepted"] = "answer_accepted"
    exchange_id: int
    sequence_order: int
    next_sequence: Optional[int] = None
    progress_percentage: float
    message: str = "Answer submitted successfully!"


class CodeSubmissionAcceptedEvent(ServerEvent):
    """Sent after code submission accepted (execution pending)."""

    event_type: Literal["code_submission_accepted"] = "code_submission_accepted"
    exchange_id: int
    code_submission_id: Optional[int] = None
    execution_status: str = "pending"
    message: str = "Code submitted successfully. Execution in progress..."
    estimated_execution_time_seconds: int = 10


class CodeExecutionCompletedEvent(ServerEvent):
    """Sent asynchronously after code execution finishes."""

    event_type: Literal["code_execution_completed"] = "code_execution_completed"
    exchange_id: int
    code_submission_id: Optional[int] = None
    execution_status: str
    score: Optional[float] = None
    test_results_summary: Optional[str] = None
    execution_time_ms: Optional[int] = None
    next_sequence: Optional[int] = None
    progress_percentage: Optional[float] = None


class TimerUpdateEvent(ServerEvent):
    """Periodic timer broadcast (every 60 seconds)."""

    event_type: Literal["timer_update"] = "timer_update"
    time_remaining_seconds: int
    progress_percentage: float
    current_sequence: int
    total_questions: int


class ProgressUpdateEvent(ServerEvent):
    """Sent after each exchange creation with updated progress."""

    event_type: Literal["progress_update"] = "progress_update"
    current_sequence: int
    total_questions: int
    progress_percentage: float
    section_progress: Optional[Dict[str, Dict[str, int]]] = None


class InterviewCompletedEvent(ServerEvent):
    """Sent when interview completes (all questions answered or manually submitted)."""

    event_type: Literal["interview_completed"] = "interview_completed"
    submission_id: int
    completion_reason: str  # "submitted" | "all_questions_answered"
    submitted_at: Optional[str] = None
    exchanges_completed: int
    total_questions: int
    message: str = "Interview completed successfully!"
    next_steps: str = "Results will be available within 24 hours."


class InterviewExpiredEvent(ServerEvent):
    """Sent when interview times out."""

    event_type: Literal["interview_expired"] = "interview_expired"
    submission_id: int
    expired_at: str
    exchanges_completed: int
    total_questions: int
    auto_submitted: bool = True
    message: str = (
        "Interview time expired. Your responses have been automatically submitted."
    )


class ErrorEvent(ServerEvent):
    """Sent on validation or server error."""

    event_type: Literal["error_event"] = "error_event"
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


class ConnectionReplacedEvent(ServerEvent):
    """Sent to old connection when a new connection replaces it."""

    event_type: Literal["connection_replaced"] = "connection_replaced"
    message: str = (
        "New connection established from another client. This connection will close."
    )
    new_connection_id: str
    timestamp: str


class HeartbeatAckEvent(ServerEvent):
    """Response to client heartbeat."""

    event_type: Literal["heartbeat_ack"] = "heartbeat_ack"
    server_time: str
    time_remaining_seconds: Optional[int] = None


# ============================================================================
# Event Parsing
# ============================================================================

CLIENT_EVENT_TYPE_MAP: Dict[str, Type[ClientEvent]] = {
    "join_session": JoinSessionEvent,
    "request_next_question": RequestNextQuestionEvent,
    "submit_answer": SubmitAnswerEvent,
    "submit_code": SubmitCodeEvent,
    "heartbeat": HeartbeatEvent,
}


def parse_client_event(data: Dict[str, Any]) -> ClientEvent:
    """
    Parse raw JSON dict into typed client event.

    Args:
        data: Parsed JSON dict from WebSocket message.

    Returns:
        Validated ClientEvent subclass instance.

    Raises:
        ValueError: If event_type is missing or unknown.
        pydantic.ValidationError: If payload fails schema validation.
    """
    event_type = data.get("event_type")
    if not event_type:
        raise ValueError("Missing 'event_type' in WebSocket message")

    event_class = CLIENT_EVENT_TYPE_MAP.get(event_type)
    if not event_class:
        raise ValueError(f"Unknown event_type: {event_type}")

    return event_class.model_validate(data)
