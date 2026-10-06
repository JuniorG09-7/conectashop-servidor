# Relatório Técnico — Grupo SERVIDOR (ConectaShop / IntegraLab)

## 1. Identificação
- Equipe Servidor: **S__**  — Integrantes: ________________
- Tecnologias: Python 3 (REST com `http.server` da biblioteca padrão; gRPC com `grpcio` + `grpcio-tools`)

## 2. Arquitetura
Um único processo (`main.py`) sobe dois servidores em paralelo, ambos com bind em `0.0.0.0`:
- **REST** (`rest_server.py`): `ThreadingHTTPServer`, uma thread por requisição, roteamento manual de `/api/v1/products/{sku}` e `/api/v1/quotes`, catálogo fixo em memória, validações e erros conforme o contrato.
- **gRPC** (`grpc_server.py`): `grpc.server` com pool de threads, `ShippingService` gerado a partir do `shipping.proto` fornecido, sem alterações. Metadata `x-client-team` lida em cada RPC.
- **Logs** (`log_setup.py`): formato único para REST e gRPC (protocolo, equipe servidor, equipe cliente, request ID, operação, parâmetros, status, resultado).

## 3. Endereços usados
- REST_BASE_URL: `http://__________:8080`
- GRPC_TARGET: `__________:50051`

## 4. Clientes que testaram
| Protocolo | Cliente | Testes | Resultado inicial | Resultado final | Request IDs | Observação |
|---|---|---|---|---|---|---|
| REST | C__ | R1–R5 | | | | |
| REST | C__ | R1–R5 | | | | |
| gRPC | C__ | G1–G5 | | | | |
| gRPC | C__ | G1–G5 | | | | |

## 5. Resultados observados
| Teste | Esperado | Cliente 1 | Cliente 2 |
|---|---|---|---|
| R1 GET KB-100 | 200; unitPriceCents=25990 | | |
| R2 GET XX-999 | 404 PRODUCT_NOT_FOUND | | |
| R3 quote 2×KB-100 + 1×MS-200 | 200; 64970 / 5% / 61722 | | |
| R4 quote 1×MN-400 | 200; 119990 / 10% / 11999 / 107991 | | |
| R5 SKU inexistente | 422 INVALID_PRODUCT | | |
| G1 Health | SERVING; server_team | | |
| G2 1500g LOCAL STANDARD | 1800; 2 dias | | |
| G3 2500g REGIONAL EXPRESS | 4600; 2 dias | | |
| G4 1000g NATIONAL STANDARD | 3400; 7 dias | | |
| G5 weight=0 | INVALID_ARGUMENT / INVALID_WEIGHT | | |

Autoteste local antes do sorteio: `python tools/selftest.py` → 30 verificações OK, 0 falhas (anexar a saída e o teste feito a partir de outra máquina).

## 6. Trechos de log (mesmo Request ID, lado Servidor e lado Cliente)
```
(colar linhas de logs/server.log e, se o Cliente fornecer, a linha correspondente do log dele)
```

## 7. Falhas observadas
| Request ID | Cliente | Sintoma | Classificação (rede / contrato / regra de negócio / cliente) | Causa | Correção (sem alterar o contrato) |
|---|---|---|---|---|---|
| | | | | | |

## 8. Comparação prática REST × gRPC (visão de quem implementou os servidores)
Pontos de partida para completar com a experiência real da equipe:
- **Contrato:** no gRPC o `.proto` gera stubs e tipos; no REST a validação de JSON, tipos e erros foi escrita à mão (ver `calculate_quote`).
- **Erros:** REST usa status HTTP + corpo JSON padronizado; gRPC usa status code + descrição curta.
- **Metadados:** headers HTTP (`X-Client-Team`, `X-Request-ID`) vs. metadata gRPC (`x-client-team`, chaves em minúsculas).
- **Dependências:** REST funcionou só com a biblioteca padrão; gRPC exigiu `grpcio`, `protoc` e geração de código.
- **Depuração:** REST pode ser testado com `curl`; gRPC precisa de cliente com stubs (ou grpcurl).

## 9. Conclusão sobre interoperabilidade
(Complete com o que foi observado: clientes em linguagens diferentes receberam as mesmas respostas? Quais divergências vieram de ambiguidade do contrato e quais de ambiente/rede?)
