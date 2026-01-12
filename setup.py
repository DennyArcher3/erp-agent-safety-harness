from setuptools import setup, find_packages

setup(
    name="erp-agent-safety-harness",
    version="0.1.0",
    description="Safety layer for AI-driven financial operations",
    author="Erhan Guclu",
    author_email="erhanguclu.3@gmail.com",
    url="https://github.com/DennyArcher3/erp-agent-safety-harness",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9",
    install_requires=[],  # No external dependencies for core functionality
    extras_require={
        "dev": ["pytest", "pytest-cov", "black", "mypy"],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Security",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
