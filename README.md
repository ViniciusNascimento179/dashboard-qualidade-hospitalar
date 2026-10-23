# Dashboard de Inspeções das Instalações — GUT 🏥📊

Dashboard público de indicadores de qualidade para inspeções de instalações hospitalares,
com priorização **GUT** (Gravidade × Urgência × Tendência).

> ⚠️ Dados de demonstração/estudo. Nomes de participantes das inspeções foram **anonimizados**
> (exibidos como quantidade). Não contém dados de pacientes.

## Como funciona

```
data/inspecoes_gut.xlsx (abas: Planos classificados + Inspeções)
        │  scripts/processa_dados.py
        ▼
dashboard/data.js  ──►  dashboard/index.html (Chart.js)
        │  GitHub Actions (.github/workflows/atualizar-dashboard.yml)
        ▼
GitHub Pages (site público)
```