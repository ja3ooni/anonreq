> translated from en/getting-started.md

# Primeiros passos com o AnonReq

## Pré-requisitos

- Docker Engine 24+
- Docker Compose v2+
- Uma chave de API da OpenAI, Anthropic ou Gemini

## Início rápido

Execute os seguintes scripts a partir da raiz do repositório:

```bash
# Passo 1: Iniciar o gateway
./examples/quickstart/01-start-gateway.sh

# Passo 2: Enviar uma requisição de teste com PII
./examples/quickstart/02-basic-anonymization.sh

# Passo 3: Limpar
./examples/quickstart/03-cleanup.sh
```

Os scripts de início rápido lidam com toda a configuração, verificação e limpeza automaticamente. Cada script termina com o código 0 em caso de sucesso ou 1 em caso de falha com saída de diagnóstico.

## Próximos passos

- Consulte `docs/en/installation.md` para obter instruções detalhadas de instalação
- Consulte `examples/curl/`, `examples/python/`, `examples/typescript/` e `examples/go/` para ver exemplos de SDK na sua linguagem
- Consulte `docs/en/deployment.md` para obter um guia de implantação em produção
- Consulte `docs/en/compliance.md` para configurar presets de conformidade
- Consulte o arquivo README do projeto para obter uma visão geral completa

---
*Este documento é uma tradução do original em inglês. Em caso de divergência, a versão em inglês prevalece.*
