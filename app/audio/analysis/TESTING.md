# Audio Analysis Module Testing Guide

## Testing Philosophy

Analysis testing focuses on **accuracy** and **determinism**. Tests use:

- **Curated test corpus** (100+ labeled sentences for completeness classifier)
- **Edge case transcripts** (single word, all fillers, technical jargon)
- **Regression tests** (same input always produces same output)

Most critical: **Completeness classifier must achieve >85% accuracy** on held-out test set.

---

## Test Structure

```
tests/
├── unit/
│   └── audio/
│       └── analysis/
│           ├── test_completeness_classifier.py
│           ├── test_filler_detector.py
│           ├── test_speech_rate_analyzer.py
│           ├── test_sentiment_analyzer.py
│           └── test_edge_cases.py
├── integration/
│   └── audio/
│       └── analysis/
│           ├── test_analysis_pipeline.py
│           └── test_spacy_dependency_parsing.py
└── fixtures/
    └── audio/
        ├── completeness_test_corpus.json  # 100+ labeled examples
        └── filler_test_corpus.json
```

---

## 1. Unit Tests

### Completeness Classifier Tests

```python
# tests/unit/audio/analysis/test_completeness_classifier.py

import pytest
from app.audio.analysis.completeness_classifier import CompletenessClassifier

@pytest.fixture
def classifier():
    return CompletenessClassifier()

def test_complete_sentence_with_period(classifier):
    \"\"\"Complete sentence ending with period\"\"\"
    result = classifier.evaluate("The answer is dynamic programming.")

    assert result.speech_state == "complete"
    assert result.sentence_complete is True
    assert result.confidence > 0.8

def test_complete_sentence_with_question_mark(classifier):
    \"\"\"Complete sentence ending with question mark\"\"\"
    result = classifier.evaluate("Is this the right answer?")

    assert result.speech_state == "complete"
    assert result.sentence_complete is True

def test_incomplete_sentence_ends_with_conjunction(classifier):
    \"\"\"Incomplete sentence ending with 'because'\"\"\"
    result = classifier.evaluate("The answer is correct because")

    assert result.speech_state == "incomplete"
    assert result.sentence_complete is False
    assert result.incomplete_reason == "ends_with_conjunction"

def test_incomplete_sentence_missing_complement(classifier):
    \"\"\"Incomplete sentence missing complement\"\"\"
    result = classifier.evaluate("I think the answer is")

    assert result.speech_state == "incomplete"
    assert result.sentence_complete is False
    assert result.incomplete_reason == "missing_complement"

def test_complete_one_word_with_punctuation(classifier):
    \"\"\"Single word with punctuation is complete\"\"\"
    result = classifier.evaluate("Yes.")

    assert result.speech_state == "complete"
    assert result.confidence > 0.7

def test_continuing_one_word_no_punctuation(classifier):
    \"\"\"Single word without punctuation is continuing\"\"\"
    result = classifier.evaluate("Yes")

    assert result.speech_state == "continuing"
    assert result.confidence < 0.7

def test_incomplete_dangling_preposition(classifier):
    \"\"\"Sentence ending with preposition is incomplete\"\"\"
    result = classifier.evaluate("The answer depends on")

    assert result.speech_state == "incomplete"
    assert result.incomplete_reason == "dangling_preposition"

def test_empty_transcript(classifier):
    \"\"\"Empty transcript is incomplete\"\"\"
    result = classifier.evaluate("")

    assert result.speech_state == "incomplete"
    assert result.incomplete_reason == "empty_transcript"

def test_transcript_with_only_fillers(classifier):
    \"\"\"Transcript with only fillers is incomplete\"\"\"
    result = classifier.evaluate("Um uh so")

    assert result.speech_state == "incomplete"

def test_technical_jargon_sentence(classifier):
    \"\"\"Sentence with technical terms parsed correctly\"\"\"
    result = classifier.evaluate("I used DFS to traverse the graph.")

    assert result.speech_state == "complete"

def test_ambiguous_sentence_lower_confidence(classifier):
    \"\"\"Ambiguous case has lower confidence\"\"\"
    result = classifier.evaluate("The algorithm works well")  # No punctuation

    # Structurally complete but no punctuation
    assert 0.5 < result.confidence < 0.8

def test_multiple_sentences_analyzes_last_only(classifier):
    \"\"\"Multiple sentences: analyze last sentence\"\"\"
    result = classifier.evaluate("First sentence. Second sentence")

    # Last sentence is incomplete (no punctuation)
    assert result.speech_state == "continuing"

def test_determinism_same_input_same_output(classifier):
    \"\"\"Same input produces same output\"\"\"
    transcript = "The answer is dynamic programming."

    result1 = classifier.evaluate(transcript)
    result2 = classifier.evaluate(transcript)

    assert result1.speech_state == result2.speech_state
    assert result1.confidence == result2.confidence
```

