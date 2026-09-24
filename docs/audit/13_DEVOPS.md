# Parecer 13 — DevOps e SRE

Não havia Docker, deploy, healthcheck, backup, rollback, logging ou monitoramento no sistema inicial. A arquitetura de VPS é viável como primeiro estágio se tratar Postgres e artifacts como estado durável, Redis como efêmero e Caddy como único ingresso.

Decisão: Compose com imagens imutáveis, migrations únicas e expand/contract, health live/ready, backup criptografado offsite e restore drill. Deploy/rollback são procedimentos registrados; SLO/RPO/RTO dependem de medição. O runbook está em [DEPLOY_VPS.md](../DEPLOY_VPS.md).

Gate: nenhuma produção sem restore testado, portas privadas, TLS, redaction, observabilidade de jobs e rollback compatível com schema.

