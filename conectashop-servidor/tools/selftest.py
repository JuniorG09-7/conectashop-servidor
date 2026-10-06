"""Autoteste do servidor (R1-R5, G1-G5 + erros). Pode rodar de OUTRA máquina.

Uso:  python selftest.py --rest http://IP:8080 --grpc IP:50051 [--team C99]
Requer: pip install grpcio  (e shipping_pb2*.py ao lado, ou rode a partir de server/)
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
import grpc
import shipping_pb2 as pb
import shipping_pb2_grpc as pb_grpc

ok_count = fail_count = 0


def check(name, cond, detail=""):
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f"  [OK]   {name}")
    else:
        fail_count += 1
        print(f"  [FAIL] {name} {detail}")


def http(base, method, path, team="CTEST", rid="t-1", body=None, raw=None):
    headers = {}
    if team is not None:
        headers["X-Client-Team"] = team
    if rid is not None:
        headers["X-Request-ID"] = rid
    data = None
    if body is not None or raw is not None:
        headers["Content-Type"] = "application/json"
        data = raw if raw is not None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode()), r.headers
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode()), e.headers


def test_rest(base, team):
    print("REST", base)
    s, b, h = http(base, "GET", "/api/v1/products/KB-100", team, "R1")
    check("R1 GET KB-100", s == 200 and b["unitPriceCents"] == 25990 and b["name"] == "Teclado Mecânico"
          and h["X-Request-ID"] == "R1", (s, b))
    s, b, _ = http(base, "GET", "/api/v1/products/XX-999", team, "R2")
    check("R2 GET XX-999", s == 404 and b["code"] == "PRODUCT_NOT_FOUND" and b["requestId"] == "R2", (s, b))
    s, b, _ = http(base, "POST", "/api/v1/quotes", team, "R3",
                   {"items": [{"sku": "KB-100", "quantity": 2}, {"sku": "MS-200", "quantity": 1}]})
    check("R3 quote 2xKB+1xMS", s == 200 and b == {"requestId": "R3", "subtotalCents": 64970,
          "discountPercent": 5, "discountCents": 3248, "totalCents": 61722}, (s, b))
    s, b, _ = http(base, "POST", "/api/v1/quotes", team, "R4", {"items": [{"sku": "MN-400", "quantity": 1}]})
    check("R4 quote 1xMN-400", s == 200 and b["subtotalCents"] == 119990 and b["discountPercent"] == 10
          and b["discountCents"] == 11999 and b["totalCents"] == 107991, (s, b))
    s, b, _ = http(base, "POST", "/api/v1/quotes", team, "R5", {"items": [{"sku": "ZZ-000", "quantity": 1}]})
    check("R5 SKU inexistente", s == 422 and b["code"] == "INVALID_PRODUCT", (s, b))
    print(" extras")
    s, b, _ = http(base, "GET", "/api/v1/products/KB-100", None, "X1")
    check("sem X-Client-Team -> 400", s == 400 and b["code"] == "MISSING_REQUIRED_HEADER", (s, b))
    s, b, _ = http(base, "GET", "/api/v1/products/KB-100", team, None)
    check("sem X-Request-ID -> 400", s == 400 and b["code"] == "MISSING_REQUIRED_HEADER", (s, b))
    s, b, _ = http(base, "POST", "/api/v1/quotes", team, "E1", raw=b"{nao-json")
    check("JSON inválido -> 400", s == 400 and b["code"] == "INVALID_REQUEST", (s, b))
    s, b, _ = http(base, "POST", "/api/v1/quotes", team, "E2", {})
    check("sem items -> 400", s == 400 and b["code"] == "INVALID_REQUEST", (s, b))
    s, b, _ = http(base, "POST", "/api/v1/quotes", team, "E3", {"items": []})
    check("items vazio -> 422", s == 422 and b["code"] == "INVALID_QUANTITY_OR_ITEMS", (s, b))
    s, b, _ = http(base, "POST", "/api/v1/quotes", team, "E4", {"items": [{"sku": "KB-100", "quantity": 11}]})
    check("quantity 11 -> 422", s == 422 and b["code"] == "INVALID_QUANTITY_OR_ITEMS", (s, b))
    s, b, _ = http(base, "POST", "/api/v1/quotes", team, "E5", {"items": [{"sku": "KB-100", "quantity": 0}]})
    check("quantity 0 -> 422", s == 422 and b["code"] == "INVALID_QUANTITY_OR_ITEMS", (s, b))
    s, b, _ = http(base, "POST", "/api/v1/quotes", team, "E6",
                   {"items": [{"sku": "KB-100", "quantity": 1}, {"sku": "KB-100", "quantity": 2}]})
    check("SKU duplicado -> 422", s == 422 and b["code"] == "INVALID_QUANTITY_OR_ITEMS", (s, b))
    s, b, _ = http(base, "POST", "/api/v1/quotes", team, "E7", {"items": [
        {"sku": k, "quantity": 1} for k in ["KB-100", "MS-200", "HD-300", "MN-400", "ZZ-1", "ZZ-2"]]})
    check("6 itens -> 422", s == 422 and b["code"] == "INVALID_QUANTITY_OR_ITEMS", (s, b))
    s, b, _ = http(base, "POST", "/api/v1/quotes", team, "E8", {"items": [{"sku": "HD-300", "quantity": 2}]})
    check("sem desconto (<50000)", s == 200 and b["discountPercent"] == 0 and b["totalCents"] == 39980, (s, b))
    s, b, _ = http(base, "POST", "/api/v1/quotes", team, "E9", {"items": [{"sku": "MN-400", "quantity": 10}]})
    check("quantidade 10 válida", s == 200 and b["subtotalCents"] == 1199900, (s, b))


def call(stub, rid, w, z, m, team="CTEST"):
    md = (("x-client-team", team),) if team else ()
    return stub.CalculateShipping(pb.ShippingRequest(request_id=rid, weight_grams=w, zone=z, mode=m),
                                  metadata=md, timeout=5)


def err_of(fn):
    try:
        fn()
        return None, None
    except grpc.RpcError as e:
        return e.code(), e.details()


def test_grpc(target, team):
    print("gRPC", target)
    stub = pb_grpc.ShippingServiceStub(grpc.insecure_channel(target))
    md = (("x-client-team", team),)
    r = stub.Health(pb.HealthRequest(), metadata=md, timeout=5)
    check("G1 Health", r.status == "SERVING" and r.server_team != "", r)
    r = call(stub, "g2", 1500, pb.LOCAL, pb.STANDARD, team)
    check("G2 1500g LOCAL STANDARD", r.price_cents == 1800 and r.estimated_days == 2 and r.request_id == "g2", r)
    r = call(stub, "g3", 2500, pb.REGIONAL, pb.EXPRESS, team)
    check("G3 2500g REGIONAL EXPRESS", r.price_cents == 4600 and r.estimated_days == 2, r)
    r = call(stub, "g4", 1000, pb.NATIONAL, pb.STANDARD, team)
    check("G4 1000g NATIONAL STANDARD", r.price_cents == 3400 and r.estimated_days == 7, r)
    c, d = err_of(lambda: call(stub, "g5", 0, pb.LOCAL, pb.STANDARD, team))
    check("G5 weight=0", c == grpc.StatusCode.INVALID_ARGUMENT and d == "INVALID_WEIGHT", (c, d))
    print(" extras")
    c, d = err_of(lambda: call(stub, "e1", 100, pb.LOCAL, pb.STANDARD, None))
    check("sem metadata -> MISSING_CLIENT_TEAM", c == grpc.StatusCode.INVALID_ARGUMENT and d == "MISSING_CLIENT_TEAM", (c, d))
    c, d = err_of(lambda: call(stub, "", 100, pb.LOCAL, pb.STANDARD, team))
    check("request_id vazio", c == grpc.StatusCode.INVALID_ARGUMENT and d == "MISSING_REQUEST_ID", (c, d))
    c, d = err_of(lambda: call(stub, "e2", 30001, pb.LOCAL, pb.STANDARD, team))
    check("peso 30001", c == grpc.StatusCode.INVALID_ARGUMENT and d == "INVALID_WEIGHT", (c, d))
    c, d = err_of(lambda: call(stub, "e3", 100, pb.SHIPPING_ZONE_UNSPECIFIED, pb.STANDARD, team))
    check("zone UNSPECIFIED", c == grpc.StatusCode.INVALID_ARGUMENT and d == "INVALID_ZONE", (c, d))
    c, d = err_of(lambda: call(stub, "e4", 100, pb.LOCAL, pb.SHIPPING_MODE_UNSPECIFIED, team))
    check("mode UNSPECIFIED", c == grpc.StatusCode.INVALID_ARGUMENT and d == "INVALID_MODE", (c, d))
    c, d = err_of(lambda: stub.Health(pb.HealthRequest(), timeout=5))
    check("Health sem metadata", c == grpc.StatusCode.INVALID_ARGUMENT and d == "MISSING_CLIENT_TEAM", (c, d))
    r = call(stub, "e5", 30000, pb.NATIONAL, pb.EXPRESS, team)
    check("30000g NATIONAL EXPRESS = 4500+30*600", r.price_cents == 22500 and r.estimated_days == 3, r)
    r = call(stub, "e6", 1, pb.LOCAL, pb.EXPRESS, team)
    check("1g LOCAL EXPRESS = 1600+600", r.price_cents == 2200 and r.estimated_days == 1, r)
    r = call(stub, "e7", 1001, pb.LOCAL, pb.STANDARD, team)
    check("1001g cobra 2 kg", r.price_cents == 1800, r)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rest", default="http://127.0.0.1:8080")
    ap.add_argument("--grpc", default="127.0.0.1:50051")
    ap.add_argument("--team", default="CTEST")
    a = ap.parse_args()
    test_rest(a.rest.rstrip("/"), a.team)
    test_grpc(a.grpc, a.team)
    print(f"\nResultado: {ok_count} OK, {fail_count} FAIL")
    sys.exit(1 if fail_count else 0)
