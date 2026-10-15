import { useEffect, useRef, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [repository, setRepository] = useState("");
  const [indexedRepository, setIndexedRepository] = useState("");
  const [task, setTask] = useState(null);
  const [question, setQuestion] = useState("");
  const [results, setResults] = useState([]);
  const [answer, setAnswer] = useState("");
  const [loadingIndex, setLoadingIndex] = useState(false);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [error, setError] = useState("");
  const [searchMode, setSearchMode] = useState("search");

  const pollingRef = useRef(null);

  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  async function startIndexing(event) {
    event.preventDefault();

    if (!repository.trim()) {
      setError("Please enter a GitHub repository URL.");
      return;
    }

    if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }

    setError("");
    setResults([]);
    setAnswer("");
    setTask(null);
    setLoadingIndex(true);

    try {
      const response = await fetch(`${API_URL}/index`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          repository: repository.trim(),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not start indexing.");
      }

      setTask(data);
      setIndexedRepository(repository.trim());

      await pollTask(data.task_id);
    } catch (err) {
      setError(err.message || "Unable to connect to the backend.");
      setLoadingIndex(false);
    }
  }

  async function pollTask(taskId) {
    let stopped = false;

    const checkStatus = async () => {
      if (stopped) return;

      try {
        const response = await fetch(
          `${API_URL}/index/${taskId}`
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail || "Could not fetch indexing status."
          );
        }

        setTask(data);

        if (data.status === "completed") {
          stopped = true;
          clearInterval(pollingRef.current);
          pollingRef.current = null;
          setLoadingIndex(false);
        } else if (data.status === "failed") {
          stopped = true;
          clearInterval(pollingRef.current);
          pollingRef.current = null;
          setLoadingIndex(false);
          setError(data.error || "Repository indexing failed.");
        }
      } catch (err) {
        stopped = true;
        clearInterval(pollingRef.current);
        pollingRef.current = null;
        setLoadingIndex(false);
        setError(err.message || "Unable to check indexing status.");
      }
    };

    await checkStatus();

    if (!stopped) {
      pollingRef.current = setInterval(checkStatus, 1500);
    }
  }

  async function searchCode(event) {
    event.preventDefault();

    if (!question.trim()) {
      setError("Please enter a question about your code.");
      return;
    }

    if (!indexedRepository || task?.status !== "completed") {
      setError("Please index a repository successfully first.");
      return;
    }

    setError("");
    setResults([]);
    setAnswer("");
    setLoadingSearch(true);

    try {
      const endpoint =
        searchMode === "ask" ? "/ask" : "/search";

      const response = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: question.trim(),
          repository: indexedRepository,
          limit: 5,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Code search failed."
        );
      }

      setResults(
        searchMode === "ask"
          ? data.sources || []
          : data.results || []
      );

      if (searchMode === "ask") {
        setAnswer(data.answer || "No answer was generated.");
      }
    } catch (err) {
      setError(
        err.message ||
          "Unable to search code. Check that the backend is running."
      );
    } finally {
      setLoadingSearch(false);
    }
  }

  function formatScore(score) {
    if (typeof score !== "number") return null;

    return `${(score * 100).toFixed(1)}%`;
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#home">
          <span className="brand-icon">&lt;/&gt;</span>
          <span>
            Repo<span className="brand-accent">Mind</span>
          </span>
        </a>

        <div className="topbar-right">
          <span className="status-dot" />
          <span>AI Code Intelligence</span>
        </div>
      </header>

      <main className="main-content" id="home">
        <section className="hero">
          <div className="eyebrow">
            <span className="eyebrow-icon">✦</span>
            YOUR CODEBASE, UNDERSTOOD
          </div>

          <h1>
            Understand your code.
            <br />
            <span>Find answers faster.</span>
          </h1>

          <p className="hero-description">
            Connect a GitHub repository and ask questions about
            its code. Find relevant files, explore implementations,
            and understand how your project works.
          </p>
        </section>

        <section className="panel repository-panel">
          <div className="panel-heading">
            <div className="heading-icon">⌘</div>

            <div>
              <h2>Connect repository</h2>
              <p>Start by indexing a GitHub repository.</p>
            </div>
          </div>

          <form onSubmit={startIndexing}>
            <label htmlFor="repository">
              GitHub repository URL
            </label>

            <div className="input-row">
              <span className="input-prefix">↗</span>

              <input
                id="repository"
                type="url"
                placeholder="https://github.com/username/repository"
                value={repository}
                onChange={(event) =>
                  setRepository(event.target.value)
                }
                required
              />

              <button
                className="primary-button"
                type="submit"
                disabled={loadingIndex}
              >
                {loadingIndex
                  ? "Indexing..."
                  : "Index repository"}
                <span>→</span>
              </button>
            </div>
          </form>

          {task && (
            <div className="index-status">
              <div className="status-header">
                <div>
                  <span
                    className={`status-badge ${
                      task.status === "completed"
                        ? "success"
                        : task.status === "failed"
                          ? "failure"
                          : "processing"
                    }`}
                  >
                    {task.status || "queued"}
                  </span>

                  <span className="stage-label">
                    {task.stage || "Waiting to start"}
                  </span>
                </div>

                <strong>
                  {task.percent ?? 0}%
                </strong>
              </div>

              <div
                className="progress-track"
                role="progressbar"
                aria-valuenow={task.percent ?? 0}
                aria-valuemin="0"
                aria-valuemax="100"
              >
                <div
                  className="progress-fill"
                  style={{
                    width: `${Math.min(
                      100,
                      Math.max(0, task.percent ?? 0)
                    )}%`,
                  }}
                />
              </div>

              <div className="stats-grid">
                <div className="stat-card">
                  <span>Files scanned</span>
                  <strong>{task.files_scanned ?? 0}</strong>
                </div>

                <div className="stat-card">
                  <span>Files processed</span>
                  <strong>{task.files_processed ?? 0}</strong>
                </div>

                <div className="stat-card">
                  <span>Total chunks</span>
                  <strong>{task.chunks_total ?? 0}</strong>
                </div>

                <div className="stat-card">
                  <span>Chunks indexed</span>
                  <strong>{task.chunks_indexed ?? 0}</strong>
                </div>
              </div>
            </div>
          )}
        </section>

        <section className="panel search-panel">
          <div className="panel-heading">
            <div className="heading-icon search-icon">⌕</div>

            <div>
              <h2>Explore your codebase</h2>
              <p>
                Ask a question in plain English.
              </p>
            </div>
          </div>

          <form onSubmit={searchCode}>
            <label htmlFor="question">
              What do you want to find?
            </label>

            <textarea
              id="question"
              rows="3"
              placeholder="e.g. Where is the group creation logic implemented?"
              value={question}
              onChange={(event) =>
                setQuestion(event.target.value)
              }
            />

            <div className="search-actions">
              <div className="mode-selector">
                <button
                  type="button"
                  className={
                    searchMode === "search" ? "mode active" : "mode"
                  }
                  onClick={() => setSearchMode("search")}
                >
                  Code search
                </button>

                <button
                  type="button"
                  className={
                    searchMode === "ask" ? "mode active" : "mode"
                  }
                  onClick={() => setSearchMode("ask")}
                >
                  AI answer
                </button>
              </div>

              <button
                className="primary-button search-button"
                type="submit"
                disabled={
                  loadingSearch ||
                  loadingIndex ||
                  task?.status !== "completed"
                }
              >
                {loadingSearch
                  ? "Searching..."
                  : searchMode === "ask"
                    ? "Ask RepoMind"
                    : "Search code"}
                <span>→</span>
              </button>
            </div>
          </form>

          <div className="suggestions">
            <span>Try asking:</span>

            {[
              "Where is group creation code?",
              "How does authentication work?",
              "Where are API endpoints defined?",
            ].map((suggestion) => (
              <button
                type="button"
                key={suggestion}
                onClick={() => setQuestion(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </section>

        {error && (
          <div className="error-message" role="alert">
            <span>!</span>
            {error}
            <button
              type="button"
              onClick={() => setError("")}
              aria-label="Dismiss error"
            >
              ×
            </button>
          </div>
        )}

        {(answer || results.length > 0) && (
          <section className="results-section">
            <div className="results-heading">
              <div>
                <span className="section-kicker">
                  SEARCH RESULTS
                </span>
                <h2>
                  {searchMode === "ask"
                    ? "Answer from your codebase"
                    : "Relevant code"}
                </h2>
              </div>

              <span className="result-count">
                {results.length} source
                {results.length === 1 ? "" : "s"}
              </span>
            </div>

            {answer && (
              <article className="answer-card">
                <h3>✦ RepoMind's answer</h3>
                <p>{answer}</p>
              </article>
            )}

            {results.map((result, index) => (
              <article
                className="result-card"
                key={`${result.file}-${result.start_line}-${index}`}
              >
                <div className="result-card-header">
                  <div className="file-info">
                    <span className="file-icon">
                      {result.language === "typescript" ||
                      result.language === "javascript"
                        ? "TS"
                        : result.language === "python"
                          ? "PY"
                          : "{"}
                    </span>

                    <div>
                      <h3>{result.file || "Unknown file"}</h3>

                      <p>
                        {result.start_line != null
                          ? `Lines ${result.start_line}–${result.end_line}`
                          : result.symbol || "Source code"}
                      </p>
                    </div>
                  </div>

                  {formatScore(result.score) && (
                    <span className="score-badge">
                      Match {formatScore(result.score)}
                    </span>
                  )}
                </div>

                <pre className="code-block">
                  <code>{result.code || "No code snippet available."}</code>
                </pre>
              </article>
            ))}
          </section>
        )}

        {task?.status === "completed" &&
          results.length === 0 &&
          !answer &&
          !loadingSearch && (
            <p className="empty-hint">
              Your repository is indexed. Ask a question above
              to explore its code.
            </p>
          )}
      </main>

      <footer className="footer">
        <span>
          <span className="footer-brand">RepoMind</span>
          {" "}· AI-powered code search
        </span>
        <span>Built for developers</span>
      </footer>
    </div>
  );
}

export default App;