# Audio Analysis Module

## 1. Purpose

**Why this submodule exists:**

The Audio Analysis module extracts **behavioral signals** from transcripts and audio metadata. It:

- Classifies sentence completeness (complete vs incomplete)
- Detects filler words (um, uh, like, you know)
- Calculates speech rate (words per minute)
- Identifies long pauses (silence within speech)
- Performs sentiment analysis (confidence, hesitation, frustration)
- Flags behavioral anomalies (excessive fillers, abnormally slow speech)

**Critical responsibility:** Analysis must be **deterministic** and **rule-based** where possible (e.g., completeness classifier uses NLP parsing, not LLMs). Sentiment is derived from acoustic features + transcript patterns, NOT subjective interpretation.

---

## 2. Owned Tables / Entities

**None.** This module is stateless. All analysis results are aggregated into `AudioSignal` by the parent `audio` module and persisted to `audio_analytics`.

---

## 3. Input Contracts

### CompletenessRequest

```python
@dataclass
class CompletenessRequest:
    transcript: str                    # REQUIRED: Full transcript text
    segments: List[TranscriptSegment]  # Optional: Word-level segments for context
```

### FillerDetectionRequest

```python
@dataclass
class FillerDetectionRequest:
    transcript: str                    # REQUIRED: Full transcript
    context_aware: bool = True         # Use NLP to distinguish filler vs verb (e.g., "like")
```

### SpeechRateRequest

```python
@dataclass
class SpeechRateRequest:
    transcript: str                         # REQUIRED: Full transcript
    segments: List[TranscriptSegment]       # REQUIRED: Word timestamps
    exclude_pauses: bool = True             # Exclude pause time from rate calculation
```

### SentimentRequest

```python
@dataclass
class SentimentRequest:
    transcript: str                         # REQUIRED: Full transcript
    audio_features: Optional[Dict] = None   # Optional: Prosody, pitch, volume
```

---

## 4. Output Contracts

### CompletenessResult

```python
@dataclass
class CompletenessResult:
    speech_state: Literal["complete", "incomplete", "continuing"]
    sentence_complete: bool              # Grammatically complete sentence
    confidence: float                    # 0.0-1.0 (how confident in classification)
    incomplete_reason: Optional[str] = None  # e.g., "ends_with_conjunction", "missing_complement"
    linguistic_features: Dict[str, Any] = {}  # Parse tree depth, POS tags, etc.
```

### FillerDetectionResult

```python
@dataclass
class FillerDetectionResult:
    filler_word_count: int               # Total filler words detected
    filler_rate: float                   # Fillers per total words (0.0-1.0)
    filler_positions: List[FillerWord]   # Where fillers occurred
```

### FillerWord

```python
@dataclass
class FillerWord:
    word: str                            # "um", "uh", "like"
    position: int                        # Word index in transcript
    timestamp_ms: Optional[int] = None   # When filler occurred
```

### SpeechRateResult

```python
@dataclass
class SpeechRateResult:
    speech_rate_wpm: float               # Words per minute
    total_words: int                     # Total words in transcript
    speech_duration_ms: int              # Actual speech time (excluding pauses)
    total_duration_ms: int               # Total time (including pauses)
    long_pause_count: int                # Pauses > 1000ms
    longest_pause_ms: int                # Longest single pause
```

### SentimentResult

```python
@dataclass
class SentimentResult:
    sentiment_score: float               # -1.0 (negative) to +1.0 (positive)
    confidence_level: Literal["high", "medium", "low"]  # Derived from prosody
    hesitation_detected: bool            # Excessive fillers, long pauses
    frustration_detected: bool           # Negative sentiment + tense prosody
```

---

## 5. Acceptance Criteria

### Functional Requirements

1. **Completeness Classifier:**
   - Use spaCy for dependency parsing
   - Complete: Has subject, verb, complement (if required), ends with punctuation
   - Incomplete: Missing complement, ends with conjunction, no verb
   - Confidence >0.8 for clear cases, <0.6 for ambiguous

2. **Filler Detection:**
   - Common fillers: um, uh, like, you know, so, basically, actually
   - Context-aware: "I like Python" → "like" is verb, not filler
   - Context-aware: "The answer is, like, dynamic programming" → "like" is filler

3. **Speech Rate:**
   - Calculate WPM excluding pause time
   - Detect long pauses (>1000ms)
   - Flag abnormally slow (<80 WPM) or fast (>200 WPM) speech

4. **Sentiment Analysis:**
   - Use VADER or TextBlob for text sentiment
   - If audio features available, combine with prosody (pitch, volume)
   - Hesitation: Excessive fillers (>15% rate) + long pauses
   - Frustration: Negative sentiment + rising pitch/volume

