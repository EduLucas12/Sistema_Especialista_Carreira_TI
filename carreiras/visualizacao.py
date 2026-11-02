"""Tabelas (pandas) e gráficos (plotly) usados pela interface Streamlit.

Fica separado do app para poder ser testado sem abrir o navegador.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .gaps_roadmap import AnaliseGaps, Roadmap
from .motor_inferencia import ResultadoInferencia

COR_TOP = "#1f77b4"
COR_DEMAIS = "#b8c4d0"


def df_ranking(resultado: ResultadoInferencia) -> pd.DataFrame:
    """Todas as trilhas, da mais para a menos compatível."""
    top_ids = {r.trilha_id for r in resultado.top}
    return pd.DataFrame([{
        "Posição": i,
        "Trilha": r.nome,
        "Compatibilidade (%)": r.percentual,
        "Base (%)": round(r.base * 100, 1),
        "Regras (p.p.)": round(r.ajuste * 100, 1),
        "Top 3": "sim" if r.trilha_id in top_ids else "",
    } for i, r in enumerate(resultado.ranking, 1)])


def fig_barras(resultado: ResultadoInferencia) -> go.Figure:
    """Barras horizontais com a compatibilidade de todas as trilhas (Top 3 destacado)."""
    ranking = list(resultado.ranking)[::-1]  # a melhor fica no topo
    top_ids = {r.trilha_id for r in resultado.top}
    fig = go.Figure(go.Bar(
        x=[r.percentual for r in ranking],
        y=[r.nome for r in ranking],
        orientation="h",
        marker_color=[COR_TOP if r.trilha_id in top_ids else COR_DEMAIS for r in ranking],
        text=[f"{r.percentual:.1f}%" for r in ranking],
        textposition="outside",
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
    ))
    fig.update_layout(title="Compatibilidade por trilha", xaxis=dict(range=[0, 110], title="%"),
                      margin=dict(l=10, r=10, t=50, b=10), height=420)
    return fig


def fig_radar(resultado: ResultadoInferencia) -> go.Figure:
    """Radar com as 10 trilhas (ordem fixa por nome, para o formato ser comparável entre consultas)."""
    trilhas = sorted(resultado.ranking, key=lambda r: r.nome)
    nomes = [r.nome for r in trilhas] + [trilhas[0].nome]
    valores = [r.percentual for r in trilhas] + [trilhas[0].percentual]
    fig = go.Figure(go.Scatterpolar(r=valores, theta=nomes, fill="toself", name="Compatibilidade",
                                    line_color=COR_TOP, hovertemplate="%{theta}: %{r:.1f}%<extra></extra>"))
    fig.update_layout(title="Perfil de compatibilidade (radar)", showlegend=False,
                      polar=dict(radialaxis=dict(range=[0, 100], ticksuffix="%")),
                      margin=dict(l=150, r=130, t=60, b=30), height=460)
    return fig


def fig_prontidao(analise: AnaliseGaps) -> go.Figure:
    """Barras com nível atual x exigido por habilidade."""
    itens = list(analise.itens)[::-1]
    fig = go.Figure()
    fig.add_bar(y=[i.habilidade.nome for i in itens], x=[i.atual for i in itens], orientation="h",
                name="Seu nível", marker_color=COR_TOP)
    fig.add_bar(y=[i.habilidade.nome for i in itens], x=[i.habilidade.nivel_junior for i in itens],
                orientation="h", name="Exigido para Júnior", marker_color=COR_DEMAIS)
    fig.update_layout(barmode="group", title="Seu nível x nível Júnior", xaxis=dict(range=[0, 3], dtick=1),
                      margin=dict(l=10, r=10, t=50, b=10), height=max(320, 38 * len(itens)),
                      legend=dict(orientation="h", y=-0.1))
    return fig


def df_gaps(analise: AnaliseGaps) -> pd.DataFrame:
    return pd.DataFrame([{
        "Habilidade": i.habilidade.nome,
        "Prioridade": i.habilidade.prioridade,
        "Seu nível": i.atual,
        "Exigido (Júnior)": i.habilidade.nivel_junior,
        "Gap": i.gap,
        "Situação": "Atendida" if i.atendida else "Lacuna",
        "Origem": "estimado" if i.estimado else "informado",
    } for i in analise.itens])


def df_roadmap(roadmap: Roadmap) -> pd.DataFrame:
    return pd.DataFrame([{
        "Ordem": i.ordem,
        "Etapa": e.titulo,
        "Habilidade": i.habilidade.nome,
        "De → Para": f"{i.de_nivel} → {i.para_nivel}",
        "Horas": round(i.horas),
        "Estudar": ", ".join(i.habilidade.tecnologias),
    } for e in roadmap.etapas for i in e.itens])


def df_certificacoes(roadmap: Roadmap) -> pd.DataFrame:
    return pd.DataFrame([{
        "Certificação": c.certificacao.nome,
        "Emissor": c.certificacao.emissor,
        "Quando": "Agora" if c.disponivel_agora else f"Depois (prontidão ≥ {c.certificacao.min_prontidao * 100:.0f}%)",
        "Sobre": c.certificacao.descricao,
    } for c in roadmap.certificacoes])


def df_projetos(roadmap: Roadmap) -> pd.DataFrame:
    return pd.DataFrame([{
        "Ordem": p.ordem,
        "Projeto": p.projeto.nome,
        "Nível": p.projeto.dificuldade,
        "Momento": p.momento.capitalize(),
        "Descrição": p.projeto.descricao,
        "Treina lacunas": ", ".join(p.treina_lacunas),
    } for p in roadmap.projetos])
