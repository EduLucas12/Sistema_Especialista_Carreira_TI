"""Carregamento e validação da Base de Conhecimento (regras_carreiras.json).

A base fica FORA do código (desacoplamento exigido no enunciado). Este módulo
apenas lê o JSON, valida a consistência e expõe estruturas tipadas para o
motor de inferência (Fase 2).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

CAMINHO_PADRAO = Path(__file__).resolve().parent.parent / "data" / "regras_carreiras.json"
OPERADORES = {"<=", ">=", "<", ">", "==", "!="}
TIPOS_REGRA = {"penalidade", "bonus"}


class BaseInvalidaError(ValueError):
    """Levantada quando o JSON da base de conhecimento é inconsistente."""


@dataclass(frozen=True)
class Pergunta:
    id: str
    etapa: str
    texto: str
    rotulo: str


@dataclass(frozen=True)
class Trilha:
    id: str
    nome: str
    descricao: str
    pesos: dict[str, float]  # pergunta_id -> peso (perguntas ausentes = 0)


@dataclass(frozen=True)
class Condicao:
    pergunta: str
    op: str
    valor: int


@dataclass(frozen=True)
class Regra:
    id: str
    tipo: str  # "penalidade" | "bonus"
    descricao: str
    condicoes: tuple[Condicao, ...]  # todas devem ser verdadeiras (E lógico)
    ajuste_por_trilha: dict[str, float]  # valores positivos; o tipo define o sinal


@dataclass(frozen=True)
class BaseConhecimento:
    metadados: dict
    escala_min: int
    escala_max: int
    rotulos_escala: dict[int, str]
    etapas: dict[str, dict]
    perfil: list[dict]
    pontuacao: dict
    perguntas: dict[str, Pergunta]
    trilhas: dict[str, Trilha]
    regras: list[Regra] = field(default_factory=list)

    def perguntas_da_etapa(self, etapa: str) -> list[Pergunta]:
        return [p for p in self.perguntas.values() if p.etapa == etapa]


def _erro(msg: str) -> None:
    raise BaseInvalidaError(msg)


def carregar_base(caminho: str | Path = CAMINHO_PADRAO) -> BaseConhecimento:
    """Lê o JSON, valida e devolve a base. Levanta BaseInvalidaError se houver problema."""
    with open(caminho, encoding="utf-8") as f:
        bruto = json.load(f)
    return validar_e_construir(bruto)


def validar_e_construir(bruto: dict) -> BaseConhecimento:
    for chave in ("metadados", "escala_likert", "etapas", "perfil", "pontuacao",
                  "perguntas", "trilhas", "regras"):
        if chave not in bruto:
            _erro(f"Chave obrigatória ausente: '{chave}'")

    esc = bruto["escala_likert"]
    emin, emax = esc["minimo"], esc["maximo"]
    if emin >= emax:
        _erro("escala_likert.minimo deve ser menor que maximo")
    rotulos = {int(k): v for k, v in esc["rotulos"].items()}
    if set(rotulos) != set(range(emin, emax + 1)):
        _erro("escala_likert.rotulos deve ter um rótulo para cada valor da escala")

    etapas = {e["id"]: e for e in bruto["etapas"]}
    if len(etapas) != len(bruto["etapas"]):
        _erro("Etapas com id duplicado")

    perguntas: dict[str, Pergunta] = {}
    for p in bruto["perguntas"]:
        if p["id"] in perguntas:
            _erro(f"Pergunta duplicada: {p['id']}")
        if p["etapa"] not in etapas or not etapas[p["etapa"]].get("pontua"):
            _erro(f"Pergunta '{p['id']}' aponta para etapa inexistente ou que não pontua: {p['etapa']}")
        perguntas[p["id"]] = Pergunta(p["id"], p["etapa"], p["texto"], p["rotulo"])

    trilhas: dict[str, Trilha] = {}
    for t in bruto["trilhas"]:
        if t["id"] in trilhas:
            _erro(f"Trilha duplicada: {t['id']}")
        for pid, peso in t["pesos"].items():
            if pid not in perguntas:
                _erro(f"Trilha '{t['id']}' referencia pergunta inexistente: {pid}")
            if not isinstance(peso, (int, float)) or peso < 0:
                _erro(f"Peso inválido em '{t['id']}'/{pid}: {peso}")
        if sum(t["pesos"].values()) <= 0:
            _erro(f"Trilha '{t['id']}' não tem nenhum peso positivo")
        trilhas[t["id"]] = Trilha(t["id"], t["nome"], t["descricao"], dict(t["pesos"]))
    if len(trilhas) != 10:
        _erro(f"O escopo exige 10 trilhas, encontradas {len(trilhas)}")

    sem_peso = [pid for pid in perguntas if not any(pid in t.pesos for t in trilhas.values())]
    if sem_peso:
        _erro(f"Perguntas sem peso em nenhuma trilha: {sem_peso}")

    regras: list[Regra] = []
    ids_regras: set[str] = set()
    for r in bruto["regras"]:
        if r["id"] in ids_regras:
            _erro(f"Regra duplicada: {r['id']}")
        ids_regras.add(r["id"])
        if r["tipo"] not in TIPOS_REGRA:
            _erro(f"Regra {r['id']}: tipo inválido '{r['tipo']}'")
        if not r["condicoes"]:
            _erro(f"Regra {r['id']}: sem condições")
        conds = []
        for c in r["condicoes"]:
            if c["pergunta"] not in perguntas:
                _erro(f"Regra {r['id']}: pergunta inexistente '{c['pergunta']}'")
            if c["op"] not in OPERADORES:
                _erro(f"Regra {r['id']}: operador inválido '{c['op']}'")
            if not emin <= c["valor"] <= emax:
                _erro(f"Regra {r['id']}: valor fora da escala ({c['valor']})")
            conds.append(Condicao(c["pergunta"], c["op"], c["valor"]))
        ajustes = r["efeito"]["ajuste_por_trilha"]
        if not ajustes:
            _erro(f"Regra {r['id']}: sem efeito")
        for tid, v in ajustes.items():
            if tid not in trilhas:
                _erro(f"Regra {r['id']}: trilha inexistente '{tid}'")
            if not 0 < v <= 1:
                _erro(f"Regra {r['id']}: ajuste deve estar em (0, 1], recebido {v}")
        regras.append(Regra(r["id"], r["tipo"], r["descricao"], tuple(conds), dict(ajustes)))

    return BaseConhecimento(
        metadados=bruto["metadados"], escala_min=emin, escala_max=emax,
        rotulos_escala=rotulos, etapas=etapas, perfil=bruto["perfil"],
        pontuacao=bruto["pontuacao"], perguntas=perguntas, trilhas=trilhas, regras=regras,
    )
