#!/usr/bin/env python3
"""Local Tree-sitter playground with REST and MCP interfaces."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, TypeAlias, TypedDict, get_args

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from tree_sitter import Language, Node, Parser

MAX_CODE_BYTES = 1_000_000
HOST = "127.0.0.1"
PORT = 8765

JsonValue: TypeAlias = str | int | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


class PointResponse(TypedDict):
    row: int
    column: int


class AstNode(TypedDict):
    type: str
    start_byte: int
    end_byte: int
    start_point: PointResponse
    end_point: PointResponse
    text: str
    is_named: bool
    children: list["AstNode"]


class ParseSuccess(TypedDict):
    success: Literal[True]
    ast: AstNode


class ParseFailure(TypedDict):
    success: Literal[False]
    error: str


ParseResult: TypeAlias = ParseSuccess | ParseFailure


class ParseRequest(BaseModel):
    code: str = ""
    language: str = "python"


LANGUAGE_PARSERS: dict[str, tuple[str, str]] = {}
CUSTOM_PARSERS: dict[str, Language] = {}


def initialize_parsers() -> None:
    """Register all parsers supplied by tree-sitter-language-pack."""
    import tree_sitter_language_pack

    LANGUAGE_PARSERS.clear()
    available = get_args(tree_sitter_language_pack.SupportedLanguage)
    for language in available:
        LANGUAGE_PARSERS[language] = ("pack", language)


def get_parser(language: str) -> Parser:
    """Return a parser registered for ``language``."""
    try:
        source, language_name = LANGUAGE_PARSERS[language]
    except KeyError as error:
        raise ValueError(f"Language {language!r} is not supported") from error

    if source == "pack":
        import tree_sitter_language_pack

        return tree_sitter_language_pack.get_parser(language_name)
    if source == "custom":
        return Parser(CUSTOM_PARSERS[language_name])
    raise ValueError(f"Parser source {source!r} is not supported")


def node_to_dict(node: Node, source_code: bytes) -> AstNode:
    """Convert a Tree-sitter node into a JSON-serialisable AST node."""
    return {
        "type": node.type,
        "start_byte": node.start_byte,
        "end_byte": node.end_byte,
        "start_point": {"row": node.start_point.row, "column": node.start_point.column},
        "end_point": {"row": node.end_point.row, "column": node.end_point.column},
        "text": source_code[node.start_byte : node.end_byte].decode("utf-8", errors="replace"),
        "is_named": node.is_named,
        "children": [node_to_dict(child, source_code) for child in node.children],
    }


def parse_code(code: str, language: str) -> ParseResult:
    """Parse UTF-8 source and return its AST, using a safe, shared response shape."""
    source_code = code.encode("utf-8")
    if len(source_code) > MAX_CODE_BYTES:
        return {
            "success": False,
            "error": f"Code must not exceed {MAX_CODE_BYTES:,} UTF-8 bytes",
        }
    if language not in LANGUAGE_PARSERS:
        return {"success": False, "error": f"Language {language!r} is not supported"}

    try:
        tree = get_parser(language).parse(source_code)
        return {"success": True, "ast": node_to_dict(tree.root_node, source_code)}
    except Exception:
        return {"success": False, "error": "Parsing failed"}


def available_languages() -> list[str]:
    """Return all registered language identifiers in a stable order."""
    return sorted(LANGUAGE_PARSERS)


initialize_parsers()

mcp = FastMCP(
    "Tree-sitter Playground",
    instructions="Parse source code with the installed tree-sitter-language-pack grammars.",
    host=HOST,
    port=PORT,
    streamable_http_path="/mcp",
)


@mcp.tool()
def parse_source(code: str, language: str) -> ParseResult:
    """Parse code with Tree-sitter and return the full syntax tree."""
    return parse_code(code, language)


@mcp.tool()
def list_languages() -> list[str]:
    """List grammar identifiers accepted by parse_source."""
    return available_languages()


mcp_asgi_app = mcp.streamable_http_app()
templates = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with mcp_asgi_app.router.lifespan_context(mcp_asgi_app):
        yield


app = FastAPI(title="Tree-sitter Playground", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Render the playground UI."""
    return templates.TemplateResponse(
        request,
        "index.html",
        {"languages": available_languages()},
    )


@app.post("/parse")
async def parse(request: ParseRequest) -> ParseResult:
    """Parse code for the browser client."""
    return parse_code(request.code, request.language)


@app.get("/languages")
async def languages() -> dict[str, list[str]]:
    """Expose parser identifiers to browser clients."""
    return {"languages": available_languages()}


# Mount last so the UI and REST routes retain precedence over FastMCP's /mcp route.
app.mount("/", mcp_asgi_app)


def main() -> None:
    """Run the local HTTP UI and MCP server."""
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
