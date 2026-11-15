from setuptools import setup, find_packages

setup(
    name="prs",
    version="0.1.0",
    description="Analysis of presidential speech corpora",
    packages=find_packages(include=["prs", "prs.*", "prespeech", "prespeech.*"]),
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "prs=prs.cli:main",
            "prespeech=prs.cli:main",
        ],
    },
)
