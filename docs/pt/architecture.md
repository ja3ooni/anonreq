> translated from en/architecture.md

# Arquitetura do Gateway AnonReq

Este documento fornece um resumo da arquitetura do gateway AnonReq. Ele detalha a topologia dos componentes, o ciclo de vida das requisições e as principais invariantes de segurança.

## Visão geral do sistema

O AnonReq é um gateway de segurança e anonymisation de IA auto-hospedado projetado para ficar entre os aplicativos da empresa e os provedores de LLM (Large Language Model) externos ou locais. Ao atuar como um proxy de interceptação, ele garante que os dados sensíveis (como PII, PHI, PCI ou segredos comerciais) sejam classificados, tokenizados e sanitizados antes de cruzar o limite de confiança da rede corporativa.

```
┌─────────────────┐       ┌─────────────────┐       ┌───────────────────┐
│                 │       │                 │       │                   │
│   Aplicativo    │──────>│ Gateway         │──────>│ Provedores de LLM │
│   da Empresa    │<──────│ AnonReq         │<──────│ (OpenAI, Gemini)  │
│                 │       │ (Auto-hospedado)│       │                   │
└─────────────────┘       └─────────────────┘       └───────────────────┘
```

## Ciclo de vida da requisição

Cada requisição enviada a um provedor externo através do AnonReq passa por uma pipeline de processamento estruturada:

1. **Entrada e Despacho de Conteúdo:** A requisição entra no gateway. O despachante de tipos de conteúdo inspeciona os cabeçalhos da requisição e direciona o fluxo para o analisador apropriado (Text, JSON ou Multipart).
2. **Classificação:** O motor de classificação verifica a requisição com base nos níveis de segurança configurados. Se um conteúdo contiver dados restritos não permitidos, o motor bloqueará a requisição ou determinará se ela precisa de roteamento local, anonymisation ou passagem direta.
3. **Detecção:** O motor de detecção combina reconhecedores de regex/checksum, integração com o Presidio e algoritmos de otimização de contexto para localizar entidades sensíveis (por exemplo, e-mails, números de telefone, cartões de crédito).
4. **Tokenização:** Os valores sensíveis detectados são extraídos e substituídos por tokens anônimos (por exemplo, `[EMAIL_0]`, `[PERSON_1]`). Os mapeamentos únicos são armazenados no gestor de cache do Valkey/Redis limitado ao ciclo de vida da sessão.
5. **Adaptador do provedor:** A requisição higienizada e tokenizada é traduzida pelo adaptador para o formato de API do LLM de destino (por exemplo, convertendo de OpenAI para Anthropic/Gemini) e encaminhada.
6. **Resposta do LLM:** O LLM externo retorna sua resposta com as referências tokenizadas.
7. **Restauração:** O motor de restauração recupera as associações no gestor de cache e substitui os tokens com seus valores originais na resposta (compatível com streaming SSE).
8. **Saída:** A resposta restaurada é retornada ao aplicativo cliente.

## Componentes principais

- **Proxy/Gateway:** Aplicativo FastAPI que executa um loop de rede ASGI.
- **Motor de classificação:** PDP (Policy Decision Point) e PEP (Policy Enforcement Point) que avaliam políticas de governança e risco.
- **Motor de detecção:** Scanner de entidades multi-locale com reconhecedores de regex e Microsoft Presidio.
- **Motores de tokenização e restauração:** Código responsável pela substituição e troca dos tokens.
- **Gestor de cache:** Instância do Valkey/Redis em memória que armazena os mapas de sessão sob um TTL estrito.
- **Adaptadores de provedores:** Camada de compatibilidade que traduz as chamadas de API em tempo real.

## Principais invariantes de segurança

- **Invariante de exposição zero:** PII brutas nunca devem cruzar o limite da rede corporativa para provedores externos sob nenhuma circunstância.
- **Comportamento seguro em caso de falha (fail-secure):** Qualquer exceção, timeout, indisponibilidade do cache ou ambiguidade de classificação deve bloquear o tráfego de saída imediatamente e retornar HTTP 503 ou 403.
- **Telemetria sem PII:** Logs de auditoria e métricas do Prometheus contêm apenas metadados. Nenhum dado bruto ou valor de token é registrado.
- **Armazenamento efêmero:** Os mapeamentos são armazenados apenas em cache temporário com TTLs rígidos, garantindo sua exclusão imediata após a transação.

---
*Este documento é uma tradução do original em inglês. Em caso de divergência, a versão em inglês prevalece.*
