"""Setup script for Brainrot Generator."""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="brainrot-generator",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="AI-powered pipeline for discovering trends and generating viral short-form content",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/brainrot_generator",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        # Core
        "fastapi>=0.104.1",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        
        # YouTube & Web
        "yt-dlp>=2023.11.16",
        "playwright>=1.40.0",
        "google-api-python-client>=2.108.0",
        
        # Video Processing
        "opencv-python>=4.8.1.78",
        "pillow>=10.1.0",
        
        # AI
        "openai>=1.3.7",
        "transformers>=4.35.2",
        
        # Utilities
        "python-dotenv>=1.0.0",
        "httpx>=0.25.2",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
        "full": [
            "whisperx>=3.1.1",
            "torch>=2.1.1",
            "torchvision>=0.16.1",
            "celery>=5.3.4",
            "redis>=5.0.1",
        ],
    },
)

