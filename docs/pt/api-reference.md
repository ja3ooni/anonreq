> translated from en/api-reference.md

# Referência da API

A especificação OpenAPI completa está disponível em `docs/openapi.json` (gerada automaticamente a partir do aplicativo FastAPI). Esta página fornece um resumo dos endpoints disponíveis.

## Endpoints

| Método | Caminho | Descrição |
|--------|---------|-----------|
| POST | `/v1/chat/completions` | Envia uma requisição de chat completion (compatível com a OpenAI) |
| GET | `/health` | Teste de integridade agregado para todas as dependências |
| GET | `/v1/models` | Lista aliases de modelos configurados |
| GET | `/v1/compliance/presets` | Lista presets de conformidade disponíveis |
| GET | `/v1/config/rules` | Lista regras de detecção personalizadas ativas |
| GET | `/metrics` | Endpoint de métricas do Prometheus |

### POST /v1/chat/completions

Aceita um corpo de requisição compatível com a OpenAI. Suporta tanto o modo de streaming (`stream: true`) quanto o de não-streaming. Consulte a especificação OpenAPI para ver o esquema completo.

### GET /health

Retorna o status de saúde agregado do gateway e suas dependências (Presidio Analyzer, Valkey). Resposta:

```json
{"status":"pass","checks":{"presidio":"pass","valkey":"pass"}}
```

### GET /v1/models

Retorna a lista de aliases de modelos configurados e seus provedores de destino.

### GET /v1/compliance/presets

Retorna os presets de conformidade disponíveis com os tipos de entidades exigidos e limites de confiança.

### GET /v1/config/rules

Retorna as regras de detecção personalizadas ativas (reconhecedores e listas de exclusão).

### GET /metrics

Retorna métricas formatadas para o Prometheus, incluindo contagem de requisições, latência de detecção, contagem de entidades e contadores de eventos seguros (fail-secure).

## Autenticação

Todos os endpoints da API (exceto `/health` e `/metrics`) requerem um Bearer token no cabeçalho `Authorization`:

```bash
Authorization: Bearer <sua-chave-api-anonreq>
```

A chave de API é configurada por meio da variável de ambiente `ANONREQ_API_KEY`.

---
*Este documento é uma tradução do original em inglês. Em caso de divergência, a versão em inglês prevalece.*
