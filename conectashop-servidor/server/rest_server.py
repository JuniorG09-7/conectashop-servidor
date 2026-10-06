"""Servidor REST - Catalog & Quote API v1 (somente biblioteca padrão)."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from log_setup import log_call

BASE = "/api/v1"
CATALOG = {
    "KB-100": {"sku": "KB-100", "name": "Teclado Mecânico", "unitPriceCents": 25990, "available": True},
    "MS-200": {"sku": "MS-200", "name": "Mouse Sem Fio", "unitPriceCents": 12990, "available": True},
    "HD-300": {"sku": "HD-300", "name": "Headset USB", "unitPriceCents": 19990, "available": True},
    "MN-400": {"sku": "MN-400", "name": "Monitor 27", "unitPriceCents": 119990, "available": True},
}


class ApiError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def calculate_quote(body):
    if not isinstance(body, dict) or not isinstance(body.get("items"), list):
        raise ApiError(400, "INVALID_REQUEST", "Field 'items' is required and must be an array")
    items = body["items"]
    for it in items:
        if not isinstance(it, dict) or "sku" not in it or "quantity" not in it:
            raise ApiError(400, "INVALID_REQUEST", "Each item requires 'sku' and 'quantity'")
        if not isinstance(it["sku"], str):
            raise ApiError(400, "INVALID_REQUEST", "'sku' must be a string")
    if not 1 <= len(items) <= 5:
        raise ApiError(422, "INVALID_QUANTITY_OR_ITEMS", "items must contain between 1 and 5 items")
    seen = set()
    subtotal = 0
    for it in items:
        sku, qty = it["sku"], it["quantity"]
        if sku not in CATALOG:
            raise ApiError(422, "INVALID_PRODUCT", f"Unknown SKU: {sku}")
        if sku in seen:
            raise ApiError(422, "INVALID_QUANTITY_OR_ITEMS", f"Duplicate SKU: {sku}")
        seen.add(sku)
        if isinstance(qty, bool) or not isinstance(qty, int) or not 1 <= qty <= 10:
            raise ApiError(422, "INVALID_QUANTITY_OR_ITEMS", "quantity must be an integer between 1 and 10")
        subtotal += CATALOG[sku]["unitPriceCents"] * qty
    pct = 0 if subtotal < 50000 else (5 if subtotal < 100000 else 10)
    discount = subtotal * pct // 100
    return {"subtotalCents": subtotal, "discountPercent": pct,
            "discountCents": discount, "totalCents": subtotal - discount}


def make_handler(server_team):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "ConectaShop/1.0"

        def log_message(self, *a):  # silencia o log padrão; usamos o nosso
            pass

        def _send(self, status, payload, request_id=None):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            if request_id:
                self.send_header("X-Request-ID", request_id)
            self.end_headers()
            self.wfile.write(data)

        def _handle(self, method):
            client = (self.headers.get("X-Client-Team") or "").strip()
            rid = (self.headers.get("X-Request-ID") or "").strip()
            path = self.path.split("?", 1)[0].rstrip("/")
            operation, inp, status, result = "UNKNOWN", "-", 500, "INTERNAL_ERROR"
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length > 0 else b""
                if method == "GET" and path.startswith(BASE + "/products/"):
                    operation = "GET_PRODUCT"
                    sku = path[len(BASE + "/products/"):]
                    inp = sku
                elif method == "POST" and path == BASE + "/quotes":
                    operation = "POST_QUOTE"
                    inp = "-"
                else:
                    known = path.startswith(BASE + "/products/") or path == BASE + "/quotes"
                    if known:
                        raise ApiError(405, "METHOD_NOT_ALLOWED", "Method not allowed")
                    raise ApiError(404, "NOT_FOUND", "Resource not found")

                if not client or not rid:
                    raise ApiError(400, "MISSING_REQUIRED_HEADER",
                                   "Headers X-Client-Team and X-Request-ID are required")

                if operation == "GET_PRODUCT":
                    prod = CATALOG.get(sku)
                    if prod is None:
                        raise ApiError(404, "PRODUCT_NOT_FOUND", "Product not found")
                    status, result = 200, "OK"
                    self._send(200, prod, rid)
                else:
                    try:
                        body = json.loads(raw.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        raise ApiError(400, "INVALID_REQUEST", "Invalid JSON body")
                    inp = json.dumps(body.get("items") if isinstance(body, dict) else body,
                                     ensure_ascii=False, separators=(",", ":"))
                    q = calculate_quote(body)
                    status, result = 200, f"OK total={q['totalCents']}"
                    self._send(200, {"requestId": rid, **q}, rid)
            except ApiError as e:
                status, result = e.status, e.code
                self._send(e.status, {"code": e.code, "message": e.message, "requestId": rid}, rid or None)
            except Exception as e:  # erro inesperado
                status, result = 500, f"INTERNAL_ERROR ({type(e).__name__})"
                try:
                    self._send(500, {"code": "INTERNAL_ERROR", "message": "Internal server error",
                                     "requestId": rid}, rid or None)
                except Exception:
                    pass
            finally:
                log_call("REST", server_team, client, rid, operation, input=inp,
                         status=status, result=result)

        def do_GET(self): self._handle("GET")
        def do_POST(self): self._handle("POST")
        def do_PUT(self): self._handle("PUT")
        def do_DELETE(self): self._handle("DELETE")
        def do_PATCH(self): self._handle("PATCH")

    return Handler


def create_rest_server(host, port, server_team):
    ThreadingHTTPServer.daemon_threads = True
    return ThreadingHTTPServer((host, port), make_handler(server_team))
