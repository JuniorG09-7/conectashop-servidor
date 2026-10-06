"""Logging compartilhado: console + arquivo logs/server.log, no formato do guia."""
import logging
import os
import threading
from datetime import datetime

_lock = threading.Lock()
_logger = None


def get_logger(log_file: str):
    global _logger
    if _logger is not None:
        return _logger
    os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
    lg = logging.getLogger("conectashop")
    lg.setLevel(logging.INFO)
    lg.propagate = False
    fmt = logging.Formatter("%(message)s")
    for h in (logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")):
        h.setFormatter(fmt)
        lg.addHandler(h)
    _logger = lg
    return lg


def log_call(protocol: str, server: str, client, request_id, operation: str, **fields):
    """[2026-09-08T20:00:00] protocol=REST server=S03 client=C01 requestId=... operation=... k=v ..."""
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    parts = [
        f"[{ts}]",
        f"protocol={protocol}",
        f"server={server}",
        f"client={client or '-'}",
        f"requestId={request_id or '-'}",
        f"operation={operation}",
    ]
    parts += [f"{k}={v}" for k, v in fields.items()]
    with _lock:
        if _logger:
            _logger.info(" ".join(parts))
