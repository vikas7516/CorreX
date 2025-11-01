"""Setup configuration for CorreX package."""
from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read the requirements file
requirements_file = Path(__file__).parent / "correX" / "requirements.txt"
if requirements_file.exists():
    with open(requirements_file, "r", encoding="utf-8") as f:
        install_requires = [line.strip() for line in f if line.strip() and not line.startswith("#")]
else:
    install_requires = [
        "google-generativeai>=0.3.0",
        "keyboard>=0.13.5",
        "pywin32>=306",
        "pywinauto>=0.6.8",
        "pystray>=0.19.5",
        "Pillow>=10.0.0",
        "SpeechRecognition>=3.10.0",
        "PyAudio>=0.2.13",
        "noisereduce>=3.0.0",
        "numpy>=1.24.0",
    ]

setup(
    name="correX",
    version="1.0.0",
    author="CorreX Project",
    author_email="",
    description="AI-Powered Text Correction & Voice Dictation for Windows",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/vikas7516/CorreX",
    project_urls={
        "Bug Reports": "https://github.com/vikas7516/CorreX/issues",
        "Source": "https://github.com/vikas7516/CorreX",
        "Documentation": "https://github.com/vikas7516/CorreX/blob/main/DEVNOTES.md",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Text Processing :: Linguistic",
        "Topic :: Office/Business",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: Microsoft :: Windows :: Windows 10",
        "Operating System :: Microsoft :: Windows :: Windows 11",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Environment :: Win32 (MS Windows)",
        "Natural Language :: English",
    ],
    keywords="text-correction autocorrect ai gemini voice-dictation speech-to-text windows accessibility",
    python_requires=">=3.8",
    install_requires=install_requires,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "correx=correX.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "correX": [
            "assets/**/*",
            "assets/icons/*",
            "*.md",
            "requirements.txt",
        ],
    },
    zip_safe=False,
    platforms=["Windows"],
    license="MIT",
)