### Completeness Classifier Accuracy Test

```python
# tests/unit/audio/analysis/test_completeness_accuracy.py

import pytest
import json
from pathlib import Path

@pytest.fixture
def test_corpus():
    \"\"\"Load labeled test corpus\"\"\"
    corpus_path = Path(__file__).parent.parent.parent / "fixtures" / "audio" / "completeness_test_corpus.json"
    with open(corpus_path) as f:
        return json.load(f)

def test_classifier_accuracy_on_test_corpus(test_corpus):
    \"\"\"Classifier achieves >85% accuracy on test corpus\"\"\"
    classifier = CompletenessClassifier()

    correct = 0
    total = len(test_corpus)

    for example in test_corpus:
        transcript = example["transcript"]
        expected_state = example["expected_state"]  # "complete" or "incomplete"

        result = classifier.evaluate(transcript)

        if result.speech_state == expected_state:
            correct += 1

    accuracy = correct / total

    assert accuracy > 0.85, f"Classifier accuracy {accuracy:.2%} below 85% threshold"

def test_classifier_confusion_matrix(test_corpus):
    \"\"\"Generate confusion matrix for analysis\"\"\"
    classifier = CompletenessClassifier()

    confusion = {
        "complete_as_complete": 0,
        "complete_as_incomplete": 0,
        "incomplete_as_complete": 0,
        "incomplete_as_incomplete": 0
    }

    for example in test_corpus:
        result = classifier.evaluate(example["transcript"])
        expected = example["expected_state"]

        if expected == "complete" and result.speech_state == "complete":
            confusion["complete_as_complete"] += 1
        elif expected == "complete" and result.speech_state != "complete":
            confusion["complete_as_incomplete"] += 1
        elif expected == "incomplete" and result.speech_state == "complete":
            confusion["incomplete_as_complete"] += 1
        elif expected == "incomplete" and result.speech_state != "complete":
            confusion["incomplete_as_incomplete"] += 1

    # Print for debugging
    print(json.dumps(confusion, indent=2))

    # Assert precision/recall thresholds
    precision = confusion["complete_as_complete"] / (confusion["complete_as_complete"] + confusion["incomplete_as_complete"])
    recall = confusion["complete_as_complete"] / (confusion["complete_as_complete"] + confusion["complete_as_incomplete"])

    assert precision > 0.80
    assert recall > 0.80
```

### Filler Detection Tests

