#!/usr/bin/env python3
"""
Isolated Interview Flow Test Script

Verifies the complete interview flow by connecting ONLY via HTTP/WebSocket.
No local imports - purely network-based testing.

Usage:
    python test_interview_flow.py

Configuration (environment variables):
    TEST_BASE_URL       - Backend URL (default: http://135.235.195.83:8000)
    TEST_EMAIL          - Candidate email
    TEST_PASSWORD       - Candidate password
    TEST_SUBMISSION_ID  - Existing submission ID to use
    
Or modify the CONFIG dict below directly.
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

# ============================================================================
# Configuration
# ============================================================================

CONFIG = {
    "base_url": os.getenv("TEST_BASE_URL", "http://135.235.195.83:8000"),
    "email": os.getenv("TEST_EMAIL", "jithsunghsai@outlook.com"),
    "password": os.getenv("TEST_PASSWORD", "Vallabha@2518"),
    "submission_id": int(os.getenv("TEST_SUBMISSION_ID", "0")),  # 0 = auto-create new session
    "window_id": 1,
    "template_id": 3,
    "timeout_seconds": 120,
    "answer_delay_ms": 2000,  # Simulate thinking time
}


# ============================================================================
# Logging
# ============================================================================

def log(level: str, msg: str, data: Any = None):
    """Structured logging with timestamp."""
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    prefix = {
        "INFO": "ℹ️ ",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "SEND": "📤",
        "RECV": "📥",
        "WARN": "⚠️ ",
    }.get(level, "  ")
    
    print(f"[{ts}] {prefix} {msg}")
    if data:
        if isinstance(data, dict):
            print(f"         {json.dumps(data, indent=2, default=str)}")
        else:
            print(f"         {data}")


# ============================================================================
# HTTP Client
# ============================================================================

@dataclass
class AuthTokens:
    access_token: str
    refresh_token: str
    token_type: str


class APIClient:
    """Simple HTTP client for REST API calls."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.tokens: Optional[AuthTokens] = None
        self._client = httpx.Client(timeout=30.0)
    
    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.tokens:
            headers["Authorization"] = f"Bearer {self.tokens.access_token}"
        return headers
    
    def login(self, email: str, password: str) -> AuthTokens:
        """POST /api/v1/auth/login"""
        log("INFO", f"Logging in as {email}...")
        
        resp = self._client.post(
            f"{self.base_url}/api/v1/auth/login",
            json={"email": email, "password": password},
            headers={"Content-Type": "application/json"},
        )
        
        if resp.status_code != 200:
            log("ERROR", f"Login failed: {resp.status_code}", resp.text)
            raise Exception(f"Login failed: {resp.status_code} - {resp.text}")
        
        data = resp.json()
        self.tokens = AuthTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            token_type=data["token_type"],
        )
        log("SUCCESS", "Login successful", {"user_id": data.get("user", {}).get("user_id")})
        return self.tokens
    
    def get_candidate_windows(self) -> List[Dict]:
        """GET /api/v1/candidate/windows"""
        log("INFO", "Fetching candidate windows...")
        
        resp = self._client.get(
            f"{self.base_url}/api/v1/candidate/windows",
            headers=self._headers(),
        )
        
        if resp.status_code != 200:
            log("ERROR", f"Failed to get windows: {resp.status_code}", resp.text)
            raise Exception(f"Get windows failed: {resp.text}")
        
        windows = resp.json()
        log("SUCCESS", f"Found {len(windows)} windows")
        return windows
    
    def get_candidate_submissions(self) -> List[Dict]:
        """GET /api/v1/candidate/submissions"""
        log("INFO", "Fetching candidate submissions...")
        
        resp = self._client.get(
            f"{self.base_url}/api/v1/candidate/submissions",
            headers=self._headers(),
        )
        
        if resp.status_code != 200:
            log("ERROR", f"Failed to get submissions: {resp.status_code}", resp.text)
            raise Exception(f"Get submissions failed: {resp.text}")
        
        data = resp.json()
        # API returns {data: [], pagination: {}}
        submissions = data.get("data", data) if isinstance(data, dict) else data
        log("SUCCESS", f"Found {len(submissions)} submissions")
        for s in submissions[:5]:  # Log first 5
            log("INFO", f"  - submission_id={s.get('submission_id')}, status={s.get('status')}")
        return submissions
    
    def start_practice_session(self, template_id: int, experience_level: str = "mid_level") -> Dict:
        """POST /api/v1/candidate/practice/start"""
        log("INFO", f"Starting practice session with template_id={template_id}...")
        
        resp = self._client.post(
            f"{self.base_url}/api/v1/candidate/practice/start",
            json={
                "template_id": template_id,
                "consent_accepted": True,
                "experience_level": experience_level,
            },
            headers=self._headers(),
        )
        
        if resp.status_code not in (200, 201):
            error_text = resp.text
            # Try to parse error for better message
            try:
                err = resp.json().get("error", {})
                if "no available questions" in error_text.lower() or "total_questions" in error_text.lower():
                    log("ERROR", "Template has no questions - database may need migrations!")
                    log("ERROR", "Run: DEV-16_populate-question-topics.sql on the database")
            except:
                pass
            log("ERROR", f"Failed to start practice: {resp.status_code}", error_text)
            raise Exception(f"Start practice failed: {error_text}")
        
        data = resp.json()
        log("SUCCESS", "Practice session created", {
            "submission_id": data.get("submission_id"),
            "status": data.get("status"),
        })
        return data
    
    def get_practice_templates(self) -> List[Dict]:
        """GET /api/v1/candidate/practice/templates"""
        log("INFO", "Fetching practice templates...")
        
        resp = self._client.get(
            f"{self.base_url}/api/v1/candidate/practice/templates",
            headers=self._headers(),
        )
        
        if resp.status_code != 200:
            log("ERROR", f"Failed to get templates: {resp.status_code}", resp.text)
            return []
        
        data = resp.json()
        templates = data.get("templates", data) if isinstance(data, dict) else data
        log("SUCCESS", f"Found {len(templates)} templates")
        for t in templates[:5]:
            log("INFO", f"  - id={t.get('id')}: {t.get('name')} ({t.get('category')})")
        return templates
    
    def start_interview(self, submission_id: int, consent_accepted: bool = True) -> Dict:
        """POST /api/v1/interviews/sessions/start"""
        log("INFO", f"Starting interview for submission_id={submission_id}...")
        
        resp = self._client.post(
            f"{self.base_url}/api/v1/interviews/sessions/start",
            json={
                "submission_id": submission_id,
                "consent_accepted": consent_accepted,
            },
            headers=self._headers(),
        )
        
        # 409 Conflict means already started - that's OK
        if resp.status_code == 409:
            log("WARN", "Interview already in progress (409 Conflict)")
            return {"status": "in_progress", "submission_id": submission_id}
        
        if resp.status_code != 200:
            log("ERROR", f"Failed to start interview: {resp.status_code}", resp.text)
            raise Exception(f"Start interview failed: {resp.text}")
        
        data = resp.json()
        log("SUCCESS", "Interview started", {
            "submission_id": data.get("submission_id"),
            "status": data.get("status"),
        })
        return data
    
    def complete_interview(self, submission_id: int) -> Dict:
        """POST /api/v1/interviews/sessions/complete"""
        log("INFO", f"Completing interview submission_id={submission_id}...")
        
        resp = self._client.post(
            f"{self.base_url}/api/v1/interviews/sessions/complete",
            json={"submission_id": submission_id},
            headers=self._headers(),
        )
        
        if resp.status_code != 200:
            log("WARN", f"Complete interview response: {resp.status_code}", resp.text)
        
        return resp.json() if resp.status_code == 200 else {}


