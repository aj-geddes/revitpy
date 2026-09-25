"""
Authenticated JSON-RPC 2.0 over WebSocket.

Shared by the MCP server (:mod:`revitpy.ai.server`) and the RevitPy Live
Server (:mod:`revitpy.revit.live`). Subclasses implement
:meth:`JsonRpcWebSocketServer._handle_message`; this base provides the
server lifecycle, handshake security and frame validation.

Security model:

* When ``auth_token`` is set, the WebSocket handshake must carry
  ``Authorization: Bearer <token>`` (constant-time comparison), otherwise it
  is rejected with HTTP 401. Binding a non-loopback address without a token
  logs a loud warning.
* Handshakes carrying an ``Origin`` header that is not in
  ``allowed_origins`` are rejected with HTTP 403, so an arbitrary web page
  cannot drive a localhost server.
* Every error response carries the id of the request that caused it
  (``null`` only when it cannot be determined, e.g. parse errors).
"""

from __future__ import annotations

import asyncio
import hmac
import importlib
import ipaddress
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, ClassVar, TypeAlias

from loguru import logger

# JSON-RPC 2.0 error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

RequestId: TypeAlias = str | int | None

# (status, body, extra headers) for a rejected WebSocket handshake.
HandshakeRejection: TypeAlias = tuple[HTTPStatus, str, dict[str, str]]


@dataclass
class JsonRpcRequest:
    """A JSON-RPC 2.0 request."""

    id: RequestId = None
    method: str = ""
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class JsonRpcResponse:
    """A JSON-RPC 2.0 response (``result`` xor ``error``)."""

    id: RequestId = None
    result: Any = None
    error: dict[str, Any] | None = None

    def to_json(self) -> str:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": self.id}
        if self.error is not None:
            payload["error"] = self.error
        else:
            payload["result"] = self.result
        return json.dumps(payload, default=str)


def load_serve() -> tuple[Callable[..., Any], bool]:
    """Return ``(serve, is_new_api)`` for the installed websockets.

    Prefers the asyncio implementation (``websockets.asyncio.server``,
    websockets >= 13) and falls back to the legacy ``websockets.server``.
    """
    try:
        module = importlib.import_module("websockets.asyncio.server")
        return module.serve, True
    except ImportError:  # pragma: no cover - depends on installed version
        module = importlib.import_module("websockets.server")
        return module.serve, False


def is_loopback_host(host: str) -> bool:
    """Return ``True`` when *host* only accepts local connections."""
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def check_bearer_token(headers: Mapping[str, str], token: str) -> bool:
    """Constant-time check of an ``Authorization: Bearer <token>`` header."""
    header = headers.get("Authorization") or ""
    scheme, _, supplied = header.partition(" ")
    return scheme.lower() == "bearer" and hmac.compare_digest(
        supplied.strip().encode("utf-8"), token.encode("utf-8")
    )


