# StartupValue — Deploy em VPS

Estado: runbook proposto. Ajustar host, registry e provider de backup antes do primeiro deploy. Não há benchmark/SLO medido nesta fase.

## Topologia

Uma VPS Linux x86_64 suportada executa Docker Engine + Compose. Serviços: `caddy`, `frontend`, `backend`, `worker`, `postgres`, `redis`. Apenas Caddy publica 80/443. Backend/frontend ficam em rede app; Postgres/Redis em rede interna. Volumes: postgres data, private artifacts e Caddy data/config. Backup sai da VPS.

DNS A/AAAA aponta `DOMAIN` para a VPS. Firewall permite SSH restrito e 80/443; banco/cache nunca públicos. Caddy obtém/renova certificado automaticamente após DNS/ports corretos. Staging usa subdomínio e dados/segredos separados.

## Host baseline

Usuário de deploy sem login root rotineiro, SSH keys, password login/root remoto desabilitados após teste, patches automáticos de segurança com janela, firewall, NTP, disco/CPU/RAM monitorados. Docker group equivale a root; acesso é mínimo. Diretórios `/opt/startupvalue/{compose,secrets,backups}` com owner/permissões explícitas. Swap e limites são definidos após benchmark; não mascarar OOM recorrente.

## Configuração

`.env.example` documenta: `DOMAIN`, image tags/digests, DB name/user, Redis URL, session/CSRF secrets, email provider, storage root, Sentry DSN opcional e retention. Valores reais ficam em `/opt/startupvalue/secrets/*.env` modo 600 ou Docker secrets, fora do Git. `NEXT_PUBLIC_*` contém somente configuração pública.

Imagens são multi-stage, non-root, lockfiles obrigatórios e healthcheck. Produção usa tags imutáveis/digests; nunca `latest`. Python wheels/Node packages vêm de locks. Containers read-only quando possível, tmpfs para `/tmp`, capabilities removidas e `no-new-privileges`. Postgres/Redis têm versões major/minor fixadas e upgrade separado.

## Compose

`docker-compose.yml` contém base/dev; `docker-compose.prod.yml` adiciona Caddy, imagens release, restart `unless-stopped`, resources, logging rotation e volumes. `depends_on` não substitui readiness. Um serviço `migrate` executa Alembic uma vez; backend/worker não concorrem para migrar.

Health endpoints:

- `/health/live`: processo/event loop responde, sem depender de DB/Redis.
- `/health/ready`: Postgres e Redis com timeout curto; report storage writable/readable. Resposta pública reduzida `status` e correlation ID.
- Worker heartbeat e queue age são métricas separadas; API pode estar ready para leitura mesmo quando nova simulação é temporariamente indisponível, conforme UX.

## Primeiro deploy

1. Provisionar host, firewall, usuário, Docker e diretórios; registrar versões.
2. Configurar DNS; copiar compose/Caddyfile e secrets por canal seguro.
3. Pull de imagens por digest e `docker compose ... config` para validar.
4. Subir Postgres/Redis; confirmar volumes/permissões.
5. Executar migrate e registrar revisão Alembic.
6. Subir backend/worker/frontend; executar health/readiness.
7. Subir Caddy; validar certificado, redirect HTTP→HTTPS e headers.
8. Smoke: landing, signup/login, criar empresa, job pequeno, resultado e PDF privado.
9. Validar logs/redaction, métricas e backup inicial; só então abrir tráfego.

## Deploy recorrente

1. CI executa lint, unit/integration/numeric, build, scan e gera artefatos/SBOM.
2. Registrar release, digests, migration range e plano de rollback.
3. Fazer backup pre-deploy e verificar checksum/idade.
4. Pull; executar migrations expand compatíveis com old+new app.
5. Atualizar backend/worker/frontend e aguardar readiness; smoke automatizado.
6. Observar error rate, queue e recursos; completar contract migration em release posterior.