# ============================================================================
# WebSocket Client
# ============================================================================

class InterviewWebSocket:
    """WebSocket client for interview flow."""
    
    def __init__(self, base_url: str, submission_id: int, access_token: str):
        # Convert http to ws
        ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        self.url = f"{ws_url}/ws/interview/{submission_id}?token={access_token}"
        self.submission_id = submission_id
        self.ws = None
        self.events_received: List[Dict] = []
        self.current_question: Optional[Dict] = None
        self.session_state: Optional[Dict] = None
    
    async def connect(self):
        """Establish WebSocket connection."""
        log("INFO", f"Connecting to WebSocket...")
        log("INFO", f"URL: {self.url[:80]}...")
        
        self.ws = await websockets.connect(
            self.url,
            ping_interval=20,
            ping_timeout=10,
        )
        log("SUCCESS", "WebSocket connected")
        
        # Wait for connection_established
        event = await self._recv()
        if event.get("event_type") != "connection_established":
            raise Exception(f"Expected connection_established, got: {event}")
        
        log("SUCCESS", "Connection established", {
            "connection_id": event.get("connection_id"),
            "server_time": event.get("server_time"),
        })
    
    async def _send(self, event: Dict):
        """Send event to server."""
        log("SEND", event.get("event_type", "unknown"), event)
        await self.ws.send(json.dumps(event))
    
    async def _recv(self, timeout: float = 30.0) -> Dict:
        """Receive event from server."""
        try:
            msg = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
            event = json.loads(msg)
            self.events_received.append(event)
            log("RECV", event.get("event_type", "unknown"), event)
            return event
        except asyncio.TimeoutError:
            log("ERROR", f"Receive timeout after {timeout}s")
            raise
    
    async def join_session(self) -> Dict:
        """Send join_session and wait for session_joined."""
        await self._send({
            "event_type": "join_session",
            "submission_id": self.submission_id,
        })
        
        event = await self._recv()
        
        # If interview already completed
        if event.get("event_type") == "interview_completed":
            log("WARN", "Interview already completed!")
            return event
        
        if event.get("event_type") != "session_joined":
            raise Exception(f"Expected session_joined, got: {event}")
        
        self.session_state = event
        log("SUCCESS", "Session joined", {
            "status": event.get("submission_status"),
            "current_sequence": event.get("current_sequence"),
            "total_questions": event.get("total_questions"),
            "progress": event.get("progress_percentage"),
        })
        return event
    
    async def request_next_question(self) -> Dict:
        """Send request_next_question and wait for question_payload or interview_completed."""
        await self._send({
            "event_type": "request_next_question",
            "submission_id": self.submission_id,
        })
        
        event = await self._recv()
        
        if event.get("event_type") == "interview_completed":
            log("SUCCESS", "Interview completed!", {
                "exchanges_completed": event.get("exchanges_completed"),
                "total_questions": event.get("total_questions"),
                "reason": event.get("completion_reason"),
            })
            return event
        
        if event.get("event_type") == "error_event":
            log("ERROR", "Error from server", event)
            raise Exception(f"Server error: {event.get('message')}")
        
        if event.get("event_type") != "question_payload":
            raise Exception(f"Expected question_payload, got: {event}")
        
        self.current_question = event
        log("SUCCESS", "Question received", {
            "sequence": event.get("sequence_order"),
            "section": event.get("section_name"),
            "type": event.get("question_type"),
            "difficulty": event.get("question_difficulty"),
            "is_final": event.get("is_final_question"),
        })
        return event
    
    async def submit_answer(self, response_text: str, response_time_ms: int) -> Dict:
        """Submit answer and wait for answer_accepted."""
        if not self.current_question:
            raise Exception("No current question to answer")
        
        exchange_id = self.current_question["exchange_id"]
        
        await self._send({
            "event_type": "submit_answer",
            "exchange_id": exchange_id,
            "response_text": response_text,
            "response_time_ms": response_time_ms,
        })
        
        event = await self._recv()
        
        if event.get("event_type") == "error_event":
            log("ERROR", "Error submitting answer", event)
            raise Exception(f"Submit error: {event.get('message')}")
        
        if event.get("event_type") != "answer_accepted":
            raise Exception(f"Expected answer_accepted, got: {event}")
        
        log("SUCCESS", "Answer accepted", {
            "exchange_id": event.get("exchange_id"),
            "next_sequence": event.get("next_sequence"),
            "progress": event.get("progress_percentage"),
        })
        return event
    
    async def send_heartbeat(self) -> Dict:
        """Send heartbeat and wait for ack."""
        await self._send({
            "event_type": "heartbeat",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })
        
        event = await self._recv(timeout=5.0)
        if event.get("event_type") != "heartbeat_ack":
            log("WARN", f"Expected heartbeat_ack, got: {event.get('event_type')}")
        return event
    
    async def close(self):
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
            log("INFO", "WebSocket closed")


