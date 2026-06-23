"""
Quick start script for Quantum Feedback Analysis
"""

import subprocess
import sys
import os

def check_dependencies():
    """Check if required packages are installed"""
    print("Checking dependencies...")
    try:
        import numpy
        import scipy
        import matplotlib
        import sklearn
        import flask
        print("✓ All dependencies are installed")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        print("\nPlease install dependencies:")
        print("  pip install -r requirements.txt")
        return False

def check_data_file():
    """Check if data file exists"""
    print("\nChecking data file...")
    if os.path.exists('./s21_data.mat'):
        print("✓ Data file found: s21_data.mat")
        return True
    else:
        print("✗ Data file not found: s21_data.mat")
        print("\nPlease place your s21_data.mat file in this directory")
        return False

def main():
    """Main quick start function"""
    print("=" * 60)
    print("Quantum Feedback Analysis - Quick Start")
    print("=" * 60)

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Check data file
    if not check_data_file():
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Setup complete! You can now:")
    print("=" * 60)
    print("\n1. Run the Jupyter notebook:")
    print("   jupyter notebook feedback.ipynb")
    print("\n2. Start the API server:")
    print("   python api.py")
    print("\n3. Test the API (in another terminal):")
    print("   python example_usage.py")
    print("\n4. Use the Python API directly:")
    print("   from api import QuantumFeedbackAnalyzer")
    print("   analyzer = QuantumFeedbackAnalyzer()")
    print("   analyzer.load_data()")
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
