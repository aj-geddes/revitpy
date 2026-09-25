"""
pyRevit side of the RevitPy bridge: call RevitPy analyses from pyRevit scripts.

Put this file in a pyRevit extension's ``lib/`` folder. It talks to the RevitPy
Live Server (JSON-RPC 2.0 over WebSocket, running inside Revit in the Python
embedded by the RevitPy add-in), which it finds through the discovery file
``~/.revitpy/live.json`` (or ``REVITPY_LIVE_DISCOVERY``)::

    from pyrevit import revit
    from revitpy_bridge import RevitPyBridge, serialize_elements

    bridge = RevitPyBridge()
    print(bridge.list_analyses())
    elements = serialize_elements(revit.get_selection().elements)
    print(bridge.analyze("quantity_takeoff", elements, {"group_by": "level"}))

Runs on IronPython 2.7 (pyRevit's default engine; uses .NET ClientWebSocket)
and on CPython 3 (uses the ``websockets`` package, or .NET through pythonnet).

Units: serialized geometry and parameter values are Revit internal units:
feet, square feet, cubic feet, radians.

WARNING: a pyRevit command runs on Revit's main thread and holds it while it
waits for the reply. An analysis that the Live Server must run on Revit's main
thread cannot start until then, so the call times out. Analyses meant for the
bridge must be registered with ``register_analysis(name, main_thread=False)``.
"""

from __future__ import absolute_import, division, print_function

import io
import itertools
import json
import os
import sys
import threading

try:
    text_type = unicode  # noqa: F821 - Python 2 / IronPython
except NameError:
    text_type = str

__all__ = [
    "BridgeError",
    "LiveServerNotRunning",
    "AuthenticationFailed",
    "RpcError",
    "UnknownAnalysis",
    "AnalysisFailed",
    "RevitPyBridge",
    "discovery_path",
    "read_discovery",
    "element_id_value",
    "serialize_element",
    "serialize_elements",
]

PROTOCOL_VERSION = 1
DEFAULT_TIMEOUT = 120.0
INVALID_PARAMS = -32602

_START_HINT = (
    "Start it from the RevitPy ribbon (Live Server button) or set "
    "start_live_server = true in %APPDATA%\\RevitPy\\settings.ini."
)
_STALE_HINT = (
    "The RevitPy Live Server rejected the connection token. The discovery file "
    "may be stale (the Live Server restarted); restart it and try again."
)


# -- exceptions ---------------------------------------------------------------


class BridgeError(Exception):
    """Base class of every error raised by this module."""


class LiveServerNotRunning(BridgeError):
    """No discovery file, or nothing is listening at the URL it names."""


class AuthenticationFailed(BridgeError):
    """The WebSocket handshake was rejected (HTTP 401/403): stale token."""


class RpcError(BridgeError):
    """The Live Server answered with a JSON-RPC error."""

    def __init__(self, code, message):
        super(RpcError, self).__init__("%s (code %d)" % (message, code))
        self.code = code
        self.message = message


class UnknownAnalysis(RpcError):
    """No analysis is registered under the requested name."""


class AnalysisFailed(BridgeError):
    """The analysis raised; ``details`` holds the server-side traceback."""

    def __init__(self, analysis, details):
        super(AnalysisFailed, self).__init__(
            "Analysis '%s' failed:\n%s" % (analysis, details)
        )
        self.analysis = analysis
        self.details = details


def _not_running(url, reason):
    return LiveServerNotRunning(
        "RevitPy Live Server is not running at %s (%s). %s" % (url, reason, _START_HINT)
    )


# -- discovery ----------------------------------------------------------------


def discovery_path():
    """Path of the discovery file the Live Server writes when it starts."""
    override = os.environ.get("REVITPY_LIVE_DISCOVERY", "")
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), ".revitpy", "live.json")


