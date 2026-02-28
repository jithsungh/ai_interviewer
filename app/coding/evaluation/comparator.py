"""
Output Comparator — Deterministic output comparison for test cases

Implements the exact comparison algorithm specified in
evaluation/REQUIREMENTS.md §5.

Pure functions with zero side effects.

Comparison rules:
1. Split into lines
2. Strip trailing whitespace from each line
3. Remove trailing empty lines
4. Join with newline
5. Exact string match

References:
- evaluation/REQUIREMENTS.md §5 (Output Comparison Algorithm)
"""


def normalize_output(output: str) -> str:
    """
    Normalize output for comparison.

    Process:
        1. Split into lines
        2. Strip trailing whitespace from each line
        3. Remove trailing empty lines
        4. Join with newline

    Args:
        output: Raw output string.

    Returns:
        Normalized output string.
    """
    lines = output.split("\n")
    lines = [line.rstrip() for line in lines]

    # Remove trailing empty lines
    while lines and not lines[-1]:
        lines.pop()

    return "\n".join(lines)


def compare_outputs(expected: str, actual: str) -> bool:
    """
    Compare expected vs actual output after normalization.

    Applies normalization before comparison:
    - Trailing whitespace stripped per line
    - Trailing empty lines removed
    - Exact string match after normalization

    Args:
        expected: Expected output from the test case definition.
        actual: Actual output from program execution.

    Returns:
        ``True`` if outputs match after normalization, ``False`` otherwise.
    """
    expected_normalized = normalize_output(expected)
    actual_normalized = normalize_output(actual)
    return expected_normalized == actual_normalized
