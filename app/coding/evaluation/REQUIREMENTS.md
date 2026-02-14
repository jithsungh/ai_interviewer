# Coding Evaluation Layer - Test Case Scoring & Aggregation

## 1. Purpose

**Why this submodule exists:**

The Coding Evaluation layer provides **deterministic scoring logic** for code submissions. It:

- Compares actual output vs expected output
- Calculates weighted scores across test cases
- Determines pass/fail for each test case
- Generates feedback messages
- Supports hidden vs visible test cases

**Critical responsibility:** This is the **scoring engine** for code execution. It must be deterministic, fair, and mathematically correct. Same inputs ALWAYS produce same outputs.

**Architectural philosophy:**

> **Scoring must be deterministic.**
> **No randomness. No side effects.**
> **Pure function: inputs → score.**

---

## 2. Owned Tables / Entities

**None.** Evaluation layer is stateless. It consumes test case results and produces scores.

---

## 3. Input Contracts

### TestCaseEvaluationRequest

```python
from pydantic import BaseModel
from typing import List

class TestCaseComparison(BaseModel):
    test_case_id: int
    test_case_name: str
    expected_output: str
    actual_output: str
    weight: int
    visible: bool

class TestCaseEvaluationRequest(BaseModel):
    submission_id: int
    test_cases: List[TestCaseComparison]
```

---

## 4. Output Contracts

### TestCaseEvaluationResult

```python
from typing import Literal

class TestCaseResult(BaseModel):
    test_case_id: int
    passed: bool
    feedback: Literal["Passed", "Wrong Answer"]
    match_details: Optional[str] = None  # Only for visible tests

class EvaluationResult(BaseModel):
    submission_id: int
    score: float  # 0-100
    total_weight: int
    earned_weight: int
    test_results: List[TestCaseResult]
```

---

## 5. Acceptance Criteria

### Output Comparison Algorithm

**Default comparison:**

```python
def compare_outputs(expected: str, actual: str) -> bool:
    """
    Compare expected vs actual output.

    Rules:
    1. Strip leading/trailing whitespace
    2. Strip trailing whitespace from each line
    3. Exact string match

    Returns:
        True if outputs match, False otherwise
    """
    expected_normalized = normalize_output(expected)
    actual_normalized = normalize_output(actual)
    return expected_normalized == actual_normalized

def normalize_output(output: str) -> str:
    """
    Normalize output for comparison.

    Process:
    1. Split into lines
    2. Strip trailing whitespace from each line
    3. Remove empty trailing lines
    4. Join with '\n'
    """
    lines = output.split('\n')
    lines = [line.rstrip() for line in lines]

    # Remove trailing empty lines
    while lines and not lines[-1]:
        lines.pop()

    return '\n'.join(lines)
```

**Example:**

```python
expected = "Hello World  \n\n"
actual = "Hello World\n"

# After normalization:
# expected = "Hello World"
# actual = "Hello World"
# Match: True
```

---

### Weighted Score Calculation

**Formula:**

```
score = (Σ test_case.weight × passed) / (Σ test_case.weight) × 100
```

**Implementation:**

```python
def calculate_score(test_results: List[TestCaseResult], test_cases: List[TestCase]) -> float:
    """
    Calculate weighted score.

    Args:
        test_results: List of test case results (passed or failed)
        test_cases: List of test cases with weights

    Returns:
        Score (0-100)
    """
    total_weight = sum(tc.weight for tc in test_cases)

    if total_weight == 0:
        # Edge case: all test cases have weight 0
        return 0.0

    earned_weight = sum(
        tc.weight
        for tc, result in zip(test_cases, test_results)
        if result.passed
    )

    score = (earned_weight / total_weight) * 100
    return round(score, 2)  # Round to 2 decimal places
```

**Example:**

```python
# Test cases:
# Test 1: weight=1, passed=True  → 1 point
# Test 2: weight=2, passed=True  → 2 points
# Test 3: weight=1, passed=False → 0 points

total_weight = 1 + 2 + 1 = 4
earned_weight = 1 + 2 + 0 = 3
score = (3 / 4) * 100 = 75.0
```

---

### Feedback Generation

**For passed test cases:**

- Feedback: `"Passed"`

**For failed test cases (visible):**

- Feedback: `"Wrong Answer"`
- Match details: Show diff or indication of mismatch

**For failed test cases (hidden):**

- Feedback: `"Wrong Answer"`
- Match details: None (don't reveal expected output)

**Example:**

```python
def generate_feedback(
    passed: bool,
    visible: bool,
    expected: str,
    actual: str
) -> tuple[str, Optional[str]]:
    """
    Generate feedback message.

    Returns:
        (feedback, match_details)
    """
    if passed:
        return ("Passed", None)

    if not visible:
        # Hidden test case: don't reveal details
        return ("Wrong Answer", None)

    # Visible test case: show diff
    if len(actual) == 0:
        match_details = "No output produced"
    elif len(expected) != len(actual):
        match_details = f"Output length mismatch: expected {len(expected)} chars, got {len(actual)} chars"
    else:
        match_details = "Output does not match expected"

    return ("Wrong Answer", match_details)
```

---

### Hidden Test Case Protection

**Rules:**

1. Hidden test cases MUST NOT expose `expected_output` in API responses
2. Hidden test case feedback limited to: `"Passed"` or `"Wrong Answer"`
3. No diff, no match details, no hints

**Enforcement:**

```python
def sanitize_result_for_api(
    result: TestCaseResult,
    test_case: TestCase
) -> TestCaseResultDTO:
    """
    Sanitize test case result for API response.

    If test case is hidden:
    - Don't include expected_output
    - Don't include actual_output (prevents inference)
    - Don't include detailed match_details
    """
    if not test_case.visible:
        return TestCaseResultDTO(
            test_case_id=result.test_case_id,
            test_case_name=test_case.test_case_name,
            passed=result.passed,
            visible=False,
            actual_output=None,  # Hidden
            expected_output=None,  # Hidden
            runtime_ms=result.runtime_ms,
            memory_kb=result.memory_kb,
            feedback="Passed" if result.passed else "Wrong Answer"
        )
    else:
        return TestCaseResultDTO(
            test_case_id=result.test_case_id,
            test_case_name=test_case.test_case_name,
            passed=result.passed,
            visible=True,
            actual_output=result.actual_output,
            expected_output=test_case.expected_output,
            runtime_ms=result.runtime_ms,
            memory_kb=result.memory_kb,
            feedback=result.feedback
        )
```

---

## 6. Invariants & Constraints

### Must Hold

1. **Determinism:** Same inputs → same score (always)
2. **Score Range:** Score always in range [0, 100]
3. **Weight Validation:** Total weight > 0 (enforced at problem creation)
4. **Hidden Protection:** Hidden test expected_output NEVER exposed
5. **Comparison Consistency:** Same output comparison algorithm for all languages

### Forbidden

- MUST NOT use randomness in scoring
- MUST NOT expose hidden test case expected_output
- MUST NOT modify score after calculation
- MUST NOT use floating point comparison without tolerance (future enhancement)
- MUST NOT skip test cases in score calculation

---

## 7. Dependent Modules

### Upstream (Callers)

1. **Execution Module:** Calls evaluation after test execution

### Downstream (Dependencies)

None. Evaluation is pure logic with no external dependencies.

---

## 8. Edge Cases to Handle

### 1. Empty Output

**Scenario:**

- Expected: `""`
- Actual: `""`

**Result:** Match = True

---

### 2. Trailing Whitespace

**Scenario:**

- Expected: `"Hello World  \n"`
- Actual: `"Hello World\n"`

**Result:** After normalization, both = `"Hello World"` → Match = True

---

### 3. Trailing Newlines

**Scenario:**

- Expected: `"42\n\n\n"`
- Actual: `"42\n"`

**Result:** After normalization, both = `"42"` → Match = True

---

### 4. Leading Whitespace

**Scenario:**

- Expected: `"  42"`
- Actual: `"42"`

**Result:** Match = False (leading whitespace significant)

**Rationale:** Leading whitespace may be intentional (e.g., formatted output).

---

### 5. Case Sensitivity

**Scenario:**

- Expected: `"Hello"`
- Actual: `"hello"`

**Result:** Match = False (case-sensitive by default)

**Future:** Allow case-insensitive comparison via problem settings.

---

### 6. Floating Point Output

**Scenario:**

- Expected: `"3.14159"`
- Actual: `"3.14159"`

**Result:** Exact string match required

**Future:** Support epsilon tolerance (e.g., `abs(expected - actual) < 0.0001`).

---

### 7. Multi-Line Output

**Scenario:**

- Expected:
  ```
  Line 1
  Line 2
  Line 3
  ```
- Actual:
  ```
  Line 1
  Line 2
  Line 3
  ```

**Result:** Match = True

---

### 8. Zero-Weight Test Cases

**Scenario:**

- Test 1: weight=0, passed=True
- Test 2: weight=1, passed=True

**Result:**

- Total weight = 0 + 1 = 1
- Earned weight = 0 + 1 = 1
- Score = (1 / 1) × 100 = 100.0

**Rationale:** Zero-weight tests used for examples, not counted in score.

---

### 9. All Tests Failed

**Scenario:**

- All test cases: passed=False

**Result:**

- Earned weight = 0
- Score = 0.0

---

### 10. All Tests Passed

**Scenario:**

- All test cases: passed=True

**Result:**

- Earned weight = Total weight
- Score = 100.0

---

## 9. Comparison Algorithm Variations (Future)

### 1. Floating Point Tolerance

**Use case:** Problem requires floating point output (e.g., `3.14159`).

**Algorithm:**

```python
def compare_floats(expected: str, actual: str, epsilon: float = 1e-6) -> bool:
    try:
        expected_float = float(expected.strip())
        actual_float = float(actual.strip())
        return abs(expected_float - actual_float) < epsilon
    except ValueError:
        # Not a float, fall back to string comparison
        return expected.strip() == actual.strip()
```

---

### 2. Case-Insensitive Comparison

**Use case:** Problem doesn't care about case (e.g., "YES" vs "yes").

**Algorithm:**

```python
def compare_case_insensitive(expected: str, actual: str) -> bool:
    return normalize_output(expected).lower() == normalize_output(actual).lower()
```

---

### 3. Token-Based Comparison

**Use case:** Order of tokens doesn't matter (e.g., unordered lists).

**Algorithm:**

```python
def compare_tokens(expected: str, actual: str) -> bool:
    expected_tokens = sorted(expected.split())
    actual_tokens = sorted(actual.split())
    return expected_tokens == actual_tokens
```

---

### 4. Custom Judge

**Use case:** Complex output validation (e.g., multiple valid solutions).

**Algorithm:**

```python
def custom_judge(expected: str, actual: str, judge_code: str) -> bool:
    """
    Execute custom judge code.

    Judge receives:
    - expected: expected output
    - actual: candidate output

    Judge returns:
    - True if valid
    - False if invalid
    """
    # Execute judge_code in sandbox
    # Return judge verdict
```

---

## 10. Configuration

### Environment Variables

```bash
# Comparison
ENABLE_FLOATING_POINT_TOLERANCE=false
FLOATING_POINT_EPSILON=1e-6

ENABLE_CASE_INSENSITIVE=false

# Output
MAX_DIFF_LENGTH=1000  # Max chars to show in diff
```

---

## 11. Testing Requirements

**Must test:**

### Comparison Tests

1. **Exact Match:** Identical strings → True
2. **Trailing Whitespace:** Normalized strings → True
3. **Trailing Newlines:** Normalized strings → True
4. **Leading Whitespace:** Different → False
5. **Case Difference:** "Hello" vs "hello" → False
6. **Empty Output:** Both empty → True
7. **Multi-Line Match:** Multi-line strings → True

### Scoring Tests

1. **All Passed:** Score = 100.0
2. **All Failed:** Score = 0.0
3. **Partial Credit:** 2 of 3 passed, equal weights → 66.67
4. **Weighted Scoring:** Different weights → correct calculation
5. **Zero-Weight Tests:** Excluded from score
6. **Single Test:** Passed → 100.0, Failed → 0.0

### Edge Case Tests

1. **Unicode Output:** Unicode characters compared correctly
2. **Binary Output:** Invalid UTF-8 handled gracefully
3. **Large Output:** 1MB output compared efficiently
4. **Empty Expected:** No output expected, candidate prints → False

---

## 12. Future Enhancements

1. **Floating Point Tolerance:**
   - Allow epsilon-based comparison
   - Configurable per problem

2. **Custom Comparators:**
   - Upload custom judge code
   - Execute in sandbox

3. **Partial Matching:**
   - Award partial credit for close outputs

4. **Token-Based Comparison:**
   - Unordered output validation

5. **Regex Matching:**
   - Pattern-based output validation

6. **Performance Metrics:**
   - Factor execution time into score
   - Percentile rankings

---

**End of Coding Evaluation Layer Requirements**

---

## Architectural Intent

The evaluation layer is:

- A **pure function** (no side effects)
- **Deterministic** (same inputs → same outputs)
- **Mathematically correct** (scoring formula enforced)

It transforms test case results into scores. Nothing more.

**Pure logic. No surprise.**
