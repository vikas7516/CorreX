#!/usr/bin/env python3
"""Test runner script for CorreX project."""
from __future__ import annotations

import sys
import subprocess
from pathlib import Path


def run_tests(args: list[str] | None = None) -> int:
    """Run pytest with specified arguments.
    
    Args:
        args: Additional pytest arguments
        
    Returns:
        Exit code from pytest
    """
    project_root = Path(__file__).parent
    
    cmd = ["pytest"]
    
    if args:
        cmd.extend(args)
    else:
        # Default: run all tests with coverage
        cmd.extend([
            "-v",
            "--cov=correX",
            "--cov-report=term-missing",
            "--cov-report=html",
        ])
    
    print(f"Running: {' '.join(cmd)}")
    print(f"Working directory: {project_root}")
    print("-" * 60)
    
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode


def main() -> int:
    """Main entry point."""
    print("=" * 60)
    print("CorreX Test Runner")
    print("=" * 60)
    print()
    
    # Pass command-line arguments to pytest
    args = sys.argv[1:] if len(sys.argv) > 1 else None
    
    if args and args[0] in ["-h", "--help"]:
        print("Usage: python run_tests.py [pytest arguments]")
        print()
        print("Examples:")
        print("  python run_tests.py                    # Run all tests with coverage")
        print("  python run_tests.py tests/test_*.py    # Run specific tests")
        print("  python run_tests.py -k buffer          # Run tests matching 'buffer'")
        print("  python run_tests.py -m unit            # Run only unit tests")
        print("  python run_tests.py -v -s              # Verbose with print output")
        print("  python run_tests.py --cov-report=xml   # Generate XML coverage report")
        return 0
    
    exit_code = run_tests(args)
    
    print()
    print("=" * 60)
    if exit_code == 0:
        print("✅ All tests passed!")
        print()
        print("View coverage report:")
        print("  - Console: See output above")
        print("  - HTML: Open htmlcov/index.html")
    else:
        print("❌ Some tests failed!")
        print()
        print("Debug tips:")
        print("  - Run with -vv for more verbose output")
        print("  - Run with --pdb to drop into debugger on failure")
        print("  - Run specific test: python run_tests.py tests/test_file.py::test_name")
    print("=" * 60)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
