#!/usr/bin/env python3
"""
Projeto 2 — Dashboard público de Inspeções das Instalações com GUT.

Lê data/inspecoes_gut.xlsx (abas: 'Planos classificados' + 'Inspeções'),
vincula cada apontamento à sua inspeção pela DATA, anonimiza participantes
(quantidade em vez de nomes) e gera dashboard/data.js.

Regras:
  - Apontamento real = linha com Data_Registro preenchido
  - Status vazio -> 'Em andamento'
  - Prazo texto 'N dias' -> Data_Registro + N dias
  - Prioridade: Imediata/Alta->Alta, Moderada->Moderada, Baixa->Baixa,
    vazio/'Pendente de avaliação'->Sem avaliação
  - Participantes: 'Luana, Melissa, Sara' -> '3 participantes' (anonimizado)
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT = ROOT / "dashboard" / "data.js"

FONTES = ["inspecoes_gut.xlsx", "inspecoes_gut.csv"]

STATUS_MAP = {
    "concluido": "Concluído",
    "em andamento": "Em andamento",
    "nao iniciado": "Não iniciado",
    "em validacao": "Em validação",
    "cancelado": "Cancelado",
}


def _sem_acento(txt: str) -> str:
    return unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()


def _norm(txt) -> str:
    return _sem_acento(str(txt).strip().lower())


def carregar() -> tuple[pd.DataFrame, pd.DataFrame]:
    for nome in FONTES:
        caminho = DATA_DIR / nome
        if caminho.exists():
            if caminho.suffix == ".xlsx":
                p = pd.read_excel(caminho, sheet_name="Planos classificados")
                i = pd.read_excel(caminho, sheet_name="Inspeções")
            else:
                p = pd.read_csv(caminho)
                i = pd.read_csv(DATA_DIR / "inspecoes_lista.csv")
            print(f"[fonte] {caminho.name} — {len(p)} apontamentos, {len(i)} inspeções")
            return p, i
    raise SystemExit("Planilha não encontrada em data/inspecoes_gut.(xlsx|csv)")


def limpar_planos(p: pd.DataFrame) -> pd.DataFrame:
    brutas = len(p)
    p = p.dropna(subset=["Data_Registro"]).copy()
    p["data"] = pd.to_datetime(p["Data_Registro"], errors="coerce", dayfirst=True)
    p = p.dropna(subset=["data"])
    print(f"[limpeza] {brutas} -> {len(p)} apontamentos")

    p["status"] = p["Status"].map(_norm)
    p.loc[p["status"].isin(("", "nan", "none")), "status"] = "em andamento"

    def prazo_final(r):
        v = r["Prazo"]
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return pd.NaT
            digits = "".join(ch for ch in s if ch.isdigit())
            if "dia" in _norm(s) and digits and len(digits) <= 3:
                return r["data"] + timedelta(days=int(digits))
            return pd.to_datetime(s, dayfirst=True, errors="coerce")
        if pd.notna(v):
            return pd.Timestamp(v)
        return pd.NaT

    p["prazo"] = p.apply(prazo_final, axis=1)
    p["conclusao"] = pd.to_datetime(p["Data Conclusão Real"], errors="coerce", dayfirst=True)

    hoje = pd.Timestamp(datetime.now(timezone.utc).date())

    def status_prazo(r) -> str:
        if r["status"] == "concluido":
            return "Concluído"
        if pd.isna(r["prazo"]):
            return "Sem prazo"
        ref = r["conclusao"] if pd.notna(r["conclusao"]) else hoje
        if r["prazo"] < ref:
            return "Atrasado"
        if r["prazo"] <= ref + pd.Timedelta(days=7):
            return "Vence em até 7 dias"
        return "No prazo"

    p["status_prazo"] = p.apply(status_prazo, axis=1)

    def prioridade(r) -> str:
        v = _norm(r["Prioridade GUT"])
        if v == "baixa":
            return "Baixa"
        if v == "moderada":
            return "Moderada"
        if v in ("alta", "imediata"):
            return "Alta"
        return "Sem avaliação"

    p["prioridade"] = p.apply(prioridade, axis=1)

    for origem, destino in [
        ("Setor", "setor"), ("Setor Responsável", "responsavel_setor"),
        ("Categoria por Tópico do FMS", "categoria"),
        ("Apontamento", "apontamento"), ("Observações", "observacoes"),
        ("Ação_Proposta", "acao_proposta"), ("Indicador_Relacionado", "indicador"),
    ]:
        p[destino] = p[origem].fillna("").astype(str).str.strip() if origem in p.columns else ""
    for col in ("setor", "responsavel_setor", "categoria"):
        p[col] = p[col].replace({"": "Não informado", "nan": "Não informado"})

    ci = p["Conteção Imediata ?"].map(_norm) if "Conteção Imediata ?" in p.columns else pd.Series("", index=p.index)
    p["contencao"] = ci.map({"sim": True}).fillna(False)

    for c in ("Gravidade", "Urgência", "Tendência"):
        nome = _sem_acento(c).lower().replace(" ", "_")
        p[nome] = pd.to_numeric(p[c], errors="coerce").fillna(0).astype(int)
    p["gut"] = p["gravidade"] * p["urgencia"] * p["tendencia"]
    return p


def limpar_inspecoes(i: pd.DataFrame) -> pd.DataFrame:
    i = i.dropna(subset=["Data da inspeção"]).copy()
    i["data"] = pd.to_datetime(i["Data da inspeção"], errors="coerce", dayfirst=True)
    i = i.dropna(subset=["data"])

    # ANONIMIZAÇÃO: participantes -> quantidade
    # (xlsx traz nomes; csv público traz contagens prontas em Num_Participantes)
    if "Participantes informados" in i.columns:
        def conta_participantes(v) -> int:
            if pd.isna(v) or not str(v).strip():
                return 0
            return len([x for x in re.split(r"[;,]", str(v)) if x.strip()])
        i["num_participantes"] = i["Participantes informados"].apply(conta_participantes)
    else:
        i["num_participantes"] = pd.to_numeric(i.get("Num_Participantes", 0), errors="coerce").fillna(0).astype(int)

    if "Setores presentes" in i.columns:
        def conta_setores(v) -> int:
            if pd.isna(v) or not str(v).strip():
                return 0
            return len([x for x in re.split(r"[;]", str(v)) if x.strip()])
        i["num_setores_presentes"] = i["Setores presentes"].apply(conta_setores)
    else:
        i["num_setores_presentes"] = pd.to_numeric(i.get("Num_Setores_Presentes", 0), errors="coerce").fillna(0).astype(int)

    for origem, destino in [
        ("Setor original", "setor_original"), ("Andar", "andar"),
        ("Ala", "ala"), ("Responsável acompanhou?", "responsavel_acompanhou"),
        ("Apontamentos no checklist", "apontamentos_checklist"),
    ]:
        i[destino] = i[origem].fillna("").astype(str).str.strip() if origem in i.columns else ""
    return i


def main() -> None:
    p, i = carregar()
    p = limpar_planos(p)
    i = limpar_inspecoes(i)

    # vincula apontamento -> inspeção por DATA + SETOR (5 datas têm 2-3 inspeções)
    i_min = i[["data", "ID_Inspeção", "setor_original", "andar", "ala",
               "responsavel_acompanhou", "num_participantes", "num_setores_presentes"]].copy()
    i_min["data"] = i_min["data"].dt.normalize()
    i_min["chave_setor"] = i_min["setor_original"].map(
        lambda s: _sem_acento(str(s)).strip().lower())
    j = p.copy()
    j["chave_setor"] = j["setor"].map(lambda s: _sem_acento(str(s)).strip().lower())
    j = j.merge(i_min.drop(columns=["setor_original"]),
                left_on=["chave_setor", "data"],
                right_on=["chave_setor", "data"], how="left")
    sem_vinculo = int(j["ID_Inspeção"].isna().sum())
    j = j.drop(columns=["chave_setor"], errors="ignore")

    linhas = []
    for r in j.itertuples(index=False):
        aid = None
        s = str(getattr(r, "Ação", "")).replace(".0", "")
        if s.replace(".", "", 1).isdigit():
            aid = int(float(getattr(r, "Ação")))
        linhas.append({
            "id": aid,
            "data": r.data.strftime("%Y-%m-%d"),
            "setor": r.setor,
            "andar": "" if pd.isna(r.andar) else str(r.andar),
            "ala": "" if pd.isna(r.ala) else str(r.ala),
            "responsavel_setor": r.responsavel_setor,
            "categoria": r.categoria,
            "apontamento": r.apontamento,
            "acao_proposta": r.acao_proposta,
            "status": STATUS_MAP.get(r.status, r.status.title()),
            "prazo": "" if pd.isna(r.prazo) else r.prazo.strftime("%Y-%m-%d"),
            "conclusao": "" if pd.isna(r.conclusao) else r.conclusao.strftime("%Y-%m-%d"),
            "status_prazo": r.status_prazo,
            "prioridade": r.prioridade,
            "gut": int(r.gut),
            "contencao": bool(r.contencao),
            "indicador": r.indicador,
            "id_inspecao": None if pd.isna(r.ID_Inspeção) else int(r.ID_Inspeção),
            "num_participantes": 0 if pd.isna(r.num_participantes) else int(r.num_participantes),
        })

    # lista de inspeções (anonimizada)
    inspecoes = [
        {
            "id": int(r.ID_Inspeção),
            "data": r.data.strftime("%Y-%m-%d"),
            "setor_original": r.setor_original,
            "andar": r.andar,
            "ala": r.ala,
            "responsavel_acompanhou": r.responsavel_acompanhou,
            "num_participantes": int(r.num_participantes),
            "num_setores_presentes": int(r.num_setores_presentes),
            "apontamentos": sum(1 for l in linhas if l["id_inspecao"] == int(r.ID_Inspeção)),
        }
        for r in i.itertuples(index=False)
    ]

    payload = {
        "gerado_em": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
        "fonte": "inspecoes_gut.xlsx (abas: Planos classificados + Inspeções)",
        "anonimizado": True,
        "setores": sorted({l["setor"] for l in linhas}),
        "andares": sorted({l["andar"] for l in linhas if l["andar"]}),
        "linhas": linhas,
        "inspecoes": inspecoes,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "window.DASH = " + json.dumps(payload, ensure_ascii=False, default=str) + ";\n",
        encoding="utf-8",
    )

    total = len(linhas)
    concl = sum(1 for l in linhas if l["status"] == "Concluído")
    atras = sum(1 for l in linhas if l["status_prazo"] == "Atrasado")
    alta = sum(1 for l in linhas if l["prioridade"] == "Alta")
    print(f"[kpis] apontamentos: {total} | concluídos: {concl} | atrasados: {atras} | "
          f"prioridade alta: {alta} | inspeções: {len(inspecoes)} | sem vínculo: {sem_vinculo}")


if __name__ == "__main__":
    main()