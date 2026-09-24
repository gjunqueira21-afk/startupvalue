# Benchmark do motor de simulação

Data: 2026-09-22. Este registro mede somente o kernel vetorizado de fluxos de caixa do modo simples. Não inclui HTTP, banco de dados, filas, cálculo de DCF por cenário, serialização nem PDF e não representa capacidade de uma VPS de produção.

Ambiente observado: Python 3.11.15, NumPy 2.4.6, Windows 10 build 26200, seed `471829`, horizonte de 60 meses e cinco execuções por tamanho. O valor reportado é a mediana.

| Cenários | Mediana | Melhor execução | Memória dos arrays retornados |
|---:|---:|---:|---:|
| 1.000 | 0,0084 s | 0,0074 s | 1,45 MB |
| 5.000 | 0,0607 s | 0,0524 s | 7,24 MB |
| 10.000 | 0,1324 s | 0,1225 s | 14,48 MB |
| 25.000 | 0,3677 s | 0,3308 s | 36,20 MB |

O script reproduzível está em `apps/backend/benchmarks/benchmark_simulation.py`. Execute com:

```bash
cd apps/backend
PYTHONPATH=. python benchmarks/benchmark_simulation.py --runs 5
```

Antes do deploy, repetir o benchmark no Linux e no tamanho real da VPS, incluindo o pipeline completo de valuation, persistência e geração de relatório. Definir limites de fila e concorrência usando essas medições completas, sem extrapolar estes números locais.
