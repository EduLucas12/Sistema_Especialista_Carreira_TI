"""Motor de Inferência: pontuação ponderada com regras de penalidade/bônus.

Componentes (aulas de Sistemas Especialistas):
- Memória de Trabalho  -> ``MemoriaTrabalho`` (respostas da sessão de consulta)
- Base de Conhecimento -> ``BaseConhecimento`` (carregada do JSON)
- Máquina de Inferência-> ``MotorInferencia.inferir``
- Explicador           -> ``MotorInferencia.explicar`` (por quê / como)

Fórmula (ver docs/fase1_engenharia_conhecimento.md):
    n          = (resposta - min) / (max - min)                 # 0..1
    base       = Σ(peso · peso_etapa · n) / Σ(peso · peso_etapa)
                 (pergunta não respondida = sem informação -> n neutro = 0.5)
    ajuste     = clamp(Σ ajustes das regras ativas, -teto, +teto)
    compat     = clamp(base + ajuste, 0, 1)
"""
from __future__ import annotations

import operator
from dataclasses import dataclass, field

from .base_conhecimento import BaseConhecimento, Regra, carregar_base

NEUTRO = 0.5  # valor normalizado atribuído a perguntas não respondidas

_OPS = {"<=": operator.le, ">=": operator.ge, "<": operator.lt,
        ">": operator.gt, "==": operator.eq, "!=": operator.ne}


class RespostaInvalidaError(ValueError):
    """Resposta fora da escala, pergunta desconhecida ou tipo inválido."""


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# --------------------------------------------------------------------------- #
# Memória de trabalho
# --------------------------------------------------------------------------- #
@dataclass
class MemoriaTrabalho:
    """Fatos da sessão: respostas Likert do usuário (pergunta_id -> int)."""
    respostas: dict[str, int] = field(default_factory=dict)

    def responder(self, base: BaseConhecimento, pergunta_id: str, valor: int) -> None:
        if pergunta_id not in base.perguntas:
            raise RespostaInvalidaError(f"Pergunta desconhecida: '{pergunta_id}'")
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise RespostaInvalidaError(f"Resposta de '{pergunta_id}' deve ser inteira, recebido {valor!r}")
        if not base.escala_min <= valor <= base.escala_max:
            raise RespostaInvalidaError(
                f"Resposta de '{pergunta_id}' fora da escala {base.escala_min}-{base.escala_max}: {valor}")
        self.respostas[pergunta_id] = valor

    @classmethod
    def de_dict(cls, base: BaseConhecimento, respostas: dict[str, int]) -> "MemoriaTrabalho":
        mem = cls()
        for pid, v in respostas.items():
            mem.responder(base, pid, v)
        return mem


# --------------------------------------------------------------------------- #
# Resultados
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Contribuicao:
    pergunta_id: str
    rotulo: str
    resposta: int
    peso_efetivo: float      # peso da pergunta × peso da etapa
    normalizada: float       # 0..1
    pontos: float            # peso_efetivo × normalizada
    perda: float             # peso_efetivo × (1 - normalizada): o que "faltou"


@dataclass(frozen=True)
class RegraAtiva:
    id: str
    tipo: str
    descricao: str
    ajuste: float            # com sinal (penalidade < 0, bônus > 0)


@dataclass(frozen=True)
class ResultadoTrilha:
    trilha_id: str
    nome: str
    base: float              # 0..1, antes das regras
    ajuste: float            # soma (com teto) das regras ativas
    compatibilidade: float   # 0..1, final
    contribuicoes: tuple[Contribuicao, ...]
    regras_ativas: tuple[RegraAtiva, ...]

    @property
    def percentual(self) -> float:
        return round(self.compatibilidade * 100, 1)


@dataclass(frozen=True)
class ResultadoInferencia:
    ranking: tuple[ResultadoTrilha, ...]   # todas as trilhas, da melhor para a pior
    top: tuple[ResultadoTrilha, ...]       # Top N
    empates_parciais: tuple[tuple[str, str], ...]  # pares consecutivos no Top N+1 com diferença <= limiar

    def por_id(self, trilha_id: str) -> ResultadoTrilha:
        return next(r for r in self.ranking if r.trilha_id == trilha_id)


# --------------------------------------------------------------------------- #
# Motor
# --------------------------------------------------------------------------- #
class MotorInferencia:
    def __init__(self, base: BaseConhecimento | None = None):
        self.base = base or carregar_base()

    # --- API principal ---------------------------------------------------- #
    def inferir(self, memoria: MemoriaTrabalho | dict[str, int]) -> ResultadoInferencia:
        if isinstance(memoria, dict):
            memoria = MemoriaTrabalho.de_dict(self.base, memoria)
        if not memoria.respostas:
            raise RespostaInvalidaError("Nenhuma pergunta respondida: não há fatos para inferir.")

        resultados = [self._pontuar_trilha(tid, memoria) for tid in self.base.trilhas]
        # Ordenação determinística: compatibilidade, depois base, depois nome.
        resultados.sort(key=lambda r: (-r.compatibilidade, -r.base, r.nome))

        top_n = self.base.pontuacao["top_n"]
        limiar = self.base.pontuacao["limiar_empate_pontos_percentuais"] / 100
        considerados = resultados[: top_n + 1]
        empates = tuple(
            (a.trilha_id, b.trilha_id)
            for a, b in zip(considerados, considerados[1:])
            if a.compatibilidade - b.compatibilidade <= limiar + 1e-12
        )
        return ResultadoInferencia(tuple(resultados), tuple(resultados[:top_n]), empates)

    # --- Passos internos ------------------------------------------------- #
    def _peso_etapa(self, pergunta_id: str) -> float:
        etapa = self.base.perguntas[pergunta_id].etapa
        return float(self.base.etapas[etapa].get("peso_etapa", 1.0))

    def _normalizar(self, resposta: int) -> float:
        return (resposta - self.base.escala_min) / (self.base.escala_max - self.base.escala_min)

    def _pontuar_trilha(self, trilha_id: str, memoria: MemoriaTrabalho) -> ResultadoTrilha:
        trilha = self.base.trilhas[trilha_id]
        contribs: list[Contribuicao] = []   # só perguntas respondidas (usadas na explicação)
        numerador = denominador = 0.0
        for pid, peso in trilha.pesos.items():
            pe = peso * self._peso_etapa(pid)
            if pid in memoria.respostas:
                r = memoria.respostas[pid]
                n = self._normalizar(r)
                contribs.append(Contribuicao(pid, self.base.perguntas[pid].rotulo, r, pe, n, pe * n, pe * (1 - n)))
            else:
                n = NEUTRO  # sem informação: nem a favor nem contra
            numerador += pe * n
            denominador += pe
        base = numerador / denominador if denominador > 0 else 0.0

        ativas = tuple(self._regras_ativas(trilha_id, memoria))
        teto = self.base.pontuacao["ajuste_maximo_total"]
        ajuste = _clamp(sum(a.ajuste for a in ativas), -teto, teto)
        compat = _clamp(base + ajuste, 0.0, 1.0)
        return ResultadoTrilha(trilha_id, trilha.nome, base, ajuste, compat, tuple(contribs), ativas)

    def _regras_ativas(self, trilha_id: str, memoria: MemoriaTrabalho):
        for regra in self.base.regras:
            if trilha_id not in regra.ajuste_por_trilha:
                continue
            if not self._regra_dispara(regra, memoria):
                continue
            sinal = -1 if regra.tipo == "penalidade" else 1
            yield RegraAtiva(regra.id, regra.tipo, regra.descricao, sinal * regra.ajuste_por_trilha[trilha_id])

    @staticmethod
    def _regra_dispara(regra: Regra, memoria: MemoriaTrabalho) -> bool:
        """E lógico das condições; condição sobre pergunta não respondida é falsa."""
        for c in regra.condicoes:
            resp = memoria.respostas.get(c.pergunta)
            if resp is None or not _OPS[c.op](resp, c.valor):
                return False
        return True

    # --- Explicador ------------------------------------------------------- #
    def explicar(self, resultado: ResultadoTrilha, n_destaques: int = 3) -> str:
        """Responde "por quê?" e "como?": fatos que mais ajudaram, o que faltou e regras acionadas."""
        linhas = [f"{resultado.nome}: {resultado.percentual:.1f}% "
                  f"(base {resultado.base * 100:.1f}% {resultado.ajuste * 100:+.1f} p.p. das regras)"]
        fortes = sorted((c for c in resultado.contribuicoes if c.normalizada >= 0.5),
                        key=lambda c: -c.pontos)[:n_destaques]
        if fortes:
            linhas.append("  A favor: " + "; ".join(f"{c.rotulo} (resposta {c.resposta}/{self.base.escala_max})" for c in fortes))
        fracos = sorted((c for c in resultado.contribuicoes if c.normalizada < 0.5),
                        key=lambda c: -c.perda)[:n_destaques]
        if fracos:
            linhas.append("  Contra: " + "; ".join(f"{c.rotulo} (resposta {c.resposta}/{self.base.escala_max})" for c in fracos))
        for r in resultado.regras_ativas:
            rot = "Penalidade" if r.tipo == "penalidade" else "Bônus"
            linhas.append(f"  {rot} {r.id} ({r.ajuste * 100:+.0f} p.p.): {r.descricao}")
        return "\n".join(linhas)

    def relatorio(self, resultado: ResultadoInferencia) -> str:
        blocos = []
        for i, r in enumerate(resultado.top, 1):
            blocos.append(f"{i}º {self.explicar(r)}")
        if resultado.empates_parciais:
            nomes = [(self.base.trilhas[a].nome, self.base.trilhas[b].nome) for a, b in resultado.empates_parciais]
            lim = self.base.pontuacao["limiar_empate_pontos_percentuais"]
            blocos.append("Atenção - empate parcial (diferença <= %.0f p.p.): " % lim
                          + "; ".join(f"{a} ≈ {b}" for a, b in nomes))
        return "\n\n".join(blocos)