def read_discovery(path=None):
    """Read the discovery file; return its dict (``url``, ``token``, ...)."""
    path = path or discovery_path()
    if not os.path.exists(path):
        raise LiveServerNotRunning(
            "RevitPy Live Server is not running (no %s). %s" % (path, _START_HINT)
        )
    try:
        with io.open(path, encoding="utf-8") as stream:
            data = json.load(stream)
    except (IOError, OSError) as exc:
        raise LiveServerNotRunning(
            "Cannot read the Live Server discovery file %s: %s" % (path, exc)
        )
    except ValueError as exc:
        raise LiveServerNotRunning(
            "Invalid Live Server discovery file %s: %s" % (path, exc)
        )
    if not isinstance(data, dict):
        raise LiveServerNotRunning("Invalid Live Server discovery file %s" % path)
    for key in ("url", "token"):
        value = data.get(key)
        if not isinstance(value, (str, text_type)) or not value:
            raise LiveServerNotRunning(
                "Live Server discovery file %s has no '%s'" % (path, key)
            )
    try:
        protocol = int(data.get("protocol", PROTOCOL_VERSION))
    except (TypeError, ValueError):
        raise LiveServerNotRunning(
            "Invalid protocol in Live Server discovery file %s" % path
        )
    if protocol != PROTOCOL_VERSION:
        raise BridgeError(
            "The Live Server speaks protocol %d; this revitpy_bridge.py supports "
            "%d. Update revitpy_bridge.py or RevitPy." % (protocol, PROTOCOL_VERSION)
        )
    return data


# -- transports: send(text), recv(timeout) -> text, close() ------------------


def _exception_text(exc):
    """Text of an exception including .NET inner exceptions.

    IronPython wraps .NET exceptions (the original is ``clsException``); the
    AggregateException thrown by ``Task.Wait()`` only says "One or more errors
    occurred", so the inner exceptions' messages are collected too.
    """
    parts = [text_type(exc)]
    current = getattr(exc, "clsException", None) or exc
    depth = 0
    while current is not None and depth < 8:
        message = getattr(current, "Message", None)
        if message and text_type(message) not in parts:
            parts.append(text_type(message))
        current = getattr(current, "InnerException", None)
        depth += 1
    return "; ".join(part for part in parts if part)


def _timed_out(timeout):
    return BridgeError(
        "Timed out after %ss waiting for the RevitPy Live Server" % timeout
    )


class _WebsocketsTransport(object):
    """CPython: the ``websockets`` package's synchronous client (>= 11)."""

    def __init__(self, connect, url, token, timeout):
        try:
            # Entered as a context manager, as websockets >= 16 requires.
            self._manager = connect(
                url,
                additional_headers={"Authorization": "Bearer " + token},
                open_timeout=min(timeout, 30),
                max_size=None,
            )
            self._ws = self._manager.__enter__()
        except Exception as exc:
            status = None
            if type(exc).__name__ in ("InvalidStatus", "InvalidStatusCode"):
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status is None:
                    status = getattr(exc, "status_code", None)
            if status in (401, 403):
                raise AuthenticationFailed(_STALE_HINT)
            if status is not None:
                raise BridgeError(
                    "The RevitPy Live Server at %s refused the connection (HTTP %s)"
                    % (url, status)
                )
            if isinstance(exc, OSError):  # refused, unreachable, open timeout
                raise _not_running(url, text_type(exc) or type(exc).__name__)
            raise BridgeError("Cannot connect to %s: %s" % (url, exc))

    def send(self, text):
        self._ws.send(text)

    def recv(self, timeout):
        try:
            return self._ws.recv(timeout=timeout)
        except Exception as exc:
            if type(exc).__name__ == "TimeoutError":  # builtin name not in Python 2
                raise _timed_out(timeout)
            raise BridgeError("Lost the connection to the Live Server: %s" % exc)

    def close(self):
        try:
            self._manager.__exit__(None, None, None)
        except Exception:
            pass


