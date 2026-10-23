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

## O que o dashboard mostra

- **KPIs**: total de apontamentos, concluídos, em andamento, atrasados, prioridade alta
- **Gráficos**: evolução mensal, atrasos por setor responsável, em aberto por setor/andar,
  prioridade GUT, categorias FMS, inspeções por mês
- **Tabela**: prioridade alta em aberto, ordenada por prazo
- **Filtros**: andar, ala, setor, setor responsável, status, período

## Regras do processamento

- Apontamento real = linha com `Data_Registro` preenchido
- Status vazio → **Em andamento**
- Prazo em texto (`30 dias`) → `Data_Registro + 30 dias`
- Status do prazo: Concluído > Atrasado > Vence em até 7 dias > No prazo > Sem prazo
- Prioridade: Imediata/Alta → **Alta**; Moderada → **Moderada**; Baixa → **Baixa**; vazio → **Sem avaliação**
- Apontamento ↔ inspeção vinculados por **data + setor**
- **Anonimização**: participantes das inspeções viram quantidade (`3 participantes`)

## Como atualizar

1. Substitua `data/inspecoes_gut.xlsx` (mesmo nome, mesmas abas)
2. Commit — a automação reprocessa e publica sozinha em ~1 min
3. Ou rode manualmente: *Actions → Atualizar dashboard → Run workflow*

## Estrutura

```
├── data/inspecoes_gut.xlsx      # planilha fonte
├── scripts/processa_dados.py    # pipeline
├── dashboard/index.html         # dashboard (Chart.js)
├── dashboard/data.js            # gerado pelo script
└── .github/workflows/           # automação + publicação Pages
```

## Rodar localmente

```bash
pip install -r requirements.txt
python scripts/processa_dados.py
# abra dashboard/index.html
```