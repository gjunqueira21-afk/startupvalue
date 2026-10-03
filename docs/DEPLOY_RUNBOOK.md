# QuantoVale — Runbook de deploy (Hostinger VPS)

Sequência operacional de uma página, derivada de [DEPLOY_VPS](DEPLOY_VPS.md).
Em caso de divergência, `DEPLOY_VPS.md` é a referência completa; este runbook
é o roteiro de execução. Todo comando é parametrizado por `DOMAIN`; nenhum
outro hostname deve aparecer em configuração versionada.

Convenção de caminho usada aqui: `/opt/quantovale/{app,secrets,backups}`. A
instância Hostinger já em operação (`infra/scripts/hostinger-deploy.sh`) hoje
grava em `/opt/startupvalue/` com `DOMAIN` fixo no script — isso é legado da
renomeação em curso. Para reaproveitar aquele script com os caminhos abaixo,
ajuste `BASE` e `DEFAULT_DOMAIN` nele antes de rodar; para um VPS novo, siga
os comandos manuais desta página, que usam `docker-compose.yml` +
`docker-compose.prod.yml` (Caddy termina TLS — é o fluxo documentado no
README). Se o host de destino já tem um Traefik compartilhado dono das portas
80/443 (como o VPS atual), use `docker-compose.hostinger.yml` no lugar da
etapa 7 (Caddy) — ver nota na seção 5.

## 1. Pré-requisitos

- VPS Hostinger KVM com pelo menos 8 GB de RAM, Docker Engine e Docker
  Compose v2 instalados (`docker --version`, `docker compose version`).
- Domínio registrado e sob seu controle de DNS.
- Acesso SSH somente por chave; login de senha e root remoto desabilitados.
- Usuário de deploy sem login root rotineiro (grupo `docker` já equivale a
  root — tratar como tal).

## 2. DNS

1. Criar registro A (e AAAA, se houver IPv6) de `DOMAIN` apontando para o IP
   da VPS.
2. Aguardar propagação e confirmar antes de emitir certificado:
   ```bash
   dig +short "$DOMAIN"
   ```
   O IP retornado deve ser o da VPS em todas as resoluções relevantes
   (considerar TTL e caches de resolvedor público).

## 3. Secrets

Arquivo real em `/opt/quantovale/secrets/production.env`, modo `600`, fora do
Git:

```bash
sudo mkdir -p /opt/quantovale/secrets
sudo cp infra/env/production.env.example /opt/quantovale/secrets/production.env
sudo chmod 600 /opt/quantovale/secrets/production.env
```

Editar e substituir **todo** `CHANGE_ME`:

- `DOMAIN=<hostname real>` — único knob de hostname; alimenta os rótulos
  Traefik/Caddy, `PUBLIC_APP_URL` e o guard de origem confiável do backend
  (`app/core/config.py: Settings.domain`, consumido por
  `app/auth/csrf.py:_trusted_origin`, que soma `https://{DOMAIN}` aos origins
  aceitos). Sem `DOMAIN` correto, POSTs autenticados e o POST público de
  waitlist do próprio domínio de produção recebem `403 untrusted_origin`.
- `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `SESSION_SECRET`, `CSRF_SECRET` —
  valores aleatórios de pelo menos 32 bytes (`openssl rand -hex 32`).
  `CSRF_SECRET` com menos de 32 caracteres faz o processo falhar ao subir em
  `APP_ENV=production`.
- `FRONTEND_IMAGE` / `BACKEND_IMAGE` — tag ou digest imutável de CI; nunca
  `latest`.
- `SENTRY_DSN` — opcional; vazio mantém a integração desativada.

Nenhuma variável de ambiente nova foi introduzida pelas Tasks 1-15 desta
branch (confirmado por diff vazio em `apps/backend/app/core/config.py` contra
`main`): `production.env.example` continua sendo a lista completa.

Se o host usar o gate opcional de HTTP Basic Auth
(`docker-compose.gate.yml`, ativado quando `BASIC_AUTH_USERS` está definido):
o Compose interpola `$` dentro do env file, então todo `$` do hash bcrypt
gerado por `htpasswd` deve ser dobrado para `$$`, ou o hash chega truncado no
rótulo Traefik:

```bash
docker run --rm httpd:2.4-alpine htpasswd -nbB usuario 'senha' \
  | sed -E 's/\$/\$\$/g' >> /opt/quantovale/secrets/production.env
```

## 4. Migrations

`alembic upgrade head` nesta branch aplica, em sequência, a partir do estado
atual de produção:

```
... -> c4a1e5b9d201 (workspace plan)
    -> e7f2a9c3b115 (report branding)
    -> f3d8b6a1c922 (waitlist)
```

e, após a Task 18, mais uma revisão no topo da cadeia:

```
    -> a9c4d2e8f106 (admin de plataforma)