### Non-Functional Requirements

1. **Latency:** <500ms p95 for all analysis combined
2. **Determinism:** Same input → same output (no randomness)
3. **Accuracy:** Completeness classifier >85% accuracy on test set
4. **Language Support:** English primary, extensible to Spanish/French

---

## 6. Invariants & Constraints

### Must Hold

1. **Completeness Classification is Rule-Based:** No LLM calls (too slow, non-deterministic)
2. **Speech Rate Excludes Pauses:** WPM calculated on actual speech time, not total time
3. **Sentiment Score Normalized -1.0 to +1.0:** Consistent across sentiment engines
4. **Filler Rate Between 0.0 and 1.0:** Cannot exceed 100% of words

### Forbidden

- MUST NOT call LLMs for analysis (use rule-based NLP only)
- MUST NOT modify transcript (analysis is read-only)
- MUST NOT make subjective judgments (e.g., "candidate is lying" based on hesitation)
- MUST NOT block on external services (all analysis is local/synchronous)

---

## 7. Completeness Classifier Algorithm

```python
import spacy

class CompletenessClassifier:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")

    def evaluate(self, transcript: str) -> CompletenessResult:
        # Edge case: empty transcript
        if not transcript.strip():
            return CompletenessResult(
                speech_state="incomplete",
                sentence_complete=False,
                confidence=1.0,
                incomplete_reason="empty_transcript"
            )

        # Parse with spaCy
        doc = self.nlp(transcript)

        # Extract features
        has_punctuation = transcript[-1] in ".!?"
        ends_with_conjunction = self._ends_with_conjunction(doc)
        has_complete_clause = self._has_complete_clause(doc)
        has_dangling_preposition = self._has_dangling_preposition(doc)

        # Decision tree
        if has_punctuation and has_complete_clause:
            return CompletenessResult(
                speech_state="complete",
                sentence_complete=True,
                confidence=0.9
            )
        elif ends_with_conjunction:
            return CompletenessResult(
                speech_state="incomplete",
                sentence_complete=False,
                confidence=0.85,
                incomplete_reason="ends_with_conjunction"
            )
        elif has_dangling_preposition:
            return CompletenessResult(
                speech_state="incomplete",
                sentence_complete=False,
                confidence=0.8,
                incomplete_reason="dangling_preposition"
            )
        elif not has_complete_clause:
            return CompletenessResult(
                speech_state="incomplete",
                sentence_complete=False,
                confidence=0.75,
                incomplete_reason="missing_complement"
            )
        else:
            # Ambiguous case (structurally complete but no punctuation)
            return CompletenessResult(
                speech_state="continuing",
                sentence_complete=False,
                confidence=0.6,
                incomplete_reason="no_punctuation"
            )

    def _has_complete_clause(self, doc) -> bool:
        \"\"\"Check if sentence has subject + verb + complement (if required)\"\"\"
        has_subject = any(token.dep_ in ["nsubj", "nsubjpass"] for token in doc)
        has_verb = any(token.pos_ == "VERB" for token in doc)

        # If verb requires complement, check for it
        verb_tokens = [t for t in doc if t.pos_ == "VERB"]
        if verb_tokens:
            root_verb = [t for t in verb_tokens if t.dep_ == "ROOT"]
            if root_verb:
                has_complement = any(
                    child.dep_ in ["dobj", "attr", "acomp", "xcomp"]
                    for child in root_verb[0].children
                )
                return has_subject and has_verb and (has_complement or not self._requires_complement(root_verb[0]))

        return has_subject and has_verb

    def _ends_with_conjunction(self, doc) -> bool:
        \"\"\"Check if last token is conjunction\"\"\"
        if not doc:
            return False
        last_token = doc[-1]
        return last_token.pos_ in ["CCONJ", "SCONJ"]  # and, but, because, if, etc.

    def _has_dangling_preposition(self, doc) -> bool:
        \"\"\"Check if sentence ends with preposition\"\"\"
        if not doc:
            return False
        last_token = doc[-1]
        return last_token.pos_ == "ADP"  # in, on, at, with, etc.

    def _requires_complement(self, verb_token) -> bool:
        \"\"\"Check if verb requires direct object/complement\"\"\"
        # Transitive verbs require complement
        transitive_verbs = {"is", "was", "are", "were", "have", "has", "had", "think", "believe", "know"}
        return verb_token.lemma_ in transitive_verbs
```

---

## 8. Integration Points

### Upstream (Callers)