class JsonRpcWebSocketServer:
    """Base class for an authenticated JSON-RPC 2.0 WebSocket server.

    Args:
        host: Bind address.
        port: Bind port (0 picks a free port; see :attr:`port`).
        auth_token: Required bearer token, or ``None`` for no auth.
        allowed_origins: Browser origins allowed to connect.
    """

    #: Name used in log messages and the ``WWW-Authenticate`` realm.
    server_name: ClassVar[str] = "json-rpc"
    request_cls: ClassVar[type] = JsonRpcRequest
    response_cls: ClassVar[type] = JsonRpcResponse

    def __init__(
        self,
        *,
        host: str,
        port: int,
        auth_token: str | None,
        allowed_origins: Iterable[str] = (),
    ) -> None:
        self._host = host
        self._port = port
        self._auth_token = auth_token
        self._allowed_origins = list(allowed_origins)
        self._connections: set[Any] = set()
        self._server: Any | None = None

    # -- properties -------------------------------------------------------

    @property
    def connections(self) -> set[Any]:
        """Active WebSocket connections."""
        return set(self._connections)

    @property
    def port(self) -> int | None:
        """The bound port while running (useful with ``port=0``)."""
        if self._server is None:
            return None
        sockets = list(self._server.sockets)
        return int(sockets[0].getsockname()[1]) if sockets else None

    @property
    def is_running(self) -> bool:
        return self._server is not None

    # -- lifecycle ----------------------------------------------------------

    def _startup_error(self, message: str, cause: OSError) -> Exception:
        """Exception raised when binding fails; subclasses may specialise."""
        return OSError(message)

    async def start(self) -> None:
        """Start listening."""
        logger.info(
            "Starting {} server on {}:{}", self.server_name, self._host, self._port
        )
        if self._auth_token is None and not is_loopback_host(self._host):
            logger.warning(
                "{} server is binding to non-loopback address {} WITHOUT "
                "authentication - anyone who can reach this port can act on the "
                "open Revit model. Configure an auth token.",
                self.server_name,
                self._host,
            )
        serve, is_new_api = load_serve()
        process_request = (
            self._process_request if is_new_api else self._legacy_process_request
        )
        try:
            self._server = await serve(
                self._handle_connection,
                self._host,
                self._port,
                process_request=process_request,
            )
        except OSError as exc:
            raise self._startup_error(f"Failed to start server: {exc}", exc) from exc
        logger.info("{} server started on port {}", self.server_name, self.port)

    async def stop(self, timeout: float = 5.0) -> None:
        """Stop the server and wait up to *timeout* seconds for it to close."""
        logger.info("Stopping {} server", self.server_name)
        if self._server is not None:
            self._server.close()
            await asyncio.wait_for(self._server.wait_closed(), timeout=timeout)
            self._server = None
        self._connections.clear()
        logger.info("{} server stopped", self.server_name)

    async def __aenter__(self) -> JsonRpcWebSocketServer:
        await self.start()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.stop()

    # -- handshake ----------------------------------------------------------

    def _check_handshake(self, headers: Mapping[str, str]) -> HandshakeRejection | None:
        """Validate handshake headers; return a rejection or ``None`` to accept."""
        origin = headers.get("Origin")
        if origin is not None and origin not in self._allowed_origins:
            logger.warning(
                "Rejected WebSocket handshake from disallowed origin {}", origin
            )
            return HTTPStatus.FORBIDDEN, "Forbidden origin\n", {}

        if self._auth_token is not None and not check_bearer_token(
            headers, self._auth_token
        ):
            logger.warning("Rejected unauthenticated WebSocket handshake")
            return (
                HTTPStatus.UNAUTHORIZED,
                "Unauthorized\n",
                {"WWW-Authenticate": f'Bearer realm="{self.server_name}"'},
            )
        return None

    def _process_request(self, connection: Any, request: Any) -> Any:
        """``process_request`` hook for the websockets asyncio server."""
        rejection = self._check_handshake(request.headers)
        if rejection is None:
            return None
        status, body, extra_headers = rejection
        response = connection.respond(status, body)
        for name, value in extra_headers.items():
            response.headers[name] = value
        return response

    async def _legacy_process_request(
        self, path: str, request_headers: Any
    ) -> tuple[HTTPStatus, list[tuple[str, str]], bytes] | None:
        """``process_request`` hook for legacy websockets (< 13)."""
        rejection = self._check_handshake(request_headers)
        if rejection is None:
            return None
        status, body, extra_headers = rejection
        return status, list(extra_headers.items()), body.encode("utf-8")

    # -- messages -----------------------------------------------------------

    def _error(self, request_id: RequestId, code: int, message: str) -> Any:
        """Build an error response correlated to *request_id*."""
        return self.response_cls(
            id=request_id, error={"code": code, "message": message}
        )

    async def _handle_connection(self, websocket: Any) -> None:
        """Serve one client connection until it closes."""
        self._connections.add(websocket)
        logger.info("Client connected; total connections = {}", len(self._connections))
        try:
            async for raw_message in websocket:
                response = await self._process_raw(raw_message)
                if response is not None:
                    await websocket.send(response.to_json())
        finally:
            self._connections.discard(websocket)
            logger.info(
                "Client disconnected; total connections = {}", len(self._connections)
            )

    async def _process_raw(self, raw: str | bytes) -> Any:
        """Parse and validate one raw frame, then dispatch it.

        Never raises. Returns ``None`` for notifications and client responses,
        which must not be answered.
        """
        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8")
            except UnicodeDecodeError:
                return self._error(None, PARSE_ERROR, "Parse error: invalid UTF-8")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return self._error(None, PARSE_ERROR, "Parse error")

        if isinstance(data, list):
            return self._error(
                None,
                INVALID_REQUEST,
                "Invalid Request: JSON-RPC batching is not supported",
            )
        if not isinstance(data, dict):
            return self._error(
                None, INVALID_REQUEST, "Invalid Request: expected a JSON object"
            )

        request_id = data.get("id")
        if request_id is not None and (
            isinstance(request_id, bool) or not isinstance(request_id, str | int)
        ):
            return self._error(
                None, INVALID_REQUEST, "Invalid Request: id must be a string or integer"
            )

        if "method" not in data:
            if "result" in data or "error" in data:
                logger.debug("Ignoring client response for id {}", request_id)
                return None
            return self._error(
                request_id, INVALID_REQUEST, "Invalid Request: missing 'method'"
            )

        if data.get("jsonrpc") != "2.0":
            return self._error(
                request_id, INVALID_REQUEST, "Invalid Request: jsonrpc must be '2.0'"
            )

        method = data["method"]
        if not isinstance(method, str):
            return self._error(
                request_id, INVALID_REQUEST, "Invalid Request: method must be a string"
            )

        if request_id is None:
            logger.debug("Received notification {}", method)
            return None

        params = data.get("params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return self._error(
                request_id, INVALID_PARAMS, "Invalid params: params must be an object"
            )

        request = self.request_cls(id=request_id, method=method, params=params)
        try:
            return await self._handle_message(request)
        except Exception as exc:
            logger.exception("Unhandled error while handling {}", method)
            return self._error(request_id, INTERNAL_ERROR, f"Internal error: {exc}")

    async def _handle_message(self, message: Any) -> Any:
        """Dispatch a validated request and return a response object."""
        raise NotImplementedError
