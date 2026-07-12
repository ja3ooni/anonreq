> translated from en/compliance.md

# Presets de conformidade

## Visão geral

O AnonReq fornece presets de conformidade que impõem a detecção obrigatória de entidades para estruturas regulatórias específicas. Cada preset ativa um conjunto de reconhecedores exigidos pelo regulamento correspondente.

| Preset | Regulamento | Região | Entidades exigidas |
|--------|-------------|--------|--------------------|
| `gdpr` | Regulamento Geral sobre a Proteção de Dados | UE | E-mail, telefone, nome, endereço, IP, ID nacional |
| `lgpd` | Lei Geral de Proteção de Dados | Brasil | CPF, CNPJ, e-mail, telefone, nome, endereço |
| `pdpa` | Personal Data Protection Act | Tailândia | E-mail, telefone, nome, endereço, ID nacional |
| `popia` | Protection of Personal Information Act | África do Sul | E-mail, telefone, nome, endereço, número de ID |
| `privacy-act` | Privacy Act 1988 | Austrália | E-mail, telefone, nome, endereço, Medicare, TFN |
| `pipeda` | Personal Information Protection and Electronic Documents Act | Canadá | E-mail, telefone, nome, endereço, SIN |

## Configuração por preset

Cada preset define:

- **Types de entidades obrigatórios**: regras de detecção que não podem ser desativadas enquanto o preset estiver ativo
- **Limiar de confiança**: pontuação mínima de confiança para detecção baseada em NER (padrão por preset)
- **Configuração regional (Locale)**: configuração regional associada para reconhecedores específicos do idioma

## Configurando presets

Defina o preset por meio do cabeçalho `X-AnonReq-Compliance-Preset` nas requisições:

```bash
curl -H "X-AnonReq-Compliance-Preset: gdpr"   -H "Authorization: Bearer $ANONREQ_API_KEY"   ...
```

Consulte presets disponíveis e suas configurações:

```bash
curl http://localhost:8000/v1/compliance/presets
```

## Múltiplos presets

Quando vários presets são especificados (separados por vírgula), a configuração em vigor é uma união de todos os tipos de entidades exigidos com o maior limite de confiança entre os presets selecionados.

## Validação de inicialização

Se um preset de conformidade for configurado na inicialização, o gateway validará se todos os tipos de entidades exigidos pelo preset possuem reconhecedores ativos. As configurações que desativam um tipo obrigatório são rejeitadas na inicialização.

---
*Este documento é uma tradução do original em inglês. Em caso de divergência, a versão em inglês prevalece.*