class _DotNetTransport(object):
    """IronPython / pythonnet: .NET System.Net.WebSockets.ClientWebSocket."""

    def __init__(self, url, token, timeout):
        try:
            import clr

            clr.AddReference("System")
            from System import Array, ArraySegment, Byte, TimeSpan, Uri
            from System.IO import MemoryStream
            from System.Net.WebSockets import (
                ClientWebSocket,
                WebSocketCloseStatus,
                WebSocketMessageType,
            )
            from System.Text import Encoding
            from System.Threading import CancellationTokenSource
        except Exception as exc:
            raise BridgeError("Cannot load .NET WebSocket support: %s" % exc)

        self._Array = Array
        self._Segment = ArraySegment[Byte]
        self._Byte = Byte
        self._TimeSpan = TimeSpan
        self._MemoryStream = MemoryStream
        self._CloseStatus = WebSocketCloseStatus
        self._MessageType = WebSocketMessageType
        self._Encoding = Encoding
        self._Cancel = CancellationTokenSource

        ws = ClientWebSocket()
        ws.Options.SetRequestHeader("Authorization", "Bearer " + token)
        try:
            ws.ConnectAsync(Uri(url), self._token(min(timeout, 30))).Wait()
        except Exception as exc:
            text = _exception_text(exc)
            try:
                ws.Dispose()
            except Exception:
                pass
            # e.g. "The server returned status code '401' when status code
            # '101' was expected."
            if "'401'" in text or "'403'" in text:
                raise AuthenticationFailed(_STALE_HINT)
            raise _not_running(url, text)
        self._ws = ws

    def _token(self, seconds):
        return self._Cancel(self._TimeSpan.FromSeconds(seconds)).Token

    def send(self, text):
        data = self._Encoding.UTF8.GetBytes(text)
        try:
            self._ws.SendAsync(
                self._Segment(data), self._MessageType.Text, True, self._token(30)
            ).Wait()
        except Exception as exc:
            raise BridgeError(
                "Cannot send to the Live Server: %s" % _exception_text(exc)
            )

    def recv(self, timeout):
        buffer = self._Array.CreateInstance(self._Byte, 65536)
        stream = self._MemoryStream()
        token = self._token(timeout)
        try:
            while True:
                result = self._ws.ReceiveAsync(self._Segment(buffer), token).Result
                if result.MessageType == self._MessageType.Close:
                    raise BridgeError("The RevitPy Live Server closed the connection")
                stream.Write(buffer, 0, result.Count)
                if result.EndOfMessage:
                    break
        except BridgeError:
            raise
        except Exception as exc:
            text = _exception_text(exc)
            if "cancel" in text.lower():
                raise _timed_out(timeout)
            raise BridgeError("Lost the connection to the Live Server: %s" % text)
        return self._Encoding.UTF8.GetString(stream.ToArray())

    def close(self):
        try:
            self._ws.CloseAsync(
                self._CloseStatus.NormalClosure, "", self._token(2)
            ).Wait(2000)
        except Exception:
            pass
        try:
            self._ws.Dispose()
        except Exception:
            pass


def _open_transport(url, token, timeout):
    if sys.platform == "cli":  # IronPython
        return _DotNetTransport(url, token, timeout)
    try:
        from websockets.sync.client import connect
    except ImportError:
        connect = None
    if connect is not None:
        return _WebsocketsTransport(connect, url, token, timeout)
    try:
        import clr  # noqa: F401 - pythonnet, e.g. pyRevit's CPython engine
    except ImportError:
        raise BridgeError(
            "No WebSocket client available: install the 'websockets' package (>= 11)"
        )
    return _DotNetTransport(url, token, timeout)


# -- client -------------------------------------------------------------------


