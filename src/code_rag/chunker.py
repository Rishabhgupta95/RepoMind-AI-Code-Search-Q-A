from pathlib import Path

from tree_sitter import Language, Parser
import tree_sitter_javascript as ts_javascript
import tree_sitter_python as ts_python

from .config import CHUNK_OVERLAP_LINES, MAX_CHUNK_LINES
from .scanner import detect_language


PYTHON_LANGUAGE = Language(ts_python.language())
JAVASCRIPT_LANGUAGE = Language(ts_javascript.language())


def parser_for(language: str) -> Parser | None:
    grammar = {
        "python": PYTHON_LANGUAGE,
        "javascript": JAVASCRIPT_LANGUAGE,
    }.get(language)
    return Parser(grammar) if grammar is not None else None


def node_text(source: bytes, node) -> str:
    return source[node.start_byte : node.end_byte].decode(
        "utf-8",
        errors="replace",
    )


def _split_lines(
    code: str,
    start_line: int,
    max_lines: int = MAX_CHUNK_LINES,
) -> list[tuple[int, int, str]]:
    lines = code.splitlines()
    if not lines:
        return []

    overlap = min(CHUNK_OVERLAP_LINES, max_lines - 1)
    step = max_lines - overlap
    pieces = []
    for offset in range(0, len(lines), step):
        part = lines[offset : offset + max_lines]
        if not part:
            break
        first_line = start_line + offset
        pieces.append((first_line, first_line + len(part) - 1, "\n".join(part)))
    return pieces


def _definition_chunks(
    source: bytes,
    root_node,
    path: Path,
    language: str,
) -> list[dict]:
    chunks = []
    python_definitions = {"function_definition", "class_definition"}
    javascript_definitions = {
        "function_declaration",
        "class_declaration",
        "method_definition",
    }
    definition_types = (
        python_definitions if language == "python" else javascript_definitions
    )

    def direct_definitions(node):
        found = []
        for child in node.children:
            if child.type in definition_types:
                found.append(child)
            elif child.type not in python_definitions | javascript_definitions:
                found.extend(direct_definitions(child))
        return found

    def walk(node, parent_name: str | None = None):
        if node.type not in definition_types:
            for child in node.children:
                walk(child, parent_name)
            return

        name_node = node.child_by_field_name("name")
        name = node_text(source, name_node) if name_node is not None else "anonymous"
        symbol = f"{parent_name}.{name}" if parent_name else name

        if node.type in {"class_definition", "class_declaration"}:
            members = direct_definitions(node)
            if members:
                for member in members:
                    walk(member, symbol)
                return

        code = node_text(source, node)
        pieces = _split_lines(code, node.start_point[0] + 1)
        for part_number, (start_line, end_line, part) in enumerate(pieces, start=1):
            chunks.append(
                {
                    "file": str(path),
                    "language": language,
                    "symbol": (
                        symbol
                        if len(pieces) == 1
                        else f"{symbol} (part {part_number})"
                    ),
                    "type": node.type,
                    "start_line": start_line,
                    "end_line": end_line,
                    "code": part,
                }
            )

    walk(root_node)

    # Functions/classes are indexed above; retain remaining module-level code as
    # chunks too, so imports, constants, and module setup remain searchable.
    for node in root_node.named_children:
        if any(
            descendant.type in definition_types
            for descendant in _walk_nodes(node)
        ):
            continue
        node_source = node_text(source, node)
        if language == "javascript" and any(
            descendant.type in {"arrow_function", "function_expression"}
            for descendant in _walk_nodes(node)
        ):
            continue
        for start_line, end_line, part in _split_lines(
            node_source, node.start_point[0] + 1
        ):
            chunks.append(
                {
                    "file": str(path),
                    "language": language,
                    "symbol": "module",
                    "type": "module_statement",
                    "start_line": start_line,
                    "end_line": end_line,
                    "code": part,
                }
            )

    if language == "javascript":

        def walk_arrows(node):
            if node.type == "variable_declarator":
                value = node.child_by_field_name("value")
                name_node = node.child_by_field_name("name")
                if value is not None and value.type in {
                    "arrow_function",
                    "function_expression",
                }:
                    name = (
                        node_text(source, name_node)
                        if name_node is not None
                        else "anonymous"
                    )
                    for start_line, end_line, part in _split_lines(
                        node_text(source, node), node.start_point[0] + 1
                    ):
                        chunks.append(
                            {
                                "file": str(path),
                                "language": language,
                                "symbol": name,
                                "type": value.type,
                                "start_line": start_line,
                                "end_line": end_line,
                                "code": part,
                            }
                        )
            for child in node.children:
                walk_arrows(child)

        walk_arrows(root_node)

    return chunks


def _walk_nodes(node):
    yield node
    for child in node.children:
        yield from _walk_nodes(child)


def _text_chunks(source_text: str, path: Path, language: str) -> list[dict]:
    return [
        {
            "file": str(path),
            "language": language,
            "symbol": f"lines {start_line}-{end_line}",
            "type": "text_block",
            "start_line": start_line,
            "end_line": end_line,
            "code": code,
        }
        for start_line, end_line, code in _split_lines(source_text, 1)
        if code.strip()
    ]


def chunk_file(file_path: str, relative_path: str | None = None) -> list[dict]:
    """Chunk one file semantically where a bundled Tree-sitter grammar exists."""
    path = Path(file_path)
    text = path.read_text(encoding="utf-8", errors="replace")
    language = detect_language(path)
    parser = parser_for(language)
    chunks = []
    if parser is not None:
        source = text.encode("utf-8")
        tree = parser.parse(source)
        chunks = _definition_chunks(source, tree.root_node, path, language)
    if not chunks:
        chunks = _text_chunks(text, path, language)

    display_path = relative_path or str(path)
    for chunk in chunks:
        chunk["file"] = display_path
    return chunks


def chunk_python_file(file_path: str) -> list[dict]:
    """Backward-compatible Python-specific chunking entry point."""
    if detect_language(file_path) != "python":
        raise ValueError(f"Expected a Python file, got {file_path!r}")
    return chunk_file(file_path)