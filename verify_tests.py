"""
Quick test verification

Run this to verify test setup is working correctly.
"""

import os
import sys


def verify_test_structure():
    """Verify all test files exist"""
    
    print("Verifying test structure...")
    print("=" * 50)
    
    required_files = [
        "tests/__init__.py",
        "tests/conftest.py",
        "tests/README.md",
        "tests/unit/__init__.py",
        "tests/unit/config/__init__.py",
        "tests/unit/config/test_settings_validation.py",
        "tests/unit/config/test_feature_flags.py",
        "tests/unit/config/test_security.py",
        "tests/unit/config/test_constants.py",
        "tests/unit/config/test_environments.py",
        "tests/integration/__init__.py",
        "tests/integration/config/__init__.py",
        "tests/integration/config/test_config_integration.py",
    ]
    
    all_exist = True
    for filepath in required_files:
        exists = os.path.exists(filepath)
        status = "✓" if exists else "✗"
        print(f"{status} {filepath}")
        if not exists:
            all_exist = False
    
    print("=" * 50)
    
    if all_exist:
        print("✓ All test files found!")
        return True
    else:
        print("✗ Some test files are missing")
        return False


def count_test_functions():
    """Count test functions in test files"""
    
    print("\nCounting tests...")
    print("=" * 50)
    
    import glob
    
    total_tests = 0
    
    # Find all test files
    test_files = glob.glob("tests/**/test_*.py", recursive=True)
    
    for test_file in sorted(test_files):
        with open(test_file, 'r') as f:
            content = f.read()
            # Count functions that start with 'test_'
            test_count = content.count("def test_")
            total_tests += test_count
            
            print(f"{test_file}: {test_count} tests")
    
    print("=" * 50)
    print(f"Total tests: {total_tests}")
    
    return total_tests


def check_dependencies():
    """Check if required packages are installed"""
    
    print("\nChecking dependencies...")
    print("=" * 50)
    
    required_packages = ['pytest', 'pydantic', 'pydantic_settings']
    
    all_installed = True
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} installed")
        except ImportError:
            print(f"✗ {package} NOT installed")
            all_installed = False
    
    print("=" * 50)
    
    if not all_installed:
        print("\nTo install missing dependencies:")
        print("pip3 install -r requirements.txt")
    
    return all_installed


def main():
    """Main verification function"""
    
    print("\n" + "=" * 50)
    print("Config Module Test Verification")
    print("=" * 50 + "\n")
    
    # Verify structure
    structure_ok = verify_test_structure()
    
    # Count tests
    test_count = count_test_functions()
    
    # Check dependencies
    deps_ok = check_dependencies()
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Test structure: {'✓ OK' if structure_ok else '✗ ISSUES'}")
    print(f"Total test count: {test_count}")
    print(f"Dependencies: {'✓ OK' if deps_ok else '✗ MISSING'}")
    print("=" * 50)
    
    if structure_ok and deps_ok and test_count > 0:
        print("\n✓ Test setup is ready!")
        print("\nTo run tests:")
        print("  python3 -m pytest tests/unit/config/ tests/integration/config/ -v")
        return 0
    else:
        print("\n✗ Test setup needs attention")
        return 1


if __name__ == "__main__":
    sys.exit(main())
