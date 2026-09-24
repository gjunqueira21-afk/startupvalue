# Parecer 05 — Software Architecture

O sistema atual é um único HTML com estado e cálculo no navegador. Não há backend, banco, autenticação, jobs, isolamento, versionamento, logs ou operação. A mesma função mistura UI, imposto, DCF, Monte Carlo e relatório; isso impede validação e controle de acesso.

## Decisão

Adotar monólito modular: Next.js, FastAPI, PostgreSQL, Redis/RQ, worker NumPy e Playwright PDF atrás de Caddy. Engines são puros; scenario revision e SimulationResult são imutáveis. Samples privados alimentam dashboard, target e PDF. Toda entidade de negócio é escopada por workspace.

## Riscos controlados

- Outbox e idempotência evitam job perdido/duplicado.
- Hashes, seed e runtime manifest sustentam auditoria.
- Resultados agregados vão ao browser; arrays permanecem privados.
- RLS opcional reforça repositories tenant-aware.
- Expand/contract e imagens imutáveis suportam rollback.
- PostgreSQL/storage entram em backup e restore ensaiado; Redis é reconstruível.

Contrato, diagramas, módulos, API, modelo de dados e migração estão em [ARCHITECTURE.md](../ARCHITECTURE.md). Gate: nenhuma implementação de interface deve contornar a API ou publicar resultado do motor legado.