class RevitPyBridge(object):
    """Client of the RevitPy Live Server's ``bridge/*`` methods.

    Every call opens its own connection and, unless ``url`` and ``token`` are
    given, re-reads the discovery file, so a restarted Live Server (new port
    or token) is picked up automatically.
    """

    def __init__(
        self, timeout=DEFAULT_TIMEOUT, discovery_file=None, url=None, token=None
    ):
        self.timeout = float(timeout)
        self._discovery_file = discovery_file
        self._url = url
        self._token = token
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def _connection(self):
        if self._url and self._token:
            return self._url, self._token
        data = read_discovery(self._discovery_file)
        return data["url"], data["token"]

    def call(self, method, params=None):
        """Make one JSON-RPC call and return its ``result``.

        Raises RpcError when the server answers with a JSON-RPC error.
        """
        url, token = self._connection()
        with self._lock:
            request_id = next(self._ids)
        request = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            }
        )
        transport = _open_transport(url, token, self.timeout)
        try:
            transport.send(request)
            while True:
                text = transport.recv(self.timeout)
                try:
                    reply = json.loads(text)
                except ValueError:
                    raise BridgeError("The Live Server sent a non-JSON reply")
                if isinstance(reply, dict) and reply.get("id") == request_id:
                    break
        finally:
            transport.close()
        error = reply.get("error")
        if error is not None:
            if not isinstance(error, dict):
                error = {"message": text_type(error)}
            raise RpcError(
                int(error.get("code", 0)), text_type(error.get("message", ""))
            )
        return reply.get("result")

    def status(self):
        """``live/status``: versions, open document and registered analyses."""
        return self.call("live/status")

    def list_analyses(self):
        """Names of the analyses registered in RevitPy, sorted."""
        result = self.call("bridge/listAnalyses") or {}
        return sorted(result.get("analyses") or [])

    def analyze(self, analysis, elements, options=None):
        """Run a RevitPy analysis on ``elements`` and return its result.

        ``elements`` may be serialized dicts or Revit elements (serialized
        here with :func:`serialize_element`).

        Raises UnknownAnalysis, AnalysisFailed, or another BridgeError.
        """
        payload = [
            element if isinstance(element, dict) else serialize_element(element)
            for element in elements
        ]
        params = {"analysis": analysis, "elements": payload, "options": options or {}}
        try:
            result = self.call("bridge/analyze", params)
        except RpcError as exc:
            if exc.code == INVALID_PARAMS and "Unknown analysis" in text_type(
                exc.message
            ):
                raise UnknownAnalysis(exc.code, exc.message)
            raise
        if not isinstance(result, dict):
            raise BridgeError("Unexpected bridge/analyze reply: %r" % (result,))
        if not result.get("success"):
            raise AnalysisFailed(analysis, result.get("error") or "unknown error")
        return result.get("result")


# -- serialization of Revit elements -----------------------------------------


def element_id_value(element_id):
    """Integer value of an ElementId (``Value`` in Revit 2024+, else ``IntegerValue``)."""
    if element_id is None:
        return None
    for attribute in ("Value", "IntegerValue"):
        try:
            value = getattr(element_id, attribute, None)
        except Exception:
            value = None
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


def _get(obj, attribute):
    """``getattr`` that also swallows exceptions raised by Revit properties."""
    try:
        return getattr(obj, attribute, None)
    except Exception:
        return None


def _text(value):
    if value is None:
        return None
    try:
        value = text_type(value)
    except Exception:
        return None
    return value or None


def _enum_name(value):
    """Name of an enum value: ``Double`` for .NET's and Python's ``StorageType.Double``."""
    text = _text(value)
    return text.rsplit(".", 1)[-1] if text else None


def _num(value):
    try:
        return round(float(value), 6)
    except Exception:
        return None


def _xyz(point):
    return [_num(point.X), _num(point.Y), _num(point.Z)]


def _named(doc, element_id):
    """Name of the element that ``element_id`` refers to, or None."""
    if element_id_value(element_id) in (None, -1):
        return None
    try:
        return _text(_get(doc.GetElement(element_id), "Name"))
    except Exception:
        return None


