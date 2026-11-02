"""Relatório em Markdown (para baixar na interface e guardar no GitHub)."""
from __future__ import annotations

from .gaps_roadmap import PlanoCarreira
from .motor_inferencia import MotorInferencia, ResultadoInferencia


def _tabela(cabecalho: list[str], linhas: list[list[str]]) -> str:
    def limpar(x: object) -> str:
        return str(x).replace("|", "/").replace("\n", " ")
    out = ["| " + " | ".join(cabecalho) + " |", "|" + "|".join("---" for _ in cabecalho) + "|"]
    out += ["| " + " | ".join(limpar(c) for c in l) + " |" for l in linhas]
    return "\n".join(out)


def relatorio_markdown(motor: MotorInferencia, resultado: ResultadoInferencia, plano: PlanoCarreira,
                       nome: str | None = None) -> str:
    a, r = plano.analise, plano.roadmap
    titulo = f"# Plano de carreira em TI{f' - {nome}' if nome else ''}"
    partes = [titulo, "", "## Ranking de compatibilidade (Top 3)", ""]
    partes.append(_tabela(["Posição", "Trilha", "Compatibilidade"],
                          [[i, t.nome, f"{t.percentual:.1f}%"] for i, t in enumerate(resultado.top, 1)]))
    if resultado.empates_parciais:
        partes += ["", "> Atenção: há empate parcial entre trilhas vizinhas; considere explorar ambas."]
    partes += ["", "### Por que essas trilhas?", ""]
    for t in resultado.top:
        partes += ["```", motor.explicar(t), "```", ""]
    partes += [f"## Trilha escolhida: {a.trilha_nome}", "",
               f"**Prontidão para Júnior:** {a.percentual:.1f}% - {a.classificacao}", ""]
    if a.essenciais_pendentes:
        partes += ["**Essenciais pendentes:** " + "; ".join(a.essenciais_pendentes), ""]
    partes += ["### Análise de gaps", "", _tabela(
        ["Habilidade", "Prioridade", "Seu nível", "Exigido", "Situação"],
        [[i.habilidade.nome, i.habilidade.prioridade, i.atual, i.habilidade.nivel_junior,
          "Atendida" if i.atendida else "Lacuna"] for i in a.itens]), ""]
    partes += [f"### Roadmap ({r.total_horas:.0f} h, ~{r.semanas} semanas)", ""]
    if not r.itens:
        partes += ["Nenhuma lacuna: foque em projetos de portfólio e candidaturas.", ""]
    for e in r.etapas:
        partes.append(f"**{e.titulo}** ({e.horas:.0f} h)")
        partes += [f"{i.ordem}. {i.habilidade.nome} (nível {i.de_nivel} → {i.para_nivel}, {i.horas:.0f} h) - "
                   f"estudar: {', '.join(i.habilidade.tecnologias)}" for i in e.itens]
        partes.append("")
    partes += ["### Certificações", ""]
    for c in r.certificacoes:
        quando = "agora" if c.disponivel_agora else f"depois (prontidão ≥ {c.certificacao.min_prontidao * 100:.0f}%)"
        partes.append(f"- **{c.certificacao.nome}** ({c.certificacao.emissor}) - {quando}. {c.certificacao.descricao}")
    partes += ["", "### Projetos para o portfólio no GitHub", ""]
    for p in r.projetos:
        extra = f" Treina: {', '.join(p.treina_lacunas)}." if p.treina_lacunas else ""
        partes.append(f"{p.ordem}. **{p.projeto.nome}** (nível {p.projeto.dificuldade}, {p.momento}) - "
                      f"{p.projeto.descricao}{extra}")
    partes += ["", "**Boas práticas de portfólio:**", ""] + [f"- {b}" for b in r.boas_praticas]
    return "\n".join(partes) + "\n"