```

Todas as quatro são aditivas (novas colunas/tabelas com default seguro ou
nulas) e seguras para rollback de aplicação sem downgrade de schema — não há
etapa de contract pendente nesta leva.

## 5. Ordem de subida

```bash
export ENV_FILE=/opt/quantovale/secrets/production.env
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml config --quiet
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml up -d postgres redis
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml --profile tools run --rm migrate
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml up -d
```

O último `up -d` sobe `backend`, `worker`, `frontend` e `caddy` (Caddy só
depois dos demais estarem saudáveis — `depends_on` com `condition:
service_healthy` no compose, não apenas ordem textual). Confirmar com
`docker compose ... ps` que todos os serviços ficam `healthy`/`running`
antes de seguir para o smoke test.

**Host com Traefik compartilhado (dono de 80/443):** acrescentar
`-f docker-compose.hostinger.yml` (e `-f docker-compose.gate.yml` se o gate
de senha estiver ativo) a cada comando acima; o serviço `caddy` fica parado
(profile `local-proxy`) e o roteamento/TLS é feito pelos rótulos Traefik do
`frontend`/`backend`, lidos de `${DOMAIN}`.

## 6. Smoke test

1. **HTTPS e headers**: `curl -I https://$DOMAIN/` — certificado válido,
   redirect HTTP→HTTPS, `Strict-Transport-Security`,
   `X-Content-Type-Options: nosniff`, `X-Frame-Options`/frame-ancestors e
   `Referrer-Policy` presentes.
2. **Readiness**: `curl -fsS https://$DOMAIN/health/live` e
   `.../health/ready` retornam `200` (ready depende de Postgres/Redis/storage
   com timeout curto).
3. **Fluxo principal**: signup → login → wizard de valuation → simulação →
   download de PDF do relatório autenticado (via rota da API, nunca
   `file_server` direto no volume).
4. **Waitlist pública**: `POST /api/v1/waitlist` sem sessão, com `Origin:
   https://$DOMAIN`, deve retornar sucesso (idempotente por e-mail; a
   mesma origem precisa estar coberta pelo `DOMAIN` da seção 3 ou recebe
   `403 untrusted_origin`):
   ```bash
   curl -i -X POST "https://$DOMAIN/api/v1/waitlist" \
     -H "Origin: https://$DOMAIN" -H "Content-Type: application/json" \
     -d '{"email":"smoke-test@example.com","plan_interest":"consultor","source":"runbook-smoke"}'
   ```
5. **PDF com marca (plano consultor)**: `scripts/set_plan.py` vive em
   `apps/backend/scripts/` e **não é copiado para a imagem** (o `Dockerfile`
   só empacota `app/` e `alembic/` — ver `apps/backend/Dockerfile`). Rode-o
   contra o container via stdin, a partir do checkout local (`-T` desativa o
   pseudo-TTY, igual ao padrão já usado pelo serviço `migrate` em
   `infra/scripts/hostinger-deploy.sh`):
   ```bash
   docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml \
     exec -T backend python - --workspace-id <uuid-do-workspace-de-teste> --plan consultor \
     < apps/backend/scripts/set_plan.py
   ```
   Gerar um relatório nesse workspace e verificar visualmente que a marca
   configurada (ou ausência de marca padrão) aparece no PDF. Reverter o plano
   de teste ao final (`--plan free`).
6. **Painel de admin de plataforma** (introduzido na Task 18 —
   `apps/backend/scripts/set_admin.py`, mesma ressalva de empacotamento do
   item acima): conceder a flag de admin a um usuário de teste pelo mesmo
   padrão de stdin, confirmar acesso ao painel, e revogar a flag depois do
   teste:
   ```bash
   docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml \
     exec -T backend python - --email <email-do-usuario-de-teste> --grant \
     < apps/backend/scripts/set_admin.py
   ```
   O e-mail é normalizado (espaços removidos, minúsculas) como no cadastro.
   Para revogar ao final do teste, repetir o comando trocando `--grant` por
   `--revoke`.

## 7. Backup e rollback

Drill de backup (gera dump lógico do Postgres + artifacts/samples +
checksums em diretório restrito):

```bash
sudo ENV_FILE=/opt/quantovale/secrets/production.env \
  BACKUP_ROOT=/opt/quantovale/backups \
  RETENTION_DAYS=14 \
  ./infra/scripts/backup.sh
```

Restore isolado (nunca sobrescreve o volume/banco ativo):

```bash
sudo ENV_FILE=/opt/quantovale/secrets/production.env \
  ./infra/scripts/restore-drill.sh /opt/quantovale/backups/<timestamp>
```

Não considerar backup como controle até um restore real ter sido
exercitado e medido (RPO/RTO).

Rollback de aplicação: fixar `FRONTEND_IMAGE`/`BACKEND_IMAGE` da release
anterior em `production.env` e repetir o `up -d` da seção 5. As quatro
migrations desta leva (seção 4) são aditivas — o schema novo permanece
compatível com a versão anterior do app, então rollback de container não
exige downgrade de banco. Nunca fazer downgrade destrutivo automático;
investigar e parar se uma migration falhar antes do app novo subir.

## 8. Gate de produção (bloquear go-live se)

- Compose não sobe limpo (`config`/`up` falham ou ficam `unhealthy`).
- Migrations não têm plano compatível com a versão anterior do app.
- Qualquer porta interna (Postgres, Redis, backend, frontend) está exposta
  publicamente — só Caddy/Traefik deve publicar 80/443.
- TLS ou headers de segurança falham na verificação da seção 6.
- Algum secret aparece em Git, log ou saída de comando.
- A suíte cross-tenant/segurança não passa.
- Backup/restore não foi ensaiado (seção 7).
- Relatório/PDF não é privado (download fora de rota autenticada da API).
- Health/monitoramento não identifica dependência indisponível (Postgres,
  Redis, storage).

(Lista completa e justificativas em `DEPLOY_VPS.md` §"Gate de produção".)
