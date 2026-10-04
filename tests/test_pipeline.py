import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from code_rag.chunker import chunk_file
from code_rag.indexer import index_repository
from code_rag.main import app
from code_rag.repository import repository_key, repository_name
from code_rag.scanner import detect_language


class ChunkerTests(unittest.TestCase):
    def test_python_class_methods_and_functions_are_semantic_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.py"
            source.write_text(
                "class UserService:\n"
                "    def authenticate(self, name):\n"
                "        return name\n\n"
                "def greet():\n"
                "    return 'hello'\n",
                encoding="utf-8",
            )

            chunks = chunk_file(str(source), relative_path="sample.py")

        self.assertEqual({"UserService.authenticate", "greet"}, {c["symbol"] for c in chunks})
        self.assertEqual({"python"}, {c["language"] for c in chunks})
        self.assertEqual({"sample.py"}, {c["file"] for c in chunks})

    def test_javascript_class_method_and_arrow_function_are_chunked(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.js"
            source.write_text(
                "class UserService {\n"
                "  authenticate(name) { return name; }\n"
                "}\n"
                "const greet = (name) => `hello ${name}`;\n",
                encoding="utf-8",
            )

            chunks = chunk_file(str(source))

        self.assertIn("UserService.authenticate", {c["symbol"] for c in chunks})
        self.assertIn("greet", {c["symbol"] for c in chunks})

    def test_unbundled_grammar_uses_bounded_line_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "Example.java"
            source.write_text("class Example {\n  void run() {}\n}\n", encoding="utf-8")

            chunks = chunk_file(str(source))

        self.assertEqual("java", chunks[0]["language"])
        self.assertEqual("text_block", chunks[0]["type"])
        self.assertEqual(1, chunks[0]["start_line"])


class RepositoryTests(unittest.TestCase):
    def test_github_url_and_scp_url_have_stable_keys(self):
        https_key = repository_key("https://GitHub.com/Owner/Project.git")
        ssh_key = repository_key("git@github.com:Owner/Project.git")
        self.assertEqual("github.com/owner/project", https_key)
        self.assertEqual(https_key, ssh_key)
        self.assertEqual("Project", repository_name("https://github.com/Owner/Project.git"))

    def test_language_detection_uses_extension(self):
        self.assertEqual("typescript", detect_language("src/app.tsx"))
        self.assertEqual("text", detect_language("src/unknown.bin"))


class IndexerTests(unittest.TestCase):
    def test_local_index_batches_vectors_and_prunes_stale_points(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "service.py").write_text(
                "def authenticate(user):\n    return user\n",
                encoding="utf-8",
            )
            upserted_points = []

            with (
                patch("code_rag.indexer.embedding_dimension", return_value=3),
                patch("code_rag.indexer.ensure_collection") as ensure_collection,
                patch("code_rag.indexer.repository_point_ids", return_value={"stale"}),
                patch("code_rag.indexer.embed_many", side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts]),
                patch("code_rag.indexer.upsert_points", side_effect=upserted_points.extend),
                patch("code_rag.indexer.delete_points") as delete_points,
            ):
                summary = index_repository(str(root))

        self.assertEqual(1, summary["files_scanned"])
        self.assertEqual(1, summary["chunks_indexed"])
        ensure_collection.assert_called_once_with(3)
        self.assertEqual(1, len(upserted_points))
        self.assertEqual("service.py", upserted_points[0].payload["file"])
        self.assertEqual("authenticate", upserted_points[0].payload["symbol"])
        delete_points.assert_called_once_with({"stale"})


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_route(self):
        response = self.client.get("/health")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "ok"}, response.json())

    def test_index_route_returns_index_summary(self):
        summary = {
            "repository": "example",
            "repository_path": "/tmp/example",
            "files_scanned": 2,
            "chunks_indexed": 3,
        }
        with patch("code_rag.main.index_repository", return_value=summary):
            response = self.client.post("/index", json={"repository": "/tmp/example"})
        self.assertEqual(200, response.status_code)
        self.assertEqual(summary, response.json())

    def test_index_route_rejects_invalid_local_path(self):
        with patch(
            "code_rag.main.index_repository",
            side_effect=ValueError("Local repository directory does not exist"),
        ):
            response = self.client.post("/index", json={"repository": "/missing"})
        self.assertEqual(400, response.status_code)

    def test_search_route_returns_ranked_chunks(self):
        results = [{"file": "src/auth.py", "start_line": 3, "score": 0.9}]
        with patch("code_rag.main.search_code", return_value=results) as search_code:
            response = self.client.post(
                "/search",
                json={"query": "authentication", "limit": 3},
            )
        self.assertEqual(200, response.status_code)
        self.assertEqual(results, response.json()["results"])
        search_code.assert_called_once_with(
            "authentication",
            limit=3,
            repository=None,
        )

    def test_ask_route_returns_answer_and_citations(self):
        sources = [{"file": "src/auth.py", "start_line": 3, "end_line": 7}]
        with (
            patch("code_rag.main.search_code", return_value=sources),
            patch("code_rag.main.answer_from_context", return_value="Auth is here.") as answer,
        ):
            response = self.client.post(
                "/ask",
                json={"query": "Where is authentication?"},
            )
        self.assertEqual(200, response.status_code)
        self.assertEqual("Auth is here.", response.json()["answer"])
        self.assertEqual(sources, response.json()["sources"])
        answer.assert_called_once_with("Where is authentication?", sources)


if __name__ == "__main__":
    unittest.main()