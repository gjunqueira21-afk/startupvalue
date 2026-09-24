# Parecer 12 — Security Engineering

O HTML legado não tem fronteira de servidor e, portanto, não oferece autenticação, autorização, multi-tenancy, sessão, proteção de relatório, audit trail ou LGPD operacional. A futura mudança para SaaS cria riscos que não podem ser resolvidos por IDs aleatórios ou filtros no frontend.

Decisão: sessão opaca server-side, Argon2id, CSRF ligado à sessão, repositories workspace-aware e RLS default-deny como defesa adicional. Samples/PDFs ficam privados; worker e renderer são isolados. Logs são redigidos e ações sensíveis auditadas. Requisitos e testes estão em [SECURITY.md](../SECURITY.md).

Gate: nenhuma rota tenant-owned sem teste cross-tenant; nenhum report/sample público; nenhum segredo ou payload financeiro em log; restore e deletion workflows precisam de evidência.