Na VPS única, breve restart pode ocorrer. Zero-downtime exige duas instâncias/coordenação adicional; não prometer sem testar. Job em execução deve ter shutdown gracioso ou voltar à fila sem publicar resultado parcial.

## Rollback

Rollback de app fixa digests anteriores e sobe novamente após verificar compatibilidade do schema. Não fazer downgrade destrutivo automático de banco. Migrations seguem expand→backfill→switch→contract; contract só depois de janela e backup. Se migration falhar antes do app novo, parar e investigar. Se houver corrupção, isolar serviço e seguir restore, sem sobrescrever volume original.

Registrar motivo, comandos, timestamps, release anterior/nova, integridade de resultados e incident/postmortem. SimulationResult publicado nunca é regravado para adequar versão.

## Backup

Backup diário lógico do PostgreSQL em formato custom (`pg_dump`) mais backup dos artifacts/samples/PDFs; manifests relacionam checksums. Criptografia antes de enviar a storage offsite com credencial só de escrita no job quando possível. Sugestão inicial sujeita à política: 7 diários, 5 semanais, 12 mensais; confirmar custo e LGPD antes de adotar.

Script deve usar arquivo temporário restrito, `set -e`, checksum, upload atômico, verificação remota e métrica `last_success`. Não colocar senha no comando/log. Caddy/compose/secrets são recuperados por IaC/secret manager; Redis não é fonte de verdade.

Restore drill mensal/trimestral em ambiente isolado:

1. baixar/decriptar e validar checksum;
2. criar Postgres vazio na versão compatível;
3. restaurar roles/schema/data e artifacts;
4. rodar checks de counts/FKs/result hashes e smoke autenticado;
5. medir RPO/RTO real e registrar evidência;
6. destruir com segurança o ambiente de drill.

RPO/RTO só entram em compromisso comercial após medições. Backup sem restore testado não conta como controle.

## Monitoramento

Alertas: domínio/certificado, uptime/readiness, 5xx/latência, queue depth/oldest job, job failure/time, worker heartbeat, DB connections/locks/storage, Redis memory/eviction, container restarts/OOM, disk/inodes, backup age/failure e report generation. Logs JSON com rotação local e export opcional; retention e acesso definidos. Sentry fica inativo sem DSN e recebe eventos redigidos.

Dashboards separam disponibilidade API, capacidade de simular, PDF e dependências. Health não executa query pesada. Alertas incluem runbook e evitam dados tenant.

## Caddy

Caddyfile recebe `{$DOMAIN}`, comprime respostas adequadas, aplica proxy timeouts, request body limits e security headers coordenados com app. `/api/*` → backend; restante → frontend. Download protegido passa pela API/internal route; diretório de artifacts nunca vira `file_server`. HSTS só após domínio validado; CSP com nonce é emitida pela camada capaz de gerar nonce.

Referências: [Caddy Automatic HTTPS](https://caddyserver.com/docs/automatic-https), [FastAPI em containers](https://fastapi.tiangolo.com/deployment/docker/), [Next.js self-hosting](https://nextjs.org/docs/app/guides/self-hosting).

## Runbooks

- Queue stopped: impedir novos jobs, manter resultados legíveis, verificar Redis/worker/OOM, reiniciar de forma graciosa, reconciliar outbox.
- DB unavailable: read-only não é presumido; retornar indisponível, evitar retry storm, verificar volume/conexões e restaurar só com evidência.
- Disk high: parar novos jobs/reports, identificar artifacts/logs por política, nunca apagar samples arbitrariamente.
- Cert failure: confirmar DNS/80/443/rate CA e logs Caddy; não servir HTTP autenticado.
- Compromise: isolar, revogar secrets/sessions, preservar evidência, reconstruir de imagens limpas e seguir plano LGPD.

## Gate de produção

Bloquear go-live se compose não sobe limpo, migrations não têm plano compatível, portas internas estão públicas, TLS/headers falham, secrets aparecem em Git/log, cross-tenant/security suite falha, backup/restore não foi ensaiado, relatório não é privado, ou health/monitoring não identifica dependência indisponível.

