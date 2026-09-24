# Fontes e evidências da auditoria

Data: 22 de setembro de 2026. Escopo: leitura integral, auditoria do protótipo e especificação do SaaS. A presença de uma especificação não significa que a funcionalidade esteja implementada ou homologada.

## Originais preservados

| Arquivo | Bytes | SHA256 |
| --- | ---: | --- |
| `manual_startupvalue.docx` | 21004 | `12003EB7BB1A7D97D30B78CE20B67C76740D8A03ACFAAE42B6F7C134670598AB` |
| `startupvalue_dashboard (1).html` | 63923 | `2A0B6BBA5C98362697B3804C1BE6A4A5E6C0EC1A22149730712936F7166F2DBB` |

O manual foi lido integralmente por extração OOXML em ordem documental, incluindo os parágrafos das 24 tabelas: 324 parágrafos e 318 nós de texto. O arquivo não contém desenhos, equações OMML nem alterações controladas. Comentários estão vazios; notas de rodapé e de fim contêm somente separadores. Relações do documento não apontam para imagens, documentos incorporados ou fontes externas com conteúdo adicional. A extração numerada está em `evidence/manual_full_text.txt`; identificadores P0001–P0324 usados nos pareceres referem-se a esses parágrafos, não a páginas renderizadas. A extração não é uma auditoria visual do layout do Word.

O HTML foi lido integralmente: 1666 linhas incluindo CSS, marcação, estado, navegação, cálculos, simulação, gráficos e exportação. Referências de linha nos pareceres apontam ao original inalterado, com numeração iniciada em 1. Não havia outro código de aplicação, dependências, testes ou infraestrutura no diretório inicial. Nenhum AGENTS.md foi encontrado no diretório ou nas pastas ancestrais verificadas.

## Verificação executada

`node docs/audit/evidence/probe_legacy.cjs` executa as funções originais dentro de um contexto isolado do Node e compara casos pequenos com aritmética independente. O resultado está em `evidence/legacy_probe_results.json`. Runtime observado: Node v24.16.0. Os testes caracterizam defeitos existentes; não constituem testes de aprovação de um novo engine.

Foram demonstrados: imposto do Simples dividido por 12 duas vezes; unidades e desconto do VC; convenção terminal; aceitação silenciosa de g igual ao WACC; aporte incompatível com participação; viés por exclusão de resultados; histograma degenerado. A média da distribuição triangular foi verificada analiticamente a partir da transformação usada no código.

## Limites da evidência

Não houve implantação, benchmark de um novo engine, teste Docker, teste E2E de SaaS nem validação visual de PDF institucional. Esses componentes ainda não existiam durante a auditoria. Docker não foi encontrado no PATH local; isso não prova ausência em outro ambiente. Nenhum domínio, acesso VPS ou configuração de e-mail transacional foi fornecido. Nenhum parecer de agente equivale a homologação contábil, jurídica ou certificação de segurança.

As fontes públicas consultadas ficam junto das conclusões correspondentes. Regras tributárias devem ser vinculadas ao período fiscal da projeção, não apenas à data desta auditoria. Dados financeiros locais não foram enviados nas buscas públicas.
