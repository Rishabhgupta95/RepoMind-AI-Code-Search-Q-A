# Code RAG

Index local Git working trees or GitHub repositories, search their source, and ask questions grounded in retrieved code. FastAPI exposes the pipeline; Qdrant stores vectors and source metadata.

## Flow

1. `POST /index` accepts a local repository directory or Git URL. Remote repositories are cloned under `data/repositories/` the first time; an existing clone is reused without an automatic pull.
2. The scanner filters ignored folders, unsupported extensions, and files larger than `MAX_FILE_BYTES`, then identifies the language from the file extension.
3. Tree-sitter extracts Python and JavaScript declarations. Other supported file types use bounded line chunks until their grammar is installed. All chunks include relative file paths and 1-based line ranges.
4. Sentence Transformers embeds chunks in batches. Qdrant upserts stable IDs and source metadata; stale chunks are removed only after the complete indexing pass succeeds.
5. `POST /search` embeds the query and returns matching code chunks. `POST /ask` uses the same retrieval and asks the configured OpenAI model to answer from that context. Retrieved sources are always returned separately for verifiable citations.

## Run

Start a Qdrant instance at the configured `QDRANT_URL`, configure the environment below, then run the API from the project root:

```sh
PYTHONPATH=src uv run uvicorn code_rag.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation.

## Configuration

Configuration is read from environment variables or `.env`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |
| `QDRANT_API_KEY` | unset | Optional key for Qdrant Cloud |
| `QDRANT_COLLECTION` | `code_chunks` | Collection name |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence Transformers model |
| `LLM_MODEL` | `gpt-4o-mini` | OpenAI chat model |
| `OPENAI_API_KEY` | unset | Required only by `/ask` |
| `REPOSITORY_DIRECTORY` | `data/repositories` | Destination for remote clones |
| `MAX_FILE_BYTES` | `1000000` | Maximum indexed file size |
| `MAX_REPOSITORY_FILES` | `10000` | Maximum supported files per repo |
| `MAX_CHUNK_LINES` | `80` | Maximum lines per chunk |
| `CHUNK_OVERLAP_LINES` | `8` | Context overlap for split chunks |
| `UPSERT_BATCH_SIZE` | `100` | Embedding/Qdrant batch size |

Do not commit API keys. The Qdrant collection vector size is checked against the selected embedding model; choose a new collection if changing to an embedding model with a different dimension.

## API examples

Index a local repo or remote URL with `POST /index`:

```json
{"repository": "/absolute/path/to/repository"}
```

Search with `POST /search`:

```json
{"query": "Where is user authentication implemented?", "repository": "/absolute/path/to/repository", "limit": 5}
```

Ask with `POST /ask` using the same request shape. Results include `answer` and `sources` with file and line metadata.

## Verify

```sh
PYTHONPATH=src uv run python -m unittest discover -s tests -v
```