```python
# tests/unit/audio/analysis/test_filler_detector.py

from app.audio.analysis.filler_detector import FillerDetector

def test_common_fillers_detected():
    \"\"\"Common filler words detected\"\"\"
    detector = FillerDetector()

    result = detector.detect("Um, I think, uh, the answer is, like, dynamic programming.")

    assert result.filler_word_count >= 3  # um, uh, like
    assert "um" in [f.word for f in result.filler_positions]
    assert "uh" in [f.word for f in result.filler_positions]

def test_like_as_verb_not_filler():
    \"\"\"'Like' as verb not counted as filler\"\"\"
    detector = FillerDetector(context_aware=True)

    result = detector.detect("I like Python programming.")

    assert result.filler_word_count == 0

def test_like_as_filler_detected():
    \"\"\"'Like' as filler is detected\"\"\"
    detector = FillerDetector(context_aware=True)

    result = detector.detect("The answer is, like, dynamic programming.")

    assert result.filler_word_count >= 1
    assert any(f.word == "like" for f in result.filler_positions)

def test_filler_rate_calculation():
    \"\"\"Filler rate calculated correctly\"\"\"
    detector = FillerDetector()

    transcript = "Um so uh basically the answer is bubble sort"  # 3 fillers, 8 words

    result = detector.detect(transcript)

    # 3 fillers out of 8 total words
    assert result.filler_rate == pytest.approx(0.375, abs=0.01)

def test_consecutive_fillers_counted_separately():
    \"\"\"Consecutive fillers each counted\"\"\"
    detector = FillerDetector()

    result = detector.detect("Um uh like")

    assert result.filler_word_count == 3

def test_no_fillers_clean_transcript():
    \"\"\"Clean transcript with no fillers\"\"\"
    detector = FillerDetector()

    result = detector.detect("The algorithm uses dynamic programming.")

    assert result.filler_word_count == 0
    assert result.filler_rate == 0.0

def test_filler_positions_include_timestamps():
    \"\"\"Filler positions include word index\"\"\"
    detector = FillerDetector()

    result = detector.detect("The um answer is uh correct")

    fillers = result.filler_positions
    assert len(fillers) == 2
    assert fillers[0].word == "um"
    assert fillers[0].position == 1  # Index of "um"
    assert fillers[1].word == "uh"
    assert fillers[1].position == 4  # Index of "uh"

def test_custom_filler_words():
    \"\"\"Custom filler words configurable\"\"\"
    detector = FillerDetector(filler_words=["right", "okay", "you know"])

    result = detector.detect("The answer is correct, right? Okay.")

    assert result.filler_word_count >= 2
```

### Speech Rate Tests

```python
# tests/unit/audio/analysis/test_speech_rate_analyzer.py

from app.audio.analysis.speech_rate_analyzer import SpeechRateAnalyzer

def test_words_per_minute_calculation():
    \"\"\"WPM calculated from word count and duration\"\"\"
    analyzer = SpeechRateAnalyzer()

    transcript = "one two three four five six seven eight nine"  # 9 words
    duration_ms = 3000  # 3 seconds

    result = analyzer.analyze(transcript, duration_ms)

    # 9 words in 3s = 180 WPM
    assert result.speech_rate_wpm == pytest.approx(180, abs=1)

def test_long_pause_detection():
    \"\"\"Long pauses detected from segments\"\"\"
    analyzer = SpeechRateAnalyzer()

    segments = [
        TranscriptSegment(text="First", start_ms=0, end_ms=500, confidence=0.9),
        # 2 second gap (long pause)
        TranscriptSegment(text="Second", start_ms=2500, end_ms=3000, confidence=0.9)
    ]

    result = analyzer.analyze_segments(segments)

    assert result.long_pause_count == 1
    assert result.longest_pause_ms == 2000

def test_speech_rate_excludes_pauses():
    \"\"\"Speech rate excludes pause time\"\"\"
    analyzer = SpeechRateAnalyzer()

    # 10 words, 5s of actual speech, 10s total (5s pauses)
    segments = [
        TranscriptSegment(text="one two three", start_ms=0, end_ms=2000, confidence=0.9),
        # 5s pause
        TranscriptSegment(text="four five six seven", start_ms=7000, end_ms=10000, confidence=0.9)
    ]

    result = analyzer.analyze_segments(segments)

    # 7 words over 5s actual speech = 84 WPM
    assert result.speech_duration_ms == 5000
    assert result.total_duration_ms == 10000
    assert result.speech_rate_wpm == pytest.approx(84, abs=5)

def test_empty_transcript_zero_wpm():
    \"\"\"Empty transcript returns 0 WPM\"\"\"
    analyzer = SpeechRateAnalyzer()

    result = analyzer.analyze("", duration_ms=1000)

    assert result.speech_rate_wpm == 0.0
    assert result.total_words == 0

def test_abnormally_slow_speech_flagged():
    \"\"\"Slow speech (<80 WPM) flagged\"\"\"
    analyzer = SpeechRateAnalyzer(slow_threshold_wpm=80)

    # 5 words in 5s = 60 WPM
    result = analyzer.analyze("one two three four five", duration_ms=5000)

    assert result.speech_rate_wpm < 80
    assert result.is_abnormally_slow is True

def test_abnormally_fast_speech_flagged():
    \"\"\"Fast speech (>200 WPM) flagged\"\"\"
    analyzer = SpeechRateAnalyzer(fast_threshold_wpm=200)

    # 30 words in 6s = 300 WPM
    transcript = " ".join(["word"] * 30)
    result = analyzer.analyze(transcript, duration_ms=6000)

    assert result.speech_rate_wpm > 200
    assert result.is_abnormally_fast is True
```

