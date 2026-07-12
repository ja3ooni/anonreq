> translated from en/installation.md

# Instalação

## Pré-requisitos

- Python 3.12+
- Docker Engine 24+ com Docker Compose v2+
- Mínimo 4 GB de RAM (8 GB recomendados)

## Clonar o repositório

```bash
git clone https://github.com/anonreq/anonreq.git
cd anonreq
```

## Configuração do ambiente

Copie o arquivo de ambiente de exemplo e configure as variáveis necessárias:

```bash
cp .env.example .env
```

| Variável | Obrigatória | Padrão | Descrição |
|----------|-------------|--------|-----------|
| `ANONREQ_API_KEY` | Sim | — | Token estático para autenticação da API (≥ 32 caracteres) |
| `ANONREQ_LOG_LEVEL` | Não | `INFO` | Nível de log |
| `ANONREQ_CACHE_TTL` | Não | `600` | TTL do cache de sessão em segundos |
| `ANONREQ_PRESIDIO_URL` | Não | `http://presidio-analyzer:5001` | URL do Presidio Analyzer |
| `ANONREQ_VALKEY_URL` | Não | `valkey://localhost:6379` | String de conexão do Valkey |

Pelo menos uma chave de API de provedor (`ANONREQ_OPENAI_API_KEY`, `ANONREQ_ANTHROPIC_API_KEY` ou `ANONREQ_GEMINI_API_KEY`) deve estar configurada.

## Configuração do Docker Compose

```bash
docker compose up -d --wait
```

Isso inicia os três serviços: `anonreq` (gateway), `presidio-analyzer` (detecção de PII) e `valkey` (cache efêmero).

## Verificar instalação

```bash
curl http://localhost:8000/health
```

Resposta esperada: HTTP 200 com `{"status":"pass","checks":{"presidio":"pass","valkey":"pass"}}`.

## Solução de problemas

| Problema | Causa provável | Solução |
|----------|----------------|---------|
| O teste de saúde retorna 503 | O modelo Presidio ainda está carregando | Aguarde 60 segundos para o download do modelo e tente novamente |
| `docker compose up` falha | A porta 8000 está em uso | Pare outros serviços ou altere o mapeamento de portas |
| `curl: connection refused` | O gateway não está pronto | Execute `docker compose ps` para verificar o status |

---
*Este documento é uma tradução do original em inglês. Em caso de divergência, a versão em inglês prevalece.*
