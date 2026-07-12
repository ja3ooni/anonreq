> translated from en/faq.md

# Perguntas Frequentes

## O que acontece quando a detecção de PII falha?

O gateway é seguro por padrão em caso de falha (fail-secure). Se ocorrerem erros de detecção, cache ou tempo limite do provedor, a requisição retornará HTTP 5xx e nenhum dado será enviado upstream. Consulte a arquitetura de segurança no README do projeto para obter detalhes.

## Meus dados são mantidos em algum lugar?

Não. Todos os mapeamentos de PII para tokens são armazenados no Valkey sem persistência (`save ""`). Os mapeamentos são excluídos após o envio da resposta. Os logs contêm apenas metadados — nenhum valor bruto de PII.

## Quais provedores de LLM são suportados?

OpenAI, Azure OpenAI, Anthropic (Claude), Google Gemini e Ollama (modelos locais). O gateway traduz o formato de requisição compatível com a OpenAI para o protocolo nativo de cada provedor.

## Como funciona o streaming?

O gateway usa uma máquina de estados finitos (FSM) do tipo Tail_Buffer para lidar com tokens divididos entre limites de chunks SSE. Os tokens são restaurados em tempo real à medida que os chunks chegam. A resposta é idêntica, byte a byte, ao modo sem streaming.

## Qual é o formato do token?

As PII detectadas são substituídas por marcadores `[TYPE_N]`, onde `TYPE` é o tipo da entidade (por exemplo, `EMAIL`, `PHONE`) e `N` é um índice único. A correspondência de tokens não diferencia maiúsculas de minúsculas e os colchetes são opcionais durante a restauração.

## Como os parâmetros regionais (locales) são tratados?

Defina o cabeçalho `X-AnonReq-Locale` para ativar a detecção específica do idioma. Vários idiomas podem ser combinados (separados por vírgula). Idiomas não suportados retornam HTTP 400.

## Posso adicionar padrões de detecção personalizados?

Sim, reconhecedores regex personalizados podem ser adicionados por meio de um arquivo de configuração YAML e recarregados dinamicamente sem reinicialização. Consulte a documentação de configuração para ver o formato da regra.

## Como posso contribuir?

As contribuições são bem-vindas sob a licença Apache 2.0. Consulte o guia de contribuição no repositório para obter as diretrizes de pull request e as instruções de configuração de desenvolvimento.

---
*Este documento é uma tradução do original em inglês. Em caso de divergência, a versão em inglês prevalece.*
