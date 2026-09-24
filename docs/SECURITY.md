# StartupValue — Segurança e privacidade

Estado: requisitos anteriores à implementação. Alvo: SaaS multi-tenant com dados financeiros confidenciais. Este documento não é certificação.

## Threat model

Ativos: credenciais/sessões, perfis de empresas, projeções, scenarios/samples, resultados, PDFs, dados de cobrança e audit trail. Adversários: usuário tentando IDOR entre tenants, credential stuffing, atacante web explorando XSS/CSRF/SSRF/upload, insider/admin abusivo, pacote/CI comprometido e acesso à VPS/backup. Fronteiras: browser↔Caddy, Caddy↔apps, API↔Postgres/Redis/storage, worker↔storage, operadores↔VPS.

Riscos prioritários: cross-tenant read/write/delete/export; sessão roubada/fixada; reset de senha; URL de relatório previsível; dados em logs/erros; job manipulando recurso de outro workspace; HTML de relatório provocando SSRF; segredo em frontend/imagem; backup não criptografado ou não restaurável.

## Identidade e sessão

Senha com Argon2id, parâmetros versionados e rehash no login quando necessário; nunca criptografia reversível/plaintext. Política aceita passphrases longas, permite password managers, bloqueia senhas conhecidas quando serviço seguro disponível e não impõe trocas periódicas sem incidente.

Sessão opaca com pelo menos 128 bits aleatórios; somente hash no banco. Cookie `Secure; HttpOnly; SameSite=Lax; Path=/`, sem domínio amplo. Rotacionar após login, reset, mudança de privilégio e ação sensível; expiração idle e absoluta, revoke/logout server-side e lista de sessões do usuário. Não guardar auth bearer em localStorage.

Mutações com cookie exigem CSRF token ligado à sessão (synchronizer ou signed double-submit corretamente ligado), validação Origin/Host e métodos não seguros sem efeito em GET. Login e reset têm mensagens uniformes e rate limit por IP/conta com escalonamento. Reset token aleatório, hash no banco, uso único, prazo curto; reset revoga sessões e registra audit event.

