"""
Test runner script for config module

Run this script to execute all config tests and see results.
"""

import subprocess
import sys


def run_tests():
    """Run all config tests with pytest"""
    
    print("=" * 50)
    print("AI Interviewer - Config Module Tests")
    print("=" * 50)
    print()
    
    # Test commands
    commands = [
        {
            "name": "All Config Tests",
            "cmd": ["python3", "-m", "pytest", "tests/unit/config/", "tests/integration/config/", "-v"]
        },
        {
            "name": "Unit Tests Only",
            "cmd": ["python3", "-m", "pytest", "tests/unit/config/", "-v", "--tb=short"]
        },
        {
            "name": "Integration Tests Only",
            "cmd": ["python3", "-m", "pytest", "tests/integration/config/", "-v", "--tb=short"]
        },
        {
            "name": "Test Summary",
            "cmd": ["python3", "-m", "pytest", "tests/unit/config/", "tests/integration/config/", "-v", "--tb=no", "-q"]
        }
    ]
    
    results = []
    
    for test_group in commands:
        print(f"\n{'=' * 50}")
        print(f"Running: {test_group['name']}")
        print('=' * 50)
        
        try:
            result = subprocess.run(
                test_group["cmd"],
                cwd=".",
                capture_output=False,
                text=True
            )
            results.append((test_group['name'], result.returncode == 0))
        except Exception as e:
            print(f"Error running {test_group['name']}: {e}")
            results.append((test_group['name'], False))
    
    # Print summary
    print("\n" + "=" * 50)
    print("Test Results Summary")
    print("=" * 50)
    
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{name}: {status}")
    
    # Return exit code
    all_passed = all(passed for _, passed in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_tests())
