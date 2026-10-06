"""Inicia REST e gRPC juntos. Configuração por argumentos ou variáveis de ambiente."""
import argparse
import os
import socket
import threading

from log_setup import get_logger
from rest_server import create_rest_server
from grpc_server import create_grpc_server


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    e = os.environ.get
    p = argparse.ArgumentParser(description="ConectaShop - Servidor REST + gRPC")
    p.add_argument("--team", default=e("SERVER_TEAM", "S01"), help="código da equipe Servidor (ex.: S03)")
    p.add_argument("--host", default=e("HOST", "0.0.0.0"))
    p.add_argument("--rest-port", type=int, default=int(e("REST_PORT", "8080")))
    p.add_argument("--grpc-port", type=int, default=int(e("GRPC_PORT", "50051")))
    p.add_argument("--log-file", default=e("LOG_FILE", os.path.join("..", "logs", "server.log")))
    a = p.parse_args()

    get_logger(a.log_file)
    grpc_srv = create_grpc_server(a.host, a.grpc_port, a.team)
    grpc_srv.start()
    rest_srv = create_rest_server(a.host, a.rest_port, a.team)
    threading.Thread(target=rest_srv.serve_forever, daemon=True).start()

    ip = lan_ip()
    print("=" * 60)
    print(f"Equipe Servidor : {a.team}")
    print(f"REST_BASE_URL   : http://{ip}:{a.rest_port}   (base path /api/v1)")
    print(f"GRPC_TARGET     : {ip}:{a.grpc_port}")
    print(f"Estado          : REST=UP; gRPC=UP")
    print(f"Log             : {os.path.abspath(a.log_file)}")
    print("=" * 60, flush=True)
    try:
        grpc_srv.wait_for_termination()
    except KeyboardInterrupt:
        print("\nEncerrando...")
        grpc_srv.stop(2)
        rest_srv.shutdown()


if __name__ == "__main__":
    main()
