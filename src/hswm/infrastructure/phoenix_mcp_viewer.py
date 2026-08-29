"""Provision and serve the least-privilege Phoenix MCP projection for Codex.

The durable credential is stored outside the repository with mode ``0600``.
The stdio proxy reads it directly, so neither the Codex configuration nor a
process argument contains the bearer token.  Phoenix VIEWER authorization is
the authority boundary; Codex's tool allowlist is a second, client-side bound.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from hashlib import sha256
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import time
from typing import Any, Literal, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import (
    HTTPCookieProcessor,
    OpenerDirector,
    Request,
    build_opener,
    urlopen,
)


CREDENTIAL_SCHEMA = "hswm-phoenix-mcp-viewer-credential/v1"
STATUS_SCHEMA = "hswm-phoenix-mcp-viewer-status/v1"
CLAIM_BOUNDARY = (
    "read-only observability projection; not HSWM cognition, canonical "
    "admission, causal credit, continuous learning, or efficacy evidence"
)
DEFAULT_BASE_URL = "http://127.0.0.1:6006"
DEFAULT_STATE_ROOT = Path.home() / ".local/state/hswm-research-fabric"
DEFAULT_CREDENTIAL_PATH = DEFAULT_STATE_ROOT / "secrets/phoenix-mcp-viewer.json"
DEFAULT_ADMIN_SECRET_PATH = DEFAULT_STATE_ROOT / "secrets/phoenix.json"
VIEWER_EMAIL = "hswm-phoenix-mcp-viewer@localhost.invalid"
VIEWER_USERNAME = "hswm_phoenix_mcp_viewer"
API_KEY_NAME = "HSWM Codex Phoenix viewer MCP"
FAST_MCP_VERSION = "3.4.7"
EXPOSED_TOOL_NAMES = frozenset(
    {"describeSqlSchema", "executeSql", "getProjects", "getProject"}
)
DetailLevel = Literal["brief", "detailed", "full"]


class PhoenixRequestError(RuntimeError):
    def __init__(self, method: str, path: str, status: int) -> None:
        super().__init__(f"Phoenix {method} {path} returned HTTP {status}")
        self.status = status


@dataclass(frozen=True)
class ViewerStatus:
    role: str
    username: str
    email: str
    read_probe_status: int
    mutation_probe_status: int
    credential_path: str
    credential_mode: str
    api_key_fingerprint: str


def _assert_loopback_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1":
        raise RuntimeError("Phoenix MCP provisioning is restricted to 127.0.0.1 HTTP")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError("Phoenix base URL must not contain credentials or parameters")
    return base_url.rstrip("/") + "/"


def _assert_secret_file(path: Path) -> None:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
        raise RuntimeError(f"unsafe secret file identity: {path}")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise RuntimeError(f"secret file must have mode 0600: {path}")


def _read_secret_json(path: Path) -> dict[str, Any]:
    _assert_secret_file(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RuntimeError(f"invalid secret JSON: {path}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"secret JSON must be an object: {path}")
    return value


def _write_secret_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.new")
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    descriptor = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    bearer_token: str | None = None,
    payload: Mapping[str, Any] | None = None,
    opener: OpenerDirector | None = None,
    expected: tuple[int, ...] = (200,),
) -> tuple[int, Any]:
    headers = {"Accept": "application/json", "User-Agent": "hswm-phoenix-mcp/1"}
    body = None
    if bearer_token is not None:
        headers["Authorization"] = f"Bearer {bearer_token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(
        urljoin(base_url, path.lstrip("/")),
        data=body,
        headers=headers,
        method=method,
    )
    try:
        response = (opener.open if opener is not None else urlopen)(request, timeout=15)
        with response:
            status = response.status
            raw = response.read()
    except HTTPError as error:
        status = error.code
        raw = error.read()
    except URLError as error:
        reason_type = type(error.reason).__name__
        raise RuntimeError(
            f"Phoenix request transport failed: {reason_type}"
        ) from error
    if status not in expected:
        raise PhoenixRequestError(method, path, status)
    if not raw:
        return status, None
    try:
        return status, json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        if status >= 400:
            return status, None
        raise RuntimeError(f"Phoenix {method} {path} returned non-JSON") from error


def _admin_secret(path: Path) -> str:
    value = _read_secret_json(path)
    secret = value.get("phoenix_admin_secret")
    if not isinstance(secret, str) or len(secret) < 32:
        raise RuntimeError(f"invalid Phoenix admin secret: {path}")
    return secret


def _new_pending_credential() -> dict[str, Any]:
    return {
        "schema": CREDENTIAL_SCHEMA,
        "claim_boundary": CLAIM_BOUNDARY,
        "email": VIEWER_EMAIL,
        "username": VIEWER_USERNAME,
        "role": "VIEWER",
        "password": secrets.token_urlsafe(48),
        "api_key_name": API_KEY_NAME,
        "api_key": None,
        "api_key_id": None,
        "created_unix_ns": time.time_ns(),
    }


def _load_or_create_pending(path: Path) -> dict[str, Any]:
    try:
        value = _read_secret_json(path)
    except FileNotFoundError:
        value = _new_pending_credential()
        _write_secret_json(path, value)
    if value.get("schema") != CREDENTIAL_SCHEMA:
        raise RuntimeError(f"invalid Phoenix viewer credential schema: {path}")
    for name, expected in (
        ("email", VIEWER_EMAIL),
        ("username", VIEWER_USERNAME),
        ("role", "VIEWER"),
        ("api_key_name", API_KEY_NAME),
    ):
        if value.get(name) != expected:
            raise RuntimeError(f"Phoenix viewer credential {name} drift: {path}")
    password = value.get("password")
    if not isinstance(password, str) or len(password) < 32:
        raise RuntimeError(f"invalid Phoenix viewer password: {path}")
    return value


def _find_viewer(users_body: Any) -> dict[str, Any] | None:
    if not isinstance(users_body, dict) or not isinstance(users_body.get("data"), list):
        raise RuntimeError("unexpected Phoenix users response")
    matches = [
        item
        for item in users_body["data"]
        if isinstance(item, dict)
        and (item.get("email") == VIEWER_EMAIL or item.get("username") == VIEWER_USERNAME)
    ]
    if len(matches) > 1:
        raise RuntimeError("ambiguous Phoenix viewer identity")
    return matches[0] if matches else None


def _validate_viewer_identity(user: Mapping[str, Any]) -> None:
    expected = {
        "email": VIEWER_EMAIL,
        "username": VIEWER_USERNAME,
        "role": "VIEWER",
        "auth_method": "LOCAL",
    }
    if any(user.get(name) != value for name, value in expected.items()):
        raise RuntimeError("existing Phoenix MCP identity is not the dedicated local VIEWER")


def provision(
    *,
    base_url: str = DEFAULT_BASE_URL,
    credential_path: Path = DEFAULT_CREDENTIAL_PATH,
    admin_secret_path: Path = DEFAULT_ADMIN_SECRET_PATH,
) -> ViewerStatus:
    base_url = _assert_loopback_base_url(base_url)
    credential = _load_or_create_pending(credential_path)
    admin_secret = _admin_secret(admin_secret_path)

    _, users_body = _request_json(
        base_url, "/v1/users", bearer_token=admin_secret
    )
    viewer = _find_viewer(users_body)
    if viewer is None:
        _, created = _request_json(
            base_url,
            "/v1/users",
            method="POST",
            bearer_token=admin_secret,
            payload={
                "user": {
                    "email": VIEWER_EMAIL,
                    "username": VIEWER_USERNAME,
                    "role": "VIEWER",
                    "auth_method": "LOCAL",
                    "password": credential["password"],
                },
                "send_welcome_email": False,
            },
            expected=(201,),
        )
        if not isinstance(created, dict) or not isinstance(created.get("data"), dict):
            raise RuntimeError("unexpected Phoenix create-user response")
        viewer = created["data"]
    _validate_viewer_identity(viewer)

    api_key = credential.get("api_key")
    if not isinstance(api_key, str) or len(api_key) < 32:
        cookie_jar = http.cookiejar.CookieJar()
        opener = build_opener(HTTPCookieProcessor(cookie_jar))
        _request_json(
            base_url,
            "/auth/login",
            method="POST",
            payload={"email": VIEWER_EMAIL, "password": credential["password"]},
            opener=opener,
            expected=(200, 204),
        )
        _, key_body = _request_json(
            base_url,
            "/v1/user/api_keys",
            method="POST",
            payload={
                "data": {
                    "name": API_KEY_NAME,
                    "description": (
                        "Read-only Phoenix MCP projection for HSWM Codex research"
                    ),
                }
            },
            opener=opener,
            expected=(201,),
        )
        data = key_body.get("data") if isinstance(key_body, dict) else None
        if not isinstance(data, dict):
            raise RuntimeError("unexpected Phoenix create-key response")
        api_key = data.get("key")
        api_key_id = data.get("id")
        if not isinstance(api_key, str) or len(api_key) < 32:
            raise RuntimeError("Phoenix did not return a usable viewer API key")
        credential["api_key"] = api_key
        credential["api_key_id"] = api_key_id
        _write_secret_json(credential_path, credential)
    return validate(
        base_url=base_url,
        credential_path=credential_path,
    )


def validate(
    *,
    base_url: str = DEFAULT_BASE_URL,
    credential_path: Path = DEFAULT_CREDENTIAL_PATH,
) -> ViewerStatus:
    base_url = _assert_loopback_base_url(base_url)
    credential = _read_secret_json(credential_path)
    if credential.get("schema") != CREDENTIAL_SCHEMA:
        raise RuntimeError(f"invalid Phoenix viewer credential schema: {credential_path}")
    api_key = credential.get("api_key")
    if not isinstance(api_key, str) or len(api_key) < 32:
        raise RuntimeError("Phoenix viewer API key has not been provisioned")
    read_status, body = _request_json(
        base_url, "/v1/user", bearer_token=api_key
    )
    user = body.get("data") if isinstance(body, dict) else None
    if not isinstance(user, dict):
        raise RuntimeError("unexpected Phoenix viewer response")
    _validate_viewer_identity(user)
    mutation_status, _ = _request_json(
        base_url,
        "/v1/users",
        method="POST",
        bearer_token=api_key,
        payload={},
        expected=(403,),
    )
    _assert_secret_file(credential_path)
    return ViewerStatus(
        role="VIEWER",
        username=VIEWER_USERNAME,
        email=VIEWER_EMAIL,
        read_probe_status=read_status,
        mutation_probe_status=mutation_status,
        credential_path=str(credential_path),
        credential_mode="0600",
        api_key_fingerprint=sha256(api_key.encode("utf-8")).hexdigest()[:16],
    )


def _load_api_key(path: Path) -> str:
    value = _read_secret_json(path)
    if value.get("schema") != CREDENTIAL_SCHEMA:
        raise RuntimeError(f"invalid Phoenix viewer credential schema: {path}")
    api_key = value.get("api_key")
    if not isinstance(api_key, str) or len(api_key) < 32:
        raise RuntimeError("Phoenix viewer API key has not been provisioned")
    return api_key


def _build_read_only_server(base_url: str, credential_path: Path) -> Any:
    """Build an explicit four-tool server; never proxy the upstream catalog."""

    from importlib.metadata import version

    observed = version("fastmcp-slim")
    if observed != FAST_MCP_VERSION:
        raise RuntimeError(
            f"FastMCP version drift: expected {FAST_MCP_VERSION}, observed {observed}"
        )
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport
    from fastmcp.exceptions import ToolError
    from fastmcp.server import FastMCP
    from mcp.types import ToolAnnotations

    mcp_url = urljoin(_assert_loopback_base_url(base_url), "mcp")
    api_key = _load_api_key(credential_path)
    server = FastMCP(
        "HSWM Phoenix viewer projection",
        instructions=(
            "Bounded read-only Phoenix observability projection. Results are not "
            "HSWM cognition, causal credit, canonical admission, or learning."
        ),
    )
    read_only = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    async def forward(name: str, arguments: Mapping[str, Any]) -> Any:
        if name not in EXPOSED_TOOL_NAMES:
            raise ToolError("tool is outside the Phoenix read-only projection")
        transport = StreamableHttpTransport(mcp_url, auth=api_key)
        async with Client(transport) as client:
            result = await client.call_tool(name, dict(arguments))
        if result.is_error:
            raise ToolError(f"upstream Phoenix read tool failed: {name}")
        if result.structured_content is not None:
            return result.structured_content
        text_blocks = [
            block.text
            for block in result.content
            if getattr(block, "type", None) == "text"
        ]
        if len(text_blocks) == 1:
            return text_blocks[0]
        return text_blocks

    @server.tool(name="describeSqlSchema", annotations=read_only)
    async def describe_sql_schema(
        area: str | None = None,
        tables: list[str] | None = None,
        detail: DetailLevel = "brief",
        search: str | None = None,
    ) -> Any:
        """Describe the allowlisted, read-only Phoenix analytics SQL schema."""

        return await forward(
            "describeSqlSchema",
            {
                "area": area,
                "tables": tables,
                "detail": detail,
                "search": search,
            },
        )

    @server.tool(name="executeSql", annotations=read_only)
    async def execute_sql(
        sql: str,
        validate_only: bool = False,
        row_limit: int | None = None,
    ) -> Any:
        """Execute Phoenix's bounded, read-only analytics SELECT surface."""

        return await forward(
            "executeSql",
            {
                "sql": sql,
                "validate_only": validate_only,
                "row_limit": row_limit,
            },
        )

    @server.tool(name="getProjects", annotations=read_only)
    async def get_projects(
        cursor: str | None = None,
        include_dataset_evaluator_projects: bool = False,
        include_experiment_projects: bool = False,
        limit: int = 100,
        name_contains: str | None = None,
    ) -> Any:
        """List Phoenix projects through the authenticated VIEWER principal."""

        return await forward(
            "getProjects",
            {
                "cursor": cursor,
                "include_dataset_evaluator_projects": (
                    include_dataset_evaluator_projects
                ),
                "include_experiment_projects": include_experiment_projects,
                "limit": limit,
                "name_contains": name_contains,
            },
        )

    @server.tool(name="getProject", annotations=read_only)
    async def get_project(project_identifier: str) -> Any:
        """Read one Phoenix project by ID or name."""

        return await forward(
            "getProject", {"project_identifier": project_identifier}
        )

    return server


