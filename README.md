# Tree-sitter Playground

> **Unofficial clone:** This project is an unofficial, independently maintained clone of the
> [Tree-sitter Playground](https://tree-sitter.github.io/tree-sitter/playground/). It is not
> affiliated with or endorsed by the Tree-sitter project.

A local playground for inspecting Tree-sitter ASTs. Unlike the original Tree-sitter Playground,
this implementation runs **server-side**, so it is less suitable for fully self-contained use in
a browser. In exchange, it supports 306+ grammars through
[tree-sitter-language-pack](https://github.com/xberg-io/tree-sitter-language-pack) and is useful
for debugging custom parsers.

## Run

```bash
uv run ts-playground
```

Open <http://127.0.0.1:8765>. The language pack may download and cache a grammar locally when it
is first requested.

## Interfaces

- UI: `GET /`
- REST: `POST /parse` with JSON `{ "code": "...", "language": "python" }`
- Languages: `GET /languages`
- MCP Streamable HTTP: `http://127.0.0.1:8765/mcp`

MCP provides the `parse_source(code, language)` and `list_languages()` tools.

## Custom parsers

Add a compiled `tree_sitter.Language` to `CUSTOM_PARSERS`, then register it in
`LANGUAGE_PARSERS` with the `"custom"` source. The parser will then be available through the UI,
REST API, and MCP.
