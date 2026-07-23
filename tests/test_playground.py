import httpx
import pytest

from treesitter_playground import MAX_CODE_BYTES, app, list_languages, parse_code, parse_source


@pytest.fixture
def transport() -> httpx.ASGITransport:
    """Exercise HTTP routes without restarting FastMCP's one-shot lifespan."""
    return httpx.ASGITransport(app=app)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_index_renders_playground(transport: httpx.ASGITransport) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "Tree-sitter Playground" in response.text


@pytest.mark.anyio
async def test_languages_endpoint_matches_service(transport: httpx.ASGITransport) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/languages")

    assert response.status_code == 200
    assert response.json()["languages"] == list_languages()
    assert "python" in response.json()["languages"]


@pytest.mark.anyio
async def test_parse_endpoint_returns_ast(transport: httpx.ASGITransport) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/parse", json={"code": "value = 1\n", "language": "python"})

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["ast"]["type"] == "module"


def test_parse_rejects_unsupported_language() -> None:
    result = parse_code("answer", "not-a-language")

    assert result == {"success": False, "error": "Language 'not-a-language' is not supported"}


def test_parse_rejects_code_larger_than_limit() -> None:
    result = parse_code("x" * (MAX_CODE_BYTES + 1), "python")

    assert result["success"] is False
    assert "must not exceed" in result["error"]


def test_mcp_tool_uses_shared_parser_service() -> None:
    assert parse_source("value = 1\n", "python") == parse_code("value = 1\n", "python")
