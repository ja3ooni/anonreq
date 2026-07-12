> translated from en/operations.md

# Guia de Operações do AnonReq

Este guia fornece runbooks operacionais, estruturas de configuração, especificações de monitoramento e etapas de solução de problemas para os operadores do gateway AnonReq.

## Gestão de configuração

As configurações do gateway são gerenciadas por meio de arquivos YAML carregados na inicialização do contêiner. As configurações principais são:

- **Motor de políticas (`config/policy.yaml`):** Define regras de inquilinos, limites de taxa, orçamentos de gastos e limites geográficos.
- **Configuração de SLO (`config/slo.yaml`):** Declara as metas operacionais para taxa de sucesso, latência, estados seguros e registros de auditoria.
- **Trust Center (`config/trust_center.yaml`):** Controla o acesso aos portais públicos de conformidade.

As configurações são recarregadas automaticamente ao receber um sinal `SIGHUP`.

### Exemplo de configuração de políticas

```yaml
version: "1.0"
rules:
  - rule_id: "block_restricted_pii"
    name: "Block Restricted Data"
    action: "BLOCK"
    priority: 100
    enabled: true
    conditions:
      classification_level: "Restricted"
rate_limits:
  enabled: true
  rpm: 1000
```

## Monitoramento de Objetivos de Nível de Serviço (SLOs)

O AnonReq rastreia 4 SLOs principais para garantir a segurança e o desempenho do sistema:

1. **Taxa de sucesso:** Pelo menos 99,9% das solicitações do gateway devem ser bem-sucedidas.
2. **Latência P95:** O tempo de processamento deve permanecer ≤100ms.
3. **Taxa de falhas seguras (Fail-Secure):** ≤0.1% das transações devem acionar bloqueios de segurança.
4. **Taxa de gravação de auditoria:** ≥99.99% das gravações de registros de auditoria devem ser concluídas com sucesso.

### Infraestrutura de monitoramento

- **Painel do Prometheus:** Coleta métricas de `/metrics` na porta `8080`.
- **Painel do Grafana:** Visualiza a conformidade com os SLOs e orçamentos de erros.

## Operações administrativas da CLI

Os operadores do sistema usam requisições curl para consultar status, coletar métricas e realizar atualizações.

### 1. Verificar políticas ativas
```bash
curl -X GET http://localhost:8080/v1/admin/policies   -H "Authorization: Bearer <ADMIN_API_KEY>"   -H "X-AnonReq-Role: operator"   -H "X-AnonReq-Tenant-ID: default"
```

### 2. Consultar conformidade com SLO em tempo real
```bash
curl -H "Authorization: Bearer <ADMIN_API_KEY>"      -H "X-AnonReq-Role: administrator"      http://localhost:8080/v1/governance/status
```

### 3. Verificar integridade da cadeia de auditoria criptográfica
```bash
curl -X POST http://localhost:8080/v1/governance/audit/verify   -H "Authorization: Bearer <ADMIN_API_KEY>"   -H "X-AnonReq-Role: administrator"
```

## Solução de problemas e recuperação de violação

Quando um SLO é violado, o gateway emite alertas automaticamente. Os operadores devem verificar os seguintes subsistemas:

- **Queda na taxa de sucesso:** Verifique a conectividade com os provedores (OpenAI/Gemini) e inspecione o consumo de recursos do Valkey.
- **Picos de latência:** Verifique o uso de CPU/memória dos contêineres do gateway e redimensione as instâncias conforme necessário.
- **Aumento na taxa de falhas seguras:** Inspecione os logs para verificar se o contêiner do Presidio Analyzer está respondendo ou se os padrões de regex falham ao compilar.
- **Falhas de gravação de auditoria:** Inspecione a conectividade do Valkey ou a capacidade do pool do banco de dados SQL. Verifique o espaço em disco.

---
*Este documento é uma tradução do original em inglês. Em caso de divergência, a versão em inglês prevalece.*