### Sentiment Analysis Tests

```python
# tests/unit/audio/analysis/test_sentiment_analyzer.py

from app.audio.analysis.sentiment_analyzer import SentimentAnalyzer

def test_positive_sentiment():
    \"\"\"Positive transcript has positive sentiment\"\"\"
    analyzer = SentimentAnalyzer()

    result = analyzer.analyze("I'm confident this is the correct solution.")

    assert result.sentiment_score > 0.3
    assert result.confidence_level in ["medium", "high"]

def test_negative_sentiment():
    \"\"\"Negative transcript has negative sentiment\"\"\"
    analyzer = SentimentAnalyzer()

    result = analyzer.analyze("I really don't know how to solve this problem.")

    assert result.sentiment_score < 0.0
    assert result.hesitation_detected is True

def test_neutral_sentiment():
    \"\"\"Neutral transcript has neutral sentiment\"\"\"
    analyzer = SentimentAnalyzer()

    result = analyzer.analyze("The algorithm uses dynamic programming.")

    assert -0.2 < result.sentiment_score < 0.2

def test_hesitation_detected_from_fillers():
    \"\"\"Hesitation detected from excessive fillers\"\"\"
    analyzer = SentimentAnalyzer()

    result = analyzer.analyze(
        transcript="Um, I think, uh, maybe, like, I don't know",
        filler_rate=0.5  # 50% fillers
    )

    assert result.hesitation_detected is True

def test_frustration_detected():
    \"\"\"Frustration detected from negative sentiment + context\"\"\"
    analyzer = SentimentAnalyzer()

    result = analyzer.analyze("This problem is really difficult and I can't figure it out.")

    assert result.sentiment_score < -0.3
    assert result.frustration_detected is True

def test_sentiment_score_normalized():
    \"\"\"Sentiment score always between -1.0 and +1.0\"\"\"
    analyzer = SentimentAnalyzer()

    result = analyzer.analyze("Some random transcript")

    assert -1.0 <= result.sentiment_score <= 1.0
```

### Edge Case Tests

```python
# tests/unit/audio/analysis/test_edge_cases.py

def test_single_word_yes():
    \"\"\"Single word 'Yes' is complete\"\"\"
    classifier = CompletenessClassifier()
    result = classifier.evaluate("Yes.")
    assert result.speech_state == "complete"

def test_single_word_no_punctuation():
    \"\"\"Single word without punctuation is continuing\"\"\"
    classifier = CompletenessClassifier()
    result = classifier.evaluate("Yes")
    assert result.speech_state == "continuing"

def test_all_fillers_transcript():
    \"\"\"Transcript with only fillers\"\"\"
    detector = FillerDetector()
    result = detector.detect("Um uh like so basically")
    assert result.filler_rate == 1.0

def test_extremely_long_transcript():
    \"\"\"Very long transcript (>1000 words)\"\"\"
    classifier = CompletenessClassifier()
    long_transcript = " ".join(["word"] * 1000) + "."
    result = classifier.evaluate(long_transcript)
    # Should still complete in <500ms
    assert result is not None

def test_non_english_transcript():
    \"\"\"Non-English transcript (if spaCy model unavailable)\"\"\"
    classifier = CompletenessClassifier()
    result = classifier.evaluate("La respuesta es programación dinámica.")
    # Should return lower confidence or error
    assert result.confidence < 0.5 or result.speech_state == "incomplete"

def test_transcript_with_code_snippets():
    \"\"\"Transcript containing code snippets\"\"\"
    classifier = CompletenessClassifier()
    result = classifier.evaluate("I would use for i in range(n) to iterate.")
    # Code may confuse parser, but should not crash
    assert result is not None
```

