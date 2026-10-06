# ConectaShop — Grupo SERVIDOR (REST + gRPC)

Implementação dos dois contratos da dinâmica IntegraLab:

- **REST** — Catalog & Quote API v1 (`/api/v1`), porta padrão **8080**
- **gRPC** — `shipping.v1.ShippingService`, porta padrão **50051**

Tecnologia: **Python 3.9+**. O REST usa só a biblioteca padrão; o gRPC usa `grpcio`.
Sem banco de dados (catálogo fixo em memória), sem autenticação, sem headers/metadata extras.

## Pré-requisitos e instalação

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Os stubs (`shipping_pb2.py`, `shipping_pb2_grpc.py`) já estão em `server/`. Para regenerar a partir do `.proto`:

```bash
cd server
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. shipping.proto
```

## Iniciar os dois serviços

```bash
cd server
python main.py --team S03
```

Troque `S03` pelo código da sua equipe (ele aparece em `server_team` no gRPC e nos logs).
Ao subir, o terminal mostra os valores para informar ao professor:

```
REST_BASE_URL   : http://<IP>:8080
GRPC_TARGET     : <IP>:50051
```

### Configuração (argumento ou variável de ambiente)

| Argumento     | Variável      | Padrão               | Descrição                               |
| ------------- | ------------- | -------------------- | --------------------------------------- |
| `--team`      | `SERVER_TEAM` | `S01`                | Código da equipe Servidor               |
| `--host`      | `HOST`        | `0.0.0.0`            | Interface de bind (todas as interfaces) |
| `--rest-port` | `REST_PORT`   | `8080`               | Porta REST                              |
| `--grpc-port` | `GRPC_PORT`   | `50051`              | Porta gRPC                              |
| `--log-file`  | `LOG_FILE`    | `../logs/server.log` | Arquivo de log                          |

## Acesso pela rede do laboratório

1. O bind é `0.0.0.0`, não só localhost.
2. Libere as portas no firewall do SO:
   - Linux (ufw): `sudo ufw allow 8080/tcp && sudo ufw allow 50051/tcp`
   - Windows (PowerShell admin): `New-NetFirewallRule -DisplayName ConectaShop -Direction Inbound -Protocol TCP -LocalPort 8080,50051 -Action Allow`
3. Teste **de outra máquina** antes do sorteio:
   ```bash
   python tools/selftest.py --rest http://IP:8080 --grpc IP:50051 --team C99
   ```
   (precisa de `pip install grpcio` e da pasta `server/` ao lado para importar os stubs).

## Autoteste

Com o servidor rodando:

```bash
python tools/selftest.py
```

Cobre R1–R5, G1–G5 e casos extras (headers ausentes, JSON inválido, limites de quantidade/peso, duplicados, enums UNSPECIFIED).

## Logs

Cada chamada gera uma linha em `logs/server.log` (e no console):

```
[2026-09-08T20:00:00] protocol=REST server=S03 client=C01 requestId=req-101 operation=GET_PRODUCT input=KB-100 status=200 result=OK
[2026-09-08T20:02:10] protocol=GRPC server=S03 client=C01 requestId=req-204 operation=CalculateShipping weight=1500 zone=LOCAL mode=STANDARD status=OK priceCents=1800 estimatedDays=2
```

Chamadas com erro (inclusive header/metadata ausente) também são registradas. O `Health` do gRPC não tem `request_id` no contrato, então aparece como `requestId=-`.

## Decisões em pontos que o contrato não detalha

- Ordem de validação do `POST /quotes`: JSON/estrutura (400) → quantidade de itens 1–5 → por item: SKU existe (`INVALID_PRODUCT`), SKU duplicado e quantidade 1–10 (`INVALID_QUANTITY_OR_ITEMS`).
- `quantity` não inteira (ex.: `1.5`, `"2"`, `true`) → 422 `INVALID_QUANTITY_OR_ITEMS`; `sku`/`quantity` ausentes ou `items` ausente/não-lista → 400 `INVALID_REQUEST`.
- Rota inexistente → 404 `NOT_FOUND`; método não permitido → 405 (fora do contrato, só para não deixar sem resposta).
- Header ausente responde 400 `MISSING_REQUIRED_HEADER` antes das demais validações; se `X-Request-ID` não foi enviado, o `requestId` do corpo vai vazio.
- `x-client-team` é exigido em **todas** as RPCs gRPC, inclusive `Health`.
- Ordem de validação gRPC: metadata → `request_id` → peso → zona → modo.

## Estrutura

```
server/   main.py, rest_server.py, grpc_server.py, log_setup.py, shipping.proto, stubs gerados
tools/    selftest.py
logs/     server.log (gerado em execução)
docs/     relatorio.md (modelo do relatório final)
```