1. **Parent Audio Module (`app.audio`):**
   - Sends transcript + segments for analysis
   - Aggregates all analysis results into `AudioSignal`

### Downstream (Dependencies)

1. **spaCy (NLP):**
   - Dependency parsing for completeness classification
   - POS tagging for filler detection

2. **VADER (Sentiment):**
   - Text sentiment analysis

3. **TextBlob (Alternative Sentiment):**
   - Fallback sentiment analysis if VADER unavailable

---

## 9. Edge Cases to Handle

1. **Single-Word Transcript ("Yes."):**
   - Complete: `sentence_complete=True` (has punctuation, context implies completeness)

2. **Single-Word Transcript ("Yes"):**
   - Continuing: `speech_state="continuing"` (no punctuation, might add more)

3. **Transcript with Only Fillers ("Um, uh, so"):**
   - Incomplete: No actual content, `filler_rate=1.0`

4. **Transcript Ends Mid-Sentence ("The answer is"):**
   - Incomplete: Missing complement

5. **Extremely Long Transcript (>1000 words):**
   - Chunk into sentences, analyze last sentence only for completeness

6. **Non-English Transcript:**
   - Return low-confidence analysis or error (depends on spaCy model availability)

7. **Transcript with Technical Jargon ("I used DFS to traverse the graph"):**
   - spaCy may misparse, return lower confidence

8. **Candidate Pauses Mid-Word ("The ans... answer is"):**
   - Filler detector should ignore disfluencies (transcription engine handles this)

---

## 10. Example Usage

### Completeness Classification

```python
from app.audio.analysis import CompletenessClassifier

classifier = CompletenessClassifier()

# Complete sentence
result = classifier.evaluate("The answer is dynamic programming.")
print(result.speech_state)  # "complete"
print(result.confidence)    # 0.9

# Incomplete sentence
result = classifier.evaluate("The answer is")
print(result.speech_state)  # "incomplete"
print(result.incomplete_reason)  # "missing_complement"
```

### Filler Detection

```python
from app.audio.analysis import FillerDetector

detector = FillerDetector(context_aware=True)

result = detector.detect("Um, I think the answer is, like, dynamic programming.")

print(result.filler_word_count)  # 3 (um, I think, like)
print(result.filler_rate)        # 0.273 (3 out of 11 words)
```

### Speech Rate Analysis

```python
from app.audio.analysis import SpeechRateAnalyzer

analyzer = SpeechRateAnalyzer()

result = analyzer.analyze(
    transcript="The quick brown fox jumps over the lazy dog",
    segments=segments_with_timestamps
)

print(result.speech_rate_wpm)  # 180 WPM
print(result.long_pause_count)  # 2
```

### Sentiment Analysis

```python
from app.audio.analysis import SentimentAnalyzer

analyzer = SentimentAnalyzer()

result = analyzer.analyze("I really don't know how to solve this problem.")

print(result.sentiment_score)     # -0.35 (slightly negative)
print(result.hesitation_detected)  # True (contains "don't know")
```

---

## 11. Configuration

### Environment Variables

```bash
# Completeness classifier
COMPLETENESS_SPACY_MODEL=en_core_web_sm  # or en_core_web_md for better accuracy

# Filler detection
FILLER_WORDS=um,uh,like,so,basically,actually,you know,I think,I mean
FILLER_CONTEXT_AWARE=true

# Speech rate thresholds
SPEECH_RATE_SLOW_THRESHOLD_WPM=80
SPEECH_RATE_FAST_THRESHOLD_WPM=200
SPEECH_RATE_LONG_PAUSE_THRESHOLD_MS=1000

# Sentiment analysis
SENTIMENT_ENGINE=vader  # vader | textblob
SENTIMENT_HESITATION_THRESHOLD=0.15  # Filler rate threshold for hesitation
```

---

## 12. Future Enhancements

1. **Multi-Language Support:**
   - Load spaCy models for Spanish, French, German
   - Language-specific filler words

2. **Custom Filler Dictionaries:**
   - Allow tenants to define custom fillers (e.g., "right?", "okay?")

3. **Acoustic Feature Analysis:**
   - Extract pitch, volume, speech rate from raw audio (requires audio signal processing)
   - More accurate sentiment/hesitation detection

4. **Code-Switching Detection:**
   - Detect when candidate switches between languages mid-sentence
   - Common in multilingual interviews

5. **Discourse Marker Analysis:**
   - Detect transition markers ("first", "second", "finally")
   - Indicates structured thinking

6. **Disfluency Detection:**
   - Detect word repetitions ("the the answer")
   - Detect self-corrections ("I mean... rather...")

---

**End of Audio Analysis Module Requirements**
