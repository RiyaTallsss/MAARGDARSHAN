"""Setup configuration for the AI-Powered Rural Infrastructure Planning System."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text() if (this_directory / "README.md").exists() else ""

# Read requirements - use minimal for now to avoid GDAL dependency issues
requirements = []
if (this_directory / "requirements-minimal.txt").exists():
    with open("requirements-minimal.txt") as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="rural-infrastructure-planning",
    version="0.1.0",
    author="Rural Infrastructure Planning Team",
    author_email="team@rural-infrastructure.ai",
    description="AI-Powered Rural Infrastructure Planning System for challenging terrain",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rural-infrastructure/planning-system",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: GIS",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.2.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "hypothesis>=6.70.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0",
        ],
        "viz": [
            "folium>=0.14.0",
            "matplotlib>=3.6.0",
            "contextily>=1.3.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "rural-planning=rural_infrastructure_planning.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "rural_infrastructure_planning": [
            "config/*.yaml",
            "data/templates/*.json",
        ],
    },
)