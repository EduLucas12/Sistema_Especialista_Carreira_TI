"""Fase 3: análise de gaps (skill gap) e geração de roadmap personalizado.

Cruza a trilha recomendada pelo motor de inferência com o nível atual do usuário:
- Gap por habilidade  = max(0, nível exigido para Júnior - nível atual)
- Prontidão Júnior    = Σ(peso · min(atual, exigido)) / Σ(peso · exigido)
- Roadmap             = habilidades com gap, em ordem de pré-requisitos, agrupadas por bloco
                        (fundamentos -> ferramentas -> prática), com horas e semanas estimadas
- Certificações       = liberadas conforme a prontidão
- Projetos de portfólio = do mais simples ao mais complexo, destacando as lacunas que treinam

O conhecimento (habilidades, certificações, projetos) vem de data/habilidades_roadmap.json.
"""
from __future__ import annotations

import heapq
import json
import math
from dataclasses import dataclass
from pathlib import Path

from .base_conhecimento import BaseConhecimento, carregar_base

CAMINHO_HABILIDADES = Path(__file__).resolve().parent.parent / "data" / "habilidades_roadmap.json"
NIVEL_MIN, NIVEL_MAX = 0, 3


class HabilidadesInvalidasError(ValueError):
    """JSON de habilidades/roadmap inconsistente."""


class EntradaInvalidaError(ValueError):
    """Perfil ou avaliação do usuário inválidos."""


# --------------------------------------------------------------------------- #
# Base de habilidades
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Habilidade:
    id: str
    nome: str
    prioridade: str
    nivel_junior: int
    horas_por_nivel: float
    pre_requisitos: tuple[str, ...]
    bloco: str
    tecnologias: tuple[str, ...]


@dataclass(frozen=True)
class Certificacao:
    nome: str
    emissor: str
    min_prontidao: float
    descricao: str


@dataclass(frozen=True)
class Projeto:
    nome: str
    dificuldade: int
    descricao: str
    habilidades: tuple[str, ...]


@dataclass(frozen=True)
class ConhecimentoTrilha:
    habilidades: dict[str, Habilidade]
    certificacoes: tuple[Certificacao, ...]
    projetos: tuple[Projeto, ...]


@dataclass(frozen=True)
class BaseHabilidades:
    niveis: dict[int, str]
    pesos_prioridade: dict[str, int]
    blocos: tuple[str, ...]
    titulos_blocos: dict[str, str]
    estimativa: dict[str, dict[str, int]]
    limiares: dict[str, float]
    boas_praticas: tuple[str, ...]
    trilhas: dict[str, ConhecimentoTrilha]


def _erro(msg: str) -> None:
    raise HabilidadesInvalidasError(msg)


def carregar_habilidades(caminho: str | Path = CAMINHO_HABILIDADES,
                         base: BaseConhecimento | None = None) -> BaseHabilidades:
    with open(caminho, encoding="utf-8") as f:
        bruto = json.load(f)
    return validar_habilidades(bruto, base or carregar_base())


def validar_habilidades(bruto: dict, base: BaseConhecimento) -> BaseHabilidades:
    pesos = dict(bruto["prioridades"])
    blocos = tuple(b["id"] for b in bruto["blocos"])
    idx_bloco = {b: i for i, b in enumerate(blocos)}
    niveis = {int(k): v for k, v in bruto["niveis_habilidade"].items()}
    if set(niveis) != set(range(NIVEL_MIN, NIVEL_MAX + 1)):
        _erro("niveis_habilidade deve cobrir 0 a 3")

    est = bruto["estimativa_por_experiencia"]
    for exp, por_bloco in est.items():
        if set(por_bloco) != set(blocos) or any(not NIVEL_MIN <= v <= NIVEL_MAX for v in por_bloco.values()):
            _erro(f"estimativa_por_experiencia inválida para '{exp}'")
    lim = bruto["prontidao"]
    if not 0 < lim["em_formacao"] < lim["quase_la"] < lim["apto"] <= 1:
        _erro("prontidao: use em_formacao < quase_la < apto, todos em (0, 1]")

    if set(bruto["trilhas"]) != set(base.trilhas):
        _erro("As trilhas de habilidades devem ser exatamente as mesmas de regras_carreiras.json")

    trilhas: dict[str, ConhecimentoTrilha] = {}
    for tid, t in bruto["trilhas"].items():
        habs: dict[str, Habilidade] = {}
        for h in t["habilidades"]:
            if h["id"] in habs:
                _erro(f"{tid}: habilidade duplicada '{h['id']}'")
            if h["prioridade"] not in pesos:
                _erro(f"{tid}/{h['id']}: prioridade inválida '{h['prioridade']}'")
            if h["bloco"] not in idx_bloco:
                _erro(f"{tid}/{h['id']}: bloco inválido '{h['bloco']}'")
            if not 1 <= h["nivel_junior"] <= NIVEL_MAX:
                _erro(f"{tid}/{h['id']}: nivel_junior deve estar entre 1 e {NIVEL_MAX}")
            if h["horas_por_nivel"] <= 0:
                _erro(f"{tid}/{h['id']}: horas_por_nivel deve ser positivo")
            habs[h["id"]] = Habilidade(h["id"], h["nome"], h["prioridade"], h["nivel_junior"],
                                       float(h["horas_por_nivel"]), tuple(h["pre_requisitos"]),
                                       h["bloco"], tuple(h["tecnologias"]))
        if not habs:
            _erro(f"{tid}: sem habilidades")
        for h in habs.values():
            for p in h.pre_requisitos:
                if p not in habs or p == h.id:
                    _erro(f"{tid}/{h.id}: pré-requisito inválido '{p}'")
                if idx_bloco[habs[p].bloco] > idx_bloco[h.bloco]:
                    _erro(f"{tid}/{h.id}: pré-requisito '{p}' está em bloco posterior")
        _checar_ciclos(tid, habs)

        certs = tuple(Certificacao(c["nome"], c["emissor"], float(c["min_prontidao"]), c["descricao"])
                      for c in t["certificacoes"])
        if any(not 0 <= c.min_prontidao <= 1 for c in certs):
            _erro(f"{tid}: min_prontidao deve estar em [0, 1]")
        projs = tuple(Projeto(p["nome"], p["dificuldade"], p["descricao"], tuple(p["habilidades"]))
                      for p in t["projetos"])
        for p in projs:
            if not 1 <= p.dificuldade <= 3:
                _erro(f"{tid}/{p.nome}: dificuldade deve estar entre 1 e 3")
            for hid in p.habilidades:
                if hid not in habs:
                    _erro(f"{tid}/{p.nome}: habilidade inexistente '{hid}'")
        if not certs or not projs:
            _erro(f"{tid}: precisa de certificações e projetos")
        trilhas[tid] = ConhecimentoTrilha(habs, certs, projs)

    return BaseHabilidades(niveis, pesos, blocos, {b["id"]: b["titulo"] for b in bruto["blocos"]},
                           est, dict(lim), tuple(bruto["boas_praticas_portfolio"]), trilhas)


def _checar_ciclos(tid: str, habs: dict[str, Habilidade]) -> None:
    estado: dict[str, int] = {}

    def visita(h: str) -> None:
        if estado.get(h) == 1:
            _erro(f"{tid}: ciclo de pré-requisitos envolvendo '{h}'")
        if estado.get(h) == 2:
            return
        estado[h] = 1
        for p in habs[h].pre_requisitos:
            visita(p)
        estado[h] = 2

    for h in habs:
        visita(h)


# --------------------------------------------------------------------------- #
# Entrada do usuário
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PerfilUsuario:
    """Dados do Passo 1 (perfil pessoal)."""
    nivel_experiencia: str = "iniciante"
    horas_semanais: float = 6.0
    nome: str | None = None


# --------------------------------------------------------------------------- #
# Análise de gaps
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class GapHabilidade:
    habilidade: Habilidade
    atual: int
    estimado: bool   # True = nível inferido do perfil; False = informado pelo usuário
    gap: int

    @property
    def atendida(self) -> bool:
        return self.gap == 0


CLASSIFICACOES = {
    "apto": "Pronto para vagas Júnior",
    "quase_la": "Quase lá",
    "em_formacao": "Em formação",
    "inicio": "Início da jornada",
}


@dataclass(frozen=True)
class AnaliseGaps:
    trilha_id: str
    trilha_nome: str
    itens: tuple[GapHabilidade, ...]
    prontidao: float                       # 0..1
    classificacao_id: str
    essenciais_pendentes: tuple[str, ...]  # nomes das habilidades essenciais com gap

    @property
    def percentual(self) -> float:
        return round(self.prontidao * 100, 1)

    @property
    def classificacao(self) -> str:
        return CLASSIFICACOES[self.classificacao_id]

    @property
    def lacunas(self) -> tuple[GapHabilidade, ...]:
        return tuple(i for i in self.itens if i.gap > 0)

    def por_id(self, habilidade_id: str) -> GapHabilidade:
        return next(i for i in self.itens if i.habilidade.id == habilidade_id)


# --------------------------------------------------------------------------- #
# Roadmap
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ItemRoadmap:
    ordem: int
    habilidade: Habilidade
    de_nivel: int
    para_nivel: int
    horas: float


@dataclass(frozen=True)
class EtapaRoadmap:
    bloco_id: str
    titulo: str
    itens: tuple[ItemRoadmap, ...]

    @property
    def horas(self) -> float:
        return sum(i.horas for i in self.itens)


@dataclass(frozen=True)
class CertificacaoSugerida:
    certificacao: Certificacao
    disponivel_agora: bool


@dataclass(frozen=True)
class ProjetoSugerido:
    ordem: int
    projeto: Projeto
    momento: str                      # "agora" | "depois"
    treina_lacunas: tuple[str, ...]   # nomes das habilidades com gap que o projeto exercita


@dataclass(frozen=True)
class Roadmap:
    trilha_id: str
    trilha_nome: str
    etapas: tuple[EtapaRoadmap, ...]
    total_horas: float
    semanas: int
    certificacoes: tuple[CertificacaoSugerida, ...]
    projetos: tuple[ProjetoSugerido, ...]
    boas_praticas: tuple[str, ...]

    @property
    def itens(self) -> tuple[ItemRoadmap, ...]:
        return tuple(i for e in self.etapas for i in e.itens)


@dataclass(frozen=True)
class PlanoCarreira:
    analise: AnaliseGaps
    roadmap: Roadmap


# --------------------------------------------------------------------------- #
# Serviço
# --------------------------------------------------------------------------- #
class ConsultorGaps:
    def __init__(self, habilidades: BaseHabilidades | None = None, base: BaseConhecimento | None = None):
        self.base = base or carregar_base()
        self.hab = habilidades or carregar_habilidades(base=self.base)

    # --- validação -------------------------------------------------------- #
    def _validar_perfil(self, perfil: PerfilUsuario) -> None:
        if perfil.nivel_experiencia not in self.hab.estimativa:
            raise EntradaInvalidaError(
                f"nivel_experiencia deve ser um de {sorted(self.hab.estimativa)}, recebido '{perfil.nivel_experiencia}'")
        h = perfil.horas_semanais
        if isinstance(h, bool) or not isinstance(h, (int, float)) or not 0 < h <= 80:
            raise EntradaInvalidaError(f"horas_semanais deve estar entre 0 (exclusivo) e 80, recebido {h!r}")

    def _trilha(self, trilha_id: str) -> ConhecimentoTrilha:
        if trilha_id not in self.hab.trilhas:
            raise EntradaInvalidaError(f"Trilha desconhecida: '{trilha_id}'")
        return self.hab.trilhas[trilha_id]

    # --- gaps ------------------------------------------------------------- #
    def analisar_gaps(self, trilha_id: str, perfil: PerfilUsuario,
                      avaliacao: dict[str, int] | None = None) -> AnaliseGaps:
        """Compara o nível atual (informado ou estimado) com o exigido para Júnior."""
        self._validar_perfil(perfil)
        conhecimento = self._trilha(trilha_id)
        avaliacao = avaliacao or {}
        for hid, nivel in avaliacao.items():
            if hid not in conhecimento.habilidades:
                raise EntradaInvalidaError(f"Habilidade '{hid}' não existe na trilha '{trilha_id}'")
            if isinstance(nivel, bool) or not isinstance(nivel, int) or not NIVEL_MIN <= nivel <= NIVEL_MAX:
                raise EntradaInvalidaError(
                    f"Nível de '{hid}' deve ser inteiro de {NIVEL_MIN} a {NIVEL_MAX}, recebido {nivel!r}")

        estimativa = self.hab.estimativa[perfil.nivel_experiencia]
        itens = []
        for h in conhecimento.habilidades.values():
            if h.id in avaliacao:
                atual, estimado = avaliacao[h.id], False
            else:
                atual, estimado = estimativa[h.bloco], True
            itens.append(GapHabilidade(h, atual, estimado, max(0, h.nivel_junior - atual)))

        pesos = self.hab.pesos_prioridade
        total = sum(pesos[i.habilidade.prioridade] * i.habilidade.nivel_junior for i in itens)
        obtido = sum(pesos[i.habilidade.prioridade] * min(i.atual, i.habilidade.nivel_junior) for i in itens)
        prontidao = obtido / total
        essenciais = tuple(i.habilidade.nome for i in itens
                           if i.gap > 0 and i.habilidade.prioridade == "essencial")
        lim = self.hab.limiares
        if prontidao >= lim["apto"] and not essenciais:
            classe = "apto"
        elif prontidao >= lim["quase_la"]:
            classe = "quase_la"
        elif prontidao >= lim["em_formacao"]:
            classe = "em_formacao"
        else:
            classe = "inicio"
        return AnaliseGaps(trilha_id, self.base.trilhas[trilha_id].nome, tuple(itens),
                           prontidao, classe, essenciais)

    # --- roadmap ---------------------------------------------------------- #
    def gerar_roadmap(self, analise: AnaliseGaps, perfil: PerfilUsuario) -> Roadmap:
        self._validar_perfil(perfil)
        conhecimento = self._trilha(analise.trilha_id)
        pesos = self.hab.pesos_prioridade
        idx_bloco = {b: i for i, b in enumerate(self.hab.blocos)}
        lacunas = {i.habilidade.id: i for i in analise.lacunas}

        # Ordenação topológica (Kahn) só entre habilidades com gap; pré-requisito sem gap já está atendido.
        pendentes = {hid: {p for p in g.habilidade.pre_requisitos if p in lacunas} for hid, g in lacunas.items()}
        dependentes: dict[str, list[str]] = {hid: [] for hid in lacunas}
        for hid, pres in pendentes.items():
            for p in pres:
                dependentes[p].append(hid)

        def chave(hid: str):
            g = lacunas[hid]
            h = g.habilidade
            return (idx_bloco[h.bloco], -pesos[h.prioridade] * g.gap, h.nome)

        fila = [(chave(h), h) for h, pres in pendentes.items() if not pres]
        heapq.heapify(fila)
        ordenados: list[str] = []
        while fila:
            _, hid = heapq.heappop(fila)
            ordenados.append(hid)
            for d in dependentes[hid]:
                pendentes[d].discard(hid)
                if not pendentes[d]:
                    heapq.heappush(fila, (chave(d), d))

        itens = []
        for ordem, hid in enumerate(ordenados, 1):
            g = lacunas[hid]
            itens.append(ItemRoadmap(ordem, g.habilidade, g.atual, g.habilidade.nivel_junior,
                                     g.habilidade.horas_por_nivel * g.gap))
        etapas = []
        for bloco in self.hab.blocos:
            do_bloco = tuple(i for i in itens if i.habilidade.bloco == bloco)
            if do_bloco:
                etapas.append(EtapaRoadmap(bloco, self.hab.titulos_blocos[bloco], do_bloco))

        total = sum(i.horas for i in itens)
        semanas = math.ceil(total / perfil.horas_semanais) if total else 0

        certs = tuple(CertificacaoSugerida(c, analise.prontidao >= c.min_prontidao)
                      for c in sorted(conhecimento.certificacoes, key=lambda c: c.min_prontidao))

        if analise.prontidao < 0.5:
            dificuldade_agora = 1
        elif analise.prontidao < 0.8:
            dificuldade_agora = 2
        else:
            dificuldade_agora = 3
        projetos = []
        for ordem, p in enumerate(sorted(conhecimento.projetos, key=lambda p: (p.dificuldade, p.nome)), 1):
            treina = tuple(conhecimento.habilidades[h].nome for h in p.habilidades if h in lacunas)
            projetos.append(ProjetoSugerido(ordem, p, "agora" if p.dificuldade <= dificuldade_agora else "depois", treina))

        return Roadmap(analise.trilha_id, analise.trilha_nome, tuple(etapas), total, semanas,
                       certs, tuple(projetos), self.hab.boas_praticas)

    # --- fachada ---------------------------------------------------------- #
    def plano(self, trilha_id: str, perfil: PerfilUsuario, avaliacao: dict[str, int] | None = None) -> PlanoCarreira:
        analise = self.analisar_gaps(trilha_id, perfil, avaliacao)
        return PlanoCarreira(analise, self.gerar_roadmap(analise, perfil))


# --------------------------------------------------------------------------- #
# Texto para terminal (a interface Streamlit usa as mesmas estruturas na Fase 4)
# --------------------------------------------------------------------------- #
def formatar_plano(plano: PlanoCarreira, niveis: dict[int, str] | None = None) -> str:
    a, r = plano.analise, plano.roadmap
    linhas = [f"=== Plano para {a.trilha_nome} ===",
              f"Prontidão para Júnior: {a.percentual:.1f}% - {a.classificacao}"]
    if a.essenciais_pendentes:
        linhas.append("Essenciais pendentes: " + "; ".join(a.essenciais_pendentes))
    linhas.append("\n-- Análise de gaps --")
    for i in a.itens:
        h = i.habilidade
        marca = "ok " if i.atendida else "GAP"
        origem = "estimado" if i.estimado else "informado"
        linhas.append(f"[{marca}] {h.nome} ({h.prioridade}): nível {i.atual}/{h.nivel_junior} ({origem})")
    linhas.append(f"\n-- Roadmap: {r.total_horas:.0f} h (~{r.semanas} semanas) --")
    if not r.itens:
        linhas.append("Nenhuma lacuna: foque em projetos de portfólio e candidaturas.")
    for e in r.etapas:
        linhas.append(f"{e.titulo} ({e.horas:.0f} h)")
        for i in e.itens:
            linhas.append(f"  {i.ordem}. {i.habilidade.nome}: nível {i.de_nivel} -> {i.para_nivel} "
                          f"({i.horas:.0f} h) | estudar: {', '.join(i.habilidade.tecnologias)}")
    linhas.append("\n-- Certificações --")
    for c in r.certificacoes:
        quando = "agora" if c.disponivel_agora else f"depois (prontidão >= {c.certificacao.min_prontidao * 100:.0f}%)"
        linhas.append(f"  {c.certificacao.nome} [{c.certificacao.emissor}] - {quando}: {c.certificacao.descricao}")
    linhas.append("\n-- Projetos para o portfólio no GitHub --")
    for p in r.projetos:
        extra = f" | treina: {', '.join(p.treina_lacunas)}" if p.treina_lacunas else ""
        linhas.append(f"  {p.ordem}. {p.projeto.nome} (nível {p.projeto.dificuldade}, {p.momento}): "
                      f"{p.projeto.descricao}{extra}")
    linhas.append("Boas práticas: " + "; ".join(r.boas_praticas))
    return "\n".join(linhas)