---

## 2. Integration Tests

### Analysis Pipeline Tests

```python
# tests/integration/audio/analysis/test_analysis_pipeline.py

def test_full_analysis_pipeline():
    \"\"\"Full pipeline: completeness + fillers + speech rate + sentiment\"\"\"
    from app.audio.analysis import analyze_transcript

    transcript = "Um, I think the answer is dynamic programming."
    segments = [
        TranscriptSegment(text="Um,", start_ms=0, end_ms=200, confidence=0.9),
        TranscriptSegment(text="I", start_ms=200, end_ms=300, confidence=0.95),
        # ... more segments
    ]

    result = analyze_transcript(transcript, segments)

    assert result.completeness.speech_state == "complete"
    assert result.filler_detection.filler_word_count >= 1
    assert result.speech_rate.speech_rate_wpm > 0
    assert -1.0 <= result.sentiment.sentiment_score <= 1.0

def test_analysis_latency_under_500ms():
    \"\"\"Full analysis completes within 500ms\"\"\"
    import time
    from app.audio.analysis import analyze_transcript

    transcript = "The answer is dynamic programming and it solves the problem efficiently."
    segments = generate_mock_segments(transcript)

    start = time.time()
    result = analyze_transcript(transcript, segments)
    latency = time.time() - start

    assert latency < 0.5, f"Analysis took {latency}s, exceeds 500ms SLA"
```

### spaCy Dependency Parsing Tests

```python
# tests/integration/audio/analysis/test_spacy_dependency_parsing.py

import spacy

def test_spacy_loaded_correctly():
    \"\"\"spaCy model loaded correctly\"\"\"
    nlp = spacy.load("en_core_web_sm")
    assert nlp is not None

def test_spacy_dependency_parsing():
    \"\"\"spaCy parses dependencies correctly\"\"\"
    nlp = spacy.load("en_core_web_sm")

    doc = nlp("The answer is dynamic programming.")

    # Check for subject
    subjects = [token for token in doc if token.dep_ == "nsubj"]
    assert len(subjects) > 0

    # Check for verb
    verbs = [token for token in doc if token.pos_ == "VERB"]
    assert len(verbs) > 0

def test_spacy_handles_technical_jargon():
    \"\"\"spaCy handles technical terms\"\"\"
    nlp = spacy.load("en_core_web_sm")

    doc = nlp("I used DFS to traverse the graph.")

    # Should still parse correctly despite technical terms
    verbs = [token for token in doc if token.pos_ == "VERB"]
    assert len(verbs) > 0
```

---

## Test Coverage Requirements

- **Unit Tests:** >90% code coverage
- **Integration Tests:** Full pipeline + spaCy integration
- **Accuracy Tests:** Completeness classifier >85% accuracy on test corpus

---

## Running Tests

```bash
# Unit tests
pytest tests/unit/audio/analysis/ -v

# Accuracy test (requires test corpus)
pytest tests/unit/audio/analysis/test_completeness_accuracy.py -v

# Integration tests
pytest tests/integration/audio/analysis/ -v

# Edge cases
pytest tests/unit/audio/analysis/test_edge_cases.py -v

# Coverage
pytest tests/audio/analysis/ --cov=app/audio/analysis --cov-report=html
```

---

## Critical Tests (Must Pass)

- [ ] Completeness classifier >85% accuracy on test corpus
- [ ] Filler detector distinguishes "like" as verb vs filler
- [ ] Speech rate excludes pause time from WPM calculation
- [ ] Analysis pipeline completes within 500ms p95
- [ ] Sentiment score always between -1.0 and +1.0
- [ ] Same input produces same output (determinism)
- [ ] Single-word transcripts handled correctly
- [ ] Empty transcripts return valid results

---

**End of Audio Analysis Module Testing Guide**
