"""
Realtime WebSocket Event Contracts

Defines strict Pydantic schemas for all bidirectional WebSocket events.
This is the single source of truth for the interview WebSocket protocol.

Client → Server Events:
- JoinSessionEvent: Join interview session after connection
- RequestNextQuestionEvent: Request next question in sequence
- SubmitAnswerEvent: Submit text answer for current question
- SubmitCodeEvent: Submit code answer for coding question
- HeartbeatEvent: Keep connection alive

Server → Client Events:
- ConnectionEstablishedEvent: Connection accepted
- SessionJoinedEvent: Session state after join
- QuestionPayloadEvent: Deliver question to candidate
- AnswerAcceptedEvent: Text answer accepted
- CodeSubmissionAcceptedEvent: Code submission accepted (execution pending)
- CodeExecutionCompletedEvent: Code execution result
- TimerUpdateEvent: Periodic time remaining update
- ProgressUpdateEvent: Post-exchange progress snapshot
- InterviewCompletedEvent: Interview finished (submitted)
- InterviewExpiredEvent: Interview timed out
- ErrorEvent: Validation or server error
- ConnectionReplacedEvent: Connection replaced by new client
- HeartbeatAckEvent: Heartbeat acknowledgement

Error Codes:
- INVALID_EXCHANGE_ID, SEQUENCE_MISMATCH, EMPTY_RESPONSE
- INTERVIEW_EXPIRED, INTERVIEW_COMPLETED, VALIDATION_ERROR, SERVER_ERROR
"""

from .events import (
    # Client → Server
    ClientEvent,
    JoinSessionEvent,
    RequestNextQuestionEvent,
    SubmitAnswerEvent,
    SubmitCodeEvent,
    HeartbeatEvent,
    # Server → Client
    ServerEvent,
    ConnectionEstablishedEvent,
    SessionJoinedEvent,
    QuestionPayloadEvent,
    AnswerAcceptedEvent,
    CodeSubmissionAcceptedEvent,
    CodeExecutionCompletedEvent,
    TimerUpdateEvent,
    ProgressUpdateEvent,
    InterviewCompletedEvent,
    InterviewExpiredEvent,
    ErrorEvent,
    ConnectionReplacedEvent,
    HeartbeatAckEvent,
    # Parsing
    parse_client_event,
    CLIENT_EVENT_TYPE_MAP,
)

__all__ = [
    # Client → Server
    "ClientEvent",
    "JoinSessionEvent",
    "RequestNextQuestionEvent",
    "SubmitAnswerEvent",
    "SubmitCodeEvent",
    "HeartbeatEvent",
    # Server → Client
    "ServerEvent",
    "ConnectionEstablishedEvent",
    "SessionJoinedEvent",
    "QuestionPayloadEvent",
    "AnswerAcceptedEvent",
    "CodeSubmissionAcceptedEvent",
    "CodeExecutionCompletedEvent",
    "TimerUpdateEvent",
    "ProgressUpdateEvent",
    "InterviewCompletedEvent",
    "InterviewExpiredEvent",
    "ErrorEvent",
    "ConnectionReplacedEvent",
    "HeartbeatAckEvent",
    # Parsing
    "parse_client_event",
    "CLIENT_EVENT_TYPE_MAP",
]
