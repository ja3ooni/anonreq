> translated from en/security.md

# Política de Segurança do AnonReq

Este documento descreve a postura de segurança, as garantias de tratamento de dados e os procedimentos de resposta a incidentes para o gateway AnonReq.

## Postura de segurança

O AnonReq é baseado em uma arquitetura Zero-Trust. Assumimos que todos os endpoints de modelos externos e redes públicas não são confiáveis e aplicamos limites de segurança rígidos:

- **Privilégio mínimo:** Todas as rotas administrativas e alterações de configuração exigem autorização validada usando chaves de API de alta entropia.
- **Padrões seguros contra falhas (Fail-Secure):** Todos os parâmetros de configuração usam por padrão o estado mais restritivo (por exemplo, Trust Center desativado, presets de conformidade exigidos, ações de bloqueio padrão).
- **Isolamento:** Os dados dos inquilinos (tenants), políticas e caches de sessão são estritamente isolados na memória do Valkey usando namespaces com prefixo.

## Garantias de anonymisation e tratamento de dados

O AnonReq garante que informações confidenciais em texto simples nunca sejam expostas a redes externas:

1. **Proteção de dados de saída:** O gateway intercepta todas as requisições de texto, objetos JSON e formulários multipart. As correspondências em texto simples são tokenizadas com marcadores (por exemplo, `[EMAIL_N]`) antes do trânsito pela rede.
2. **Modelo de memória efêmera:** Os mapeamentos de tokens são armazenados exclusivamente no cache do Valkey/Redis. Eles estão sujeitos a políticas rígidas de tempo de vida (TTL) e são excluídos imediatamente após a entrega da resposta ou expiração do tempo limite.
3. **Sem PII em logs ou telemetria:** Os logs de auditoria e as métricas do Prometheus contêm apenas metadados. Os dados brutos e os valores dos tokens nunca são gravados em armazenamento persistente ou stdout.

## Protocolo de resposta a incidentes

O AnonReq mantém um fluxo de trabalho ativo de resposta a incidentes para anomalias operacionais ou de sanitização. Os incidentes são categorizados em três níveis de gravidade:

### Níveis de gravidade

- **Gravidade 1 (Crítica):** Vazamento de PII em texto simples ou violação de dados; falha na verificação da assinatura da âncora criptográfica na cadeia de auditoria. Requer contenção em até 1 hora.
- **Gravidade 2 (Maior):** Interrupção do serviço ou degradação completa da pipeline de saneamento. Requer remediação em até 4 horas.
- **Gravidade 3 (Menor):** Avisos operacionais não críticos ou pequena degradação de desempenho (por exemplo, limite de latência excedido). Requer investigação em até 24 horas.

### Fluxo de resposta

1. **Detecção:** Os alertas são gerados por meio das métricas do Prometheus ou validação manual da integridade da cadeia de auditoria.
2. **Triagem:** O SRE ou o engenheiro de segurança de plantão avalia o alerta e atribui a gravidade.
3. **Contenção:** Para incidentes críticos, o gateway pode ser suspenso imediatamente (suspensão de emergência) ou as chaves dos inquilinos podem ser revogadas.
4. **Remediação:** Os desenvolvedores corrigem a causa raiz, geram um patch e atualizam o contêiner.
5. **Recuperação:** O tráfego normal é restabelecido e a integridade da cadeia de auditoria é verificada.

---
*Este documento é uma tradução do original em inglês. Em caso de divergência, a versão em inglês prevalece.*
