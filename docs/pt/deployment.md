> translated from en/deployment.md

# Implantação

## Considerações de produção

### Alocação de recursos

Certifique-se de que seu host atenda aos requisitos mínimos de recursos para todos os três contêineres. Para implantações de produção, adicione 50% de margem de segurança acima do uso pico observado.

### Configuração de logs

Os logs são gravados no stdout em formato JSON estruturado. Configure a agregação de logs por meio de sua ferramenta preferida (driver de log do Docker, syslog ou um coletor de logs como o Fluentd ou o Vector).

### Segurança de rede

O gateway se vincula à porta 8000. O Presidio Analyzer e o Valkey estão isolados em uma rede interna do Docker e não são acessíveis diretamente do exterior.

### Terminação TLS

Termine o TLS no seu proxy reverso (nginx, Caddy ou um balanceador de carga em nuvem) e encaminhe para o gateway via HTTP na rede interna.

## Variáveis de ambiente

| Variável | Tipo | Padrão | Obrigatória | Descrição |
|----------|------|--------|-------------|-----------|
| `ANONREQ_API_KEY` | string | — | Sim | Bearer token para autenticação da API (≥ 32 caracteres) |
| `ANONREQ_LOG_LEVEL` | string | `INFO` | Não | Nível de log: DEBUG, INFO, WARNING, ERROR |
| `ANONREQ_CACHE_URL` | string | `valkey://localhost:6379` | Não | URL do servidor Valkey |
| `ANONREQ_CACHE_PASSWORD` | string | — | Não | Senha de acesso do Valkey |
| `ANONREQ_CACHE_TTL` | int | `600` | Não | TTL da sessão em segundos (60–3600) |
| `ANONREQ_OPENAI_API_KEY` | string | — | Condicional | Chave de API da OpenAI |
| `ANONREQ_ANTHROPIC_API_KEY` | string | — | Condicional | Chave de API da Anthropic |
| `ANONREQ_GEMINI_API_KEY` | string | — | Condicional | Chave de API do Google Gemini |
| `ANONREQ_OLLAMA_BASE_URL` | string | — | Não | URL do servidor do Ollama |
| `ANONREQ_LOCALE` | string | `en-US` | Não | Configuração regional padrão para detecção |
| `ANONREQ_COMPLIANCE_PRESET` | string | — | Não | Nome do preset de conformidade |
| `ANONREQ_CONFIDENCE_THRESHOLD` | float | `0.7` | Não | Limiar de confiança de detecção (0.0–1.0) |
| `PRESIDIO_ANALYZER_URL` | string | `http://presidio-analyzer:5001` | Não | URL do Presidio Analyzer |

## Configuração de produção do Docker Compose

Personalize o arquivo `docker-compose.yml` padrão com um arquivo `docker-compose.override.yml`:

```yaml
services:
  anonreq:
    deploy:
      resources:
        limits:
          cpus: "4"
          memory: "4G"
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"
```

### Configuração de testes de saúde

Cada serviço possui um teste de saúde integrado. Monitore todos os três através do endpoint `/health` do gateway. Configure o monitoramento externo para alertar em caso de respostas não-200.

### Políticas de reinicialização

Todos os serviços usam `restart: unless-stopped`. Para implantações sem tempo de inatividade, execute várias réplicas do gateway atrás de um balanceador de carga.

## Registro de logs

Logs JSON estruturados são emitidos no stdout. Campos principais: `timestamp`, `level`, `event`, `session_id`, `latency_ms`, `entity_count`, `provider`. Consuma com sua ferramenta de agregação de logs preferida.

## Atualização

1. Baixe a última imagem: `docker compose pull anonreq`
2. Recrie os serviços: `docker compose up -d --force-recreate anonreq`
3. Verifique a saúde: `curl http://localhost:8000/health`

## Segurança

- O gateway é seguro por padrão em caso de falha (fail-secure): qualquer erro de detecção ou de cache retorna HTTP 5xx e nunca envia dados não sanitizados upstream
- A rotação de chaves de API é suportada via reinicialização: atualize `ANONREQ_API_KEY` no arquivo `.env` e execute `docker compose restart anonreq`
- Todos os dados do cache são efêmeros — nenhum dado é gravado no disco

---
*Este documento é uma tradução do original em inglês. Em caso de divergência, a versão em inglês prevalece.*
