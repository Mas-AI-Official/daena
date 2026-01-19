"""
Setup configuration for Daena Python SDK.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="daena-sdk",
    version="1.0.0",
    description="Official Python SDK for Daena AI VP System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="MAS-AI Technology Inc.",
    author_email="support@mas-ai.com",
    url="https://github.com/Masoud-Masoori/daena",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "requests>=2.31.0",
        "urllib3>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.7.0",
            "mypy>=1.5.0",
            "ruff>=0.0.280",
        ],
        "websocket": [
            "websockets>=11.0",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="ai agents memory nbmf enterprise sdk",
)