async def _list_tools(base_url: str, credential_path: Path) -> list[dict[str, Any]]:
    server = _build_read_only_server(base_url, credential_path)
    tools = await server.list_tools()
    return [
        {
            "name": tool.name,
            "read_only": bool(
                tool.annotations is not None and tool.annotations.readOnlyHint
            ),
        }
        for tool in tools
    ]


def serve_proxy(base_url: str, credential_path: Path) -> None:
    server = _build_read_only_server(base_url, credential_path)
    server.run(transport="stdio", show_banner=False, log_level="ERROR")


def _safe_status(value: ViewerStatus) -> dict[str, Any]:
    return {
        "schema": STATUS_SCHEMA,
        "claim_boundary": CLAIM_BOUNDARY,
        "status": "PASS",
        **value.__dict__,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operate the dedicated Phoenix VIEWER MCP projection."
    )
    parser.add_argument(
        "command", choices=("provision", "validate", "list-tools", "serve")
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--credential-path", type=Path, default=DEFAULT_CREDENTIAL_PATH
    )
    parser.add_argument(
        "--admin-secret-path", type=Path, default=DEFAULT_ADMIN_SECRET_PATH
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            serve_proxy(args.base_url, args.credential_path)
            return 0
        if args.command == "provision":
            result: Any = _safe_status(
                provision(
                    base_url=args.base_url,
                    credential_path=args.credential_path,
                    admin_secret_path=args.admin_secret_path,
                )
            )
        elif args.command == "validate":
            result = _safe_status(
                validate(
                    base_url=args.base_url,
                    credential_path=args.credential_path,
                )
            )
        else:
            result = {
                "schema": STATUS_SCHEMA,
                "claim_boundary": CLAIM_BOUNDARY,
                "status": "PASS",
                "tools": asyncio.run(
                    _list_tools(args.base_url, args.credential_path)
                ),
            }
    except (OSError, RuntimeError, ValueError) as error:
        print(
            json.dumps(
                {
                    "schema": STATUS_SCHEMA,
                    "claim_boundary": CLAIM_BOUNDARY,
                    "status": "FAIL",
                    "error": f"{type(error).__name__}: {error}",
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            ),
            file=sys.stderr if args.command == "serve" else sys.stdout,
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
