"""
Setup script for quantum_feedback package
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="quantum_feedback",
    version="1.0.0",
    author="Quantum Feedback Analysis Contributors",
    author_email="your-email@example.com",
    description="A toolkit for analyzing quantum measurement feedback data",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/quantum_feedback_analysis",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Physics",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.7",
    install_requires=[
        "numpy>=1.21.0",
        "scipy>=1.7.0",
        "matplotlib>=3.4.0",
        "scikit-learn>=0.24.0",
    ],
    extras_require={
        "api": ["flask>=2.0.0", "flask-cors>=3.0.0"],
        "notebook": ["jupyter>=1.0.0"],
        "dev": ["pytest>=6.0", "black>=21.0", "flake8>=3.9"],
    },
)
