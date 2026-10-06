"""Servidor gRPC - shipping.v1.ShippingService."""
from concurrent import futures

import grpc

import shipping_pb2 as pb
import shipping_pb2_grpc as pb_grpc
from log_setup import log_call

BASE_FEE = {
    pb.LOCAL: {pb.STANDARD: 1000, pb.EXPRESS: 1600},
    pb.REGIONAL: {pb.STANDARD: 1800, pb.EXPRESS: 2800},
    pb.NATIONAL: {pb.STANDARD: 3000, pb.EXPRESS: 4500},
}
PER_KG = {pb.STANDARD: 400, pb.EXPRESS: 600}
DAYS = {
    pb.LOCAL: {pb.STANDARD: 2, pb.EXPRESS: 1},
    pb.REGIONAL: {pb.STANDARD: 4, pb.EXPRESS: 2},
    pb.NATIONAL: {pb.STANDARD: 7, pb.EXPRESS: 3},
}


def compute(weight_grams, zone, mode):
    kg = (weight_grams + 999) // 1000  # teto(weight/1000)
    return BASE_FEE[zone][mode] + kg * PER_KG[mode], DAYS[zone][mode]


class ShippingService(pb_grpc.ShippingServiceServicer):
    def __init__(self, server_team):
        self.team = server_team

    @staticmethod
    def _client(context):
        for k, v in context.invocation_metadata():
            if k.lower() == "x-client-team" and v.strip():
                return v.strip()
        return None

    def Health(self, request, context):
        client = self._client(context)
        if not client:
            log_call("GRPC", self.team, None, None, "Health", status="INVALID_ARGUMENT",
                     result="MISSING_CLIENT_TEAM")
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "MISSING_CLIENT_TEAM")
        log_call("GRPC", self.team, client, None, "Health", status="OK", result="SERVING")
        return pb.HealthResponse(status="SERVING", server_team=self.team)

    def CalculateShipping(self, request, context):
        client = self._client(context)
        rid = request.request_id
        args = dict(weight=request.weight_grams, zone=pb.ShippingZone.Name(request.zone),
                    mode=pb.ShippingMode.Name(request.mode))

        # 1) validação (sem abort dentro de try, para não confundir com erro inesperado)
        if not client:
            err = "MISSING_CLIENT_TEAM"
        elif not rid:
            err = "MISSING_REQUEST_ID"
        elif not 1 <= request.weight_grams <= 30000:
            err = "INVALID_WEIGHT"
        elif request.zone not in BASE_FEE:
            err = "INVALID_ZONE"
        elif request.mode not in PER_KG:
            err = "INVALID_MODE"
        else:
            err = None
        if err:
            log_call("GRPC", self.team, client, rid, "CalculateShipping", **args,
                     status="INVALID_ARGUMENT", result=err)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, err)

        # 2) cálculo
        try:
            price, days = compute(request.weight_grams, request.zone, request.mode)
        except Exception as e:
            log_call("GRPC", self.team, client, rid, "CalculateShipping", **args,
                     status="INTERNAL", result=f"INTERNAL_ERROR ({type(e).__name__})")
            context.abort(grpc.StatusCode.INTERNAL, "INTERNAL_ERROR")
        log_call("GRPC", self.team, client, rid, "CalculateShipping", **args,
                 status="OK", priceCents=price, estimatedDays=days)
        return pb.ShippingResponse(request_id=rid, price_cents=price,
                                   estimated_days=days, server_team=self.team)


def create_grpc_server(host, port, server_team):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=16))
    pb_grpc.add_ShippingServiceServicer_to_server(ShippingService(server_team), server)
    bound = server.add_insecure_port(f"{host}:{port}")
    if bound == 0:
        raise RuntimeError(f"Não foi possível abrir {host}:{port}")
    return server
