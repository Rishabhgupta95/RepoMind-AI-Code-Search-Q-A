import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "code_chunks")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
REPOSITORY_DIRECTORY = Path(
	os.getenv("REPOSITORY_DIRECTORY", "data/repositories")
).expanduser()

MAX_FILE_BYTES = int(os.getenv("MAX_FILE_BYTES", str(1_000_000)))
MAX_REPOSITORY_FILES = int(os.getenv("MAX_REPOSITORY_FILES", "10000"))
MAX_CHUNK_LINES = int(os.getenv("MAX_CHUNK_LINES", "80"))
CHUNK_OVERLAP_LINES = int(os.getenv("CHUNK_OVERLAP_LINES", "8"))
UPSERT_BATCH_SIZE = int(os.getenv("UPSERT_BATCH_SIZE", "100"))

if MAX_CHUNK_LINES < 1:
	raise ValueError("MAX_CHUNK_LINES must be at least 1")
if CHUNK_OVERLAP_LINES < 0 or CHUNK_OVERLAP_LINES >= MAX_CHUNK_LINES:
	raise ValueError("CHUNK_OVERLAP_LINES must be between 0 and MAX_CHUNK_LINES - 1")
if UPSERT_BATCH_SIZE < 1:
	raise ValueError("UPSERT_BATCH_SIZE must be at least 1")