def _parameter(parameter):
    storage = _enum_name(_get(parameter, "StorageType"))
    if storage in (None, "None"):
        return None
    value = None
    if _get(parameter, "HasValue") is not False:
        if storage == "Double":
            value = _num(parameter.AsDouble())
        elif storage == "Integer":
            value = int(parameter.AsInteger())
        elif storage == "String":
            value = _text(parameter.AsString())
        elif storage == "ElementId":
            value = element_id_value(parameter.AsElementId())
    definition = _get(parameter, "Definition")
    builtin = _enum_name(_get(definition, "BuiltInParameter"))
    data_type = None
    try:
        data_type = _text(definition.GetDataType().TypeId)  # Revit 2022+
    except Exception:
        pass
    try:
        display = _text(parameter.AsValueString())
    except Exception:
        display = None
    return {
        "storage_type": storage,
        "value": value,
        "display": display,
        "builtin": None if builtin == "INVALID" else builtin,
        "data_type": data_type,
        "read_only": bool(_get(parameter, "IsReadOnly")),
    }


def _parameters(element):
    result = {}
    try:
        parameters = list(element.Parameters)
    except Exception:
        return result
    for parameter in parameters:
        try:
            name = _text(parameter.Definition.Name)
            if name is None or name in result:
                continue
            data = _parameter(parameter)
        except Exception:
            continue
        if data is not None:
            result[name] = data
    return result


def _location(element):
    location = _get(element, "Location")
    if location is None:
        return None
    point = _get(location, "Point")  # LocationPoint; throws for some elements
    if point is not None:
        try:
            return {"type": "point", "point": _xyz(point)}
        except Exception:
            pass
    curve = _get(location, "Curve")  # LocationCurve
    if curve is not None:
        try:
            return {
                "type": "curve",
                "start": _xyz(curve.GetEndPoint(0)),
                "end": _xyz(curve.GetEndPoint(1)),
                "length": _num(curve.Length),
            }
        except Exception:
            pass
    return None


def _bounding_box(element):
    try:
        box = element.get_BoundingBox(None)
        if box is None:
            return None
        return {"min": _xyz(box.Min), "max": _xyz(box.Max)}
    except Exception:
        return None


def _materials(element, doc):
    result = []
    try:
        material_ids = list(element.GetMaterialIds(False))
    except Exception:
        return result
    for material_id in material_ids:
        try:
            material = doc.GetElement(material_id)
            result.append(
                {
                    "id": element_id_value(material_id),
                    "name": _text(_get(material, "Name")),
                    "material_class": _text(_get(material, "MaterialClass")),
                    "volume": _num(element.GetMaterialVolume(material_id)),
                    "area": _num(element.GetMaterialArea(material_id, False)),
                }
            )
        except Exception:
            continue
    return result


def serialize_element(
    element, include_parameters=True, include_materials=True, include_geometry=True
):
    """Serialize a Revit element to a JSON-safe dict (Revit internal units, feet).

    Keys: id, unique_id, name, category, type_name, level, units, and when
    requested parameters, location, bounding_box, materials. A property that
    throws leaves its key None (or empty) instead of failing the element.
    """
    doc = _get(element, "Document")
    type_id = None
    try:
        type_id = element.GetTypeId()
    except Exception:
        pass
    data = {
        "id": element_id_value(_get(element, "Id")),
        "unique_id": _text(_get(element, "UniqueId")),
        "name": _text(_get(element, "Name")),
        "category": _text(_get(_get(element, "Category"), "Name")),
        "type_name": _named(doc, type_id),
        "level": _named(doc, _get(element, "LevelId")),
        "units": "ft",
    }
    if include_parameters:
        data["parameters"] = _parameters(element)
    if include_geometry:
        data["location"] = _location(element)
        data["bounding_box"] = _bounding_box(element)
    if include_materials:
        data["materials"] = _materials(element, doc)
    return data


def serialize_elements(
    elements, include_parameters=True, include_materials=True, include_geometry=True
):
    """Serialize several Revit elements; see :func:`serialize_element`."""
    return [
        serialize_element(
            element,
            include_parameters=include_parameters,
            include_materials=include_materials,
            include_geometry=include_geometry,
        )
        for element in elements
    ]
