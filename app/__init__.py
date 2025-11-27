"""
Vanna SQL Service

A modular, self-contained service for natural language to SQL generation.
Uses QudrantDB for local vector storage and OpenAI for LLM.

No Vanna API key required - fully self-hosted solution.
"""

__version__ = "1.0.1"
__author__ = "Exelixi AI"

from .client import VannaSQLClient, AsyncVannaSQLClient, SQLResult

__all__ = [
    "VannaSQLClient",
    "AsyncVannaSQLClient", 
    "SQLResult"
]