Referências: [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

## Autorização e multi-tenancy

Toda operação recebe `ActorContext(user_id, workspace_id, role)` derivado da sessão. Cliente nunca escolhe `user_id`. Repositories exigem `workspace_id`; queries aplicam tenant antes de ID. Criação valida que parents pertencem ao mesmo tenant. Jobs armazenam tenant e revalidam acesso/contexto no worker. Objetos derivados herdam tenant do resultado, não do request.

Roles iniciais: owner, admin, analyst, viewer; platform_admin é separado, just-in-time quando possível, com razão e auditoria. Owner não pode remover último owner sem transferência. Entitlements controlam capacidade, não autorização sobre recurso.

PostgreSQL RLS como defesa adicional em tabelas tenant-owned: `ENABLE/FORCE ROW LEVEL SECURITY`, políticas default-deny, contexto transacional definido pela API e role da app sem `BYPASSRLS`. Migrations/admin usam role separada. Testes verificam ausência de policy e pool reutilizado sem contexto. Referência: [PostgreSQL Row Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).

## Reports, samples e jobs

PDFs/samples ficam fora de static/public com chaves aleatórias. Download autenticado autoriza workspace a cada request; alternativa é link assinado curto, escopo de objeto/disposition, sem listagem, revogável e sem dados no path. Caddy usa `X-Accel`/internal ou API streaming após autorização. Logs não registram signed URL.

Worker aceita IDs internos, carrega revisão/result por tenant e nunca recebe código/template do usuário. PDF usa template empacotado, escape de conteúdo e rede bloqueada/allowlist vazia no Chromium para impedir SSRF. Assets locais. Limites de CPU/memória/tempo/tamanho e filas separadas. Zip/CSV import futuro exige defesa contra zip bomb/formula injection; MVP não aceita upload arbitrário.

## Aplicação e API

Validação estrutural e semântica no backend; ORM parametrizado; IDs opacos não substituem auth. Mass assignment bloqueado por schemas de comando. Paginação/limites em listas e payloads. Idempotency key ligada a actor/workspace/body hash. CORS desabilitado quando same-origin; se necessário, origins exatas e credentials explícitas.

CSP com nonce/hash e `default-src 'self'`, `object-src 'none'`, `base-uri 'none'`, `frame-ancestors 'none'`; fontes/scripts empacotados. HSTS somente após HTTPS estável; `nosniff`, Referrer-Policy, Permissions-Policy. Sanitizar qualquer rich text ou não suportá-lo. React escaping não cobre `dangerouslySetInnerHTML`.

Rate limits em auth, simulações, target, report e export; quotas transacionais impedem corrida de consumo. Erros externos usam code/correlation ID, sem SQL/trace/config. `/health/ready` não revela credenciais/topologia detalhada publicamente.

## Segredos e supply chain

`.env.example` contém nomes, nunca valores. Produção usa arquivos/env root-readable fora do repositório; permissões mínimas e rotação documentada. Segredos separados por ambiente; DB user sem superuser; Redis privado com auth; Caddy é único serviço público. Chaves não entram em `NEXT_PUBLIC_*`, imagem, log, PDF ou backup de código.

Dependências lockadas e imagens base por digest; SBOM e vulnerabilidade scan no CI; secret scan pre-commit/CI; releases assinadas quando pipeline permitir. Atualizações têm cadência e patch urgente. Build não baixa scripts de CDN em runtime.

## Logging e audit trail

Logs estruturados permitem: timestamp, serviço, severity, correlation/job ID, route, status/duração e IDs pseudonimizados. Proibidos: senha, cookie, CSRF/reset token, full request/response, projeções e signed URLs. Redaction ocorre antes do sink; testes com canários sensíveis.

Audit trail append-only registra login/logout/reset, membership/role, empresa/scenario/revision, simulation/report/export/download, deletion e admin access, com actor, tenant, resource, action, outcome, time e razão redigida. Acesso ao audit é autorizado e exportável quando aplicável. Clock UTC/NTP.

## LGPD e ciclo de dados

Inventário e finalidade por categoria; minimização e privacy by default. Privacy/Terms explicam controlador/operador, base legal definida com assessor jurídico, suboperadores, retenção, transferência e canal de titular. Consentimento não é usado como base genérica quando outra se aplica.

Export Data produz pacote autenticado e auditado. Delete Analysis/Startup remove ou agenda cascata sem afetar outro tenant. Delete Account exige reautenticação, trata ownership/workspace compartilhado, revoga sessões e enfileira deleção. Backups expiram pela retenção; deleção lógica não promete remoção instantânea de backup imutável, mas impede restauração seletiva sem reprocessar tombstones. Retenção é definida por dado/plano/obrigação, não “para sempre”.

Incidente: preservar evidência, conter/revogar, avaliar impacto e obrigações LGPD com responsável, comunicar conforme decisão documentada e fazer postmortem. Não prometer prazo regulatório inventado no produto.

## Testes e gate

- Matriz cross-tenant para list/get/create/update/archive/delete/duplicate/simulation/target/report/export e admin; IDs válidos de outro tenant retornam resposta não enumerável.
- Session fixation/rotation/revoke/expiry; cookie flags; CSRF ausente/incorreto/origin cross-site; reset reuse/expiry/enumeration.
- RBAC por endpoint e mudança de role; RLS default-deny, `FORCE`, conexão reciclada.
- XSS/CSP, injection, mass assignment, rate limit/concurrency/quota, SSRF do renderer.
- PDF/sample direct path, expired/swap signed token, cache headers, tenant change após link.
- Secret/dependency/container scan e teste de redaction.
- Backup restore em ambiente isolado com acesso restrito e tombstones.

Release bloqueado por finding Critical/High sem mitigação aceita, qualquer fuga cross-tenant, segredo versionado, relatório público, senha fraca/plaintext, ausência de CSRF em cookie auth, ou logs com tokens/dados financeiros.