# ============================================================================
# Test Flow
# ============================================================================

def generate_answer(question: Dict) -> str:
    """Generate a test answer based on question type."""
    q_type = question.get("question_type", "technical")
    section = question.get("section_name", "unknown")
    q_text = question.get("question_text", "")[:100]
    
    answers = {
        "behavioral": (
            "In my previous role, I faced a similar challenge. I approached it by first "
            "analyzing the situation, then collaborating with my team to develop a solution. "
            "We implemented it incrementally and achieved positive results."
        ),
        "technical": (
            "The approach I would take involves understanding the core requirements first. "
            "Then I would design a solution that balances efficiency with maintainability. "
            "For implementation, I would use appropriate data structures and algorithms."
        ),
        "situational": (
            "In that situation, I would first assess the immediate priorities. Then I would "
            "communicate clearly with stakeholders about the trade-offs. Finally, I would "
            "execute the plan while monitoring for any issues."
        ),
    }
    
    base_answer = answers.get(q_type, answers["technical"])
    return f"[TEST ANSWER for {section}/{q_type}] {base_answer}"


async def run_interview_flow(config: Dict) -> Dict:
    """
    Execute full interview flow and return results.
    
    Returns:
        Dict with test results including questions answered, errors, etc.
    """
    results = {
        "success": False,
        "questions_answered": 0,
        "total_questions": 0,
        "errors": [],
        "events": [],
    }
    
    api = APIClient(config["base_url"])
    ws_client = None
    
    try:
        # Step 1: Login
        log("INFO", "=" * 60)
        log("INFO", "STEP 1: Authentication")
        log("INFO", "=" * 60)
        api.login(config["email"], config["password"])
        
        # Step 2: Get or create submission
        log("INFO", "=" * 60)
        log("INFO", "STEP 2: Get/Create Submission")
        log("INFO", "=" * 60)
        
        submission_id = config.get("submission_id", 0)
        
        if submission_id == 0:
            # First, show available templates
            log("INFO", "Checking available templates...")
            templates = api.get_practice_templates()
            
            target_template_id = config.get("template_id", 3)
            template_found = any(t.get("id") == target_template_id for t in templates)
            if not template_found and templates:
                log("WARN", f"Template {target_template_id} not found, using first template")
                target_template_id = templates[0]["id"]
            
            # Try to get existing submissions
            submissions = api.get_candidate_submissions()
            
            # Look for pending or in_progress submission for reuse
            pending = [s for s in submissions if s.get("status") == "pending"]
            in_progress = [s for s in submissions if s.get("status") == "in_progress"]
            
            if pending:
                submission_id = pending[0]["submission_id"]
                log("INFO", f"Using existing pending submission: {submission_id}")
            elif in_progress:
                submission_id = in_progress[0]["submission_id"]
                log("INFO", f"Using existing in_progress submission: {submission_id}")
            else:
                # Create new practice session
                log("INFO", f"No usable submission found, creating practice session with template_id={target_template_id}...")
                practice = api.start_practice_session(
                    template_id=target_template_id,
                    experience_level="mid_level",
                )
                submission_id = practice["submission_id"]
        
        log("SUCCESS", f"Using submission_id: {submission_id}")
        
        # Step 3: Start interview session
        log("INFO", "=" * 60)
        log("INFO", "STEP 3: Start Interview Session")
        log("INFO", "=" * 60)
        api.start_interview(submission_id, consent_accepted=True)
        
        # Step 4: Connect WebSocket
        log("INFO", "=" * 60)
        log("INFO", "STEP 4: WebSocket Connection")
        log("INFO", "=" * 60)
        ws_client = InterviewWebSocket(
            config["base_url"],
            submission_id,
            api.tokens.access_token,
        )
        await ws_client.connect()
        
        # Step 5: Join session
        log("INFO", "=" * 60)
        log("INFO", "STEP 5: Join Session")
        log("INFO", "=" * 60)
        session = await ws_client.join_session()
        
        if session.get("event_type") == "interview_completed":
            log("WARN", "Interview was already completed")
            results["success"] = True
            results["total_questions"] = session.get("total_questions", 0)
            results["questions_answered"] = session.get("exchanges_completed", 0)
            return results
        
        results["total_questions"] = session.get("total_questions", 0)
        
        # Step 6: Question-Answer loop
        log("INFO", "=" * 60)
        log("INFO", "STEP 6: Question-Answer Loop")
        log("INFO", "=" * 60)
        
        max_questions = 50  # Safety limit
        questions_processed = 0
        
        while questions_processed < max_questions:
            # Request next question
            question = await ws_client.request_next_question()
            
            if question.get("event_type") == "interview_completed":
                log("SUCCESS", "All questions completed!")
                results["questions_answered"] = question.get("exchanges_completed", questions_processed)
                break
            
            questions_processed += 1
            
            # Display question
            log("INFO", f"Question {questions_processed}: {question.get('question_text', '')[:100]}...")
            
            # Simulate thinking time
            think_time = config.get("answer_delay_ms", 2000)
            log("INFO", f"Simulating {think_time}ms think time...")
            await asyncio.sleep(think_time / 1000)
            
            # Generate and submit answer
            answer = generate_answer(question)
            log("INFO", f"Submitting answer ({len(answer)} chars)...")
            
            await ws_client.submit_answer(
                response_text=answer,
                response_time_ms=think_time + 1000,
            )
            
            results["questions_answered"] = questions_processed
            
            # Check if this was the final question
            if question.get("is_final_question"):
                log("INFO", "That was the final question, requesting completion...")
                # Request next to get interview_completed
                completion = await ws_client.request_next_question()
                if completion.get("event_type") == "interview_completed":
                    log("SUCCESS", "Interview completed!")
                    results["questions_answered"] = completion.get("exchanges_completed", questions_processed)
                break
        
        results["success"] = True
        results["events"] = ws_client.events_received
        
    except Exception as e:
        log("ERROR", f"Test failed: {str(e)}")
        results["errors"].append(str(e))
        import traceback
        traceback.print_exc()
    
    finally:
        if ws_client:
            await ws_client.close()
    
    return results


def print_summary(results: Dict):
    """Print test summary."""
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    status = "✅ PASSED" if results["success"] else "❌ FAILED"
    print(f"Status: {status}")
    print(f"Questions Answered: {results['questions_answered']} / {results['total_questions']}")
    
    if results["errors"]:
        print(f"Errors: {len(results['errors'])}")
        for err in results["errors"]:
            print(f"  - {err}")
    
    print(f"Total Events: {len(results.get('events', []))}")
    
    # Event breakdown
    events = results.get("events", [])
    event_types = {}
    for e in events:
        t = e.get("event_type", "unknown")
        event_types[t] = event_types.get(t, 0) + 1
    
    if event_types:
        print("Event Types:")
        for t, count in sorted(event_types.items()):
            print(f"  - {t}: {count}")
    
    print("=" * 60)


# ============================================================================
# Main
# ============================================================================

async def main():
    print("=" * 60)
    print("INTERVIEW FLOW TEST")
    print(f"Target: {CONFIG['base_url']}")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)
    print()
    
    results = await run_interview_flow(CONFIG)
    print_summary(results)
    
    return 0 if results["success"] else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(130)
