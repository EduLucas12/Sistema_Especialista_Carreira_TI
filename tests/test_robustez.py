"""Fase 5: testes de robustez e casos limite do motor, do explicador e da carga da base."""
import copy
import json
import random

import pytest

from carreiras.base_conhecimento import (CAMINHO_PADRAO, BaseInvalidaError,
                                         carregar_base, validar_e_construir)
from carreiras.gaps_roadmap import (CAMINHO_HABILIDADES, ConsultorGaps,
                                    HabilidadesInvalidasError, PerfilUsuario,
                                    carregar_habilidades, validar_habilidades)
from carreiras.motor_inferencia import (NEUTRO, PESO_MIN_EXPLICACAO,
                                        MemoriaTrabalho, MotorInferencia)
from carreiras.relatorio import relatorio_markdown


@pytest.fixture(scope="module")
def base():
    return carregar_base()


@pytest.fixture(scope="module")
def motor(base):
    return MotorInferencia(base)


def perfil(motor, padrao=2, **kw):
    r = {pid: padrao for pid in motor.base.perguntas}
    r.update(kw)
    return r


def ids_top(res):
    return [r.trilha_id for r in res.top]


# =========================================================================== #
# 1. Perfis ambíguos: empates parciais e justificativas coerentes
# =========================================================================== #
AMBIGUOS = {
    "dados e web": (dict(analise_dados=5, machine_learning=4, matematica=4, interfaces_web=5,
                         design_visual=4, experiencia_usuario=4, programacao=5),
                    {"cientista_dados", "frontend_ux"}),
    "dados e engenharia de dados": (dict(analise_dados=5, pipelines_dados=5, programacao=5, apis_bancos=4),
                                    {"cientista_dados", "engenheiro_dados"}),
    "infraestrutura e segurança": (dict(infraestrutura=5, seguranca=5, automacao=4, pressao=4),
                                   {"ciberseguranca", "devops_sre"}),
    "produto e UX": (dict(gestao_produto=5, comunicacao=5, experiencia_usuario=5, design_visual=4,
                          obj_impacto_negocio=5),
                     {"product_management", "frontend_ux"}),
    "mobile e web": (dict(mobile=5, interfaces_web=5, design_visual=4, experiencia_usuario=5, programacao=5),
                     {"mobile", "frontend_ux"}),
    "back-end e nuvem": (dict(apis_bancos=5, programacao=5, arquitetura=5, infraestrutura=4),
                         {"backend", "cloud_architecture"}),
}


@pytest.mark.parametrize("nome", AMBIGUOS)
def test_perfil_ambiguo_traz_as_duas_trilhas_no_top3(motor, nome):
    resp, esperadas = AMBIGUOS[nome]
    res = motor.inferir(perfil(motor, **resp))
    assert esperadas <= set(ids_top(res)), f"{nome}: top = {ids_top(res)}"
    assert not res.perfil_indefinido  # ambíguo não é o mesmo que indefinido


@pytest.mark.parametrize("nome", AMBIGUOS)
def test_justificativa_do_ambiguo_cita_o_que_puxou_cada_trilha(motor, nome):
    resp, esperadas = AMBIGUOS[nome]
    res = motor.inferir(perfil(motor, **resp))
    for tid in esperadas:
        r = res.por_id(tid)
        texto = motor.explicar(r)
        favoraveis = [c for c in r.contribuicoes if c.normalizada > NEUTRO and c.peso_efetivo >= PESO_MIN_EXPLICACAO]
        assert favoraveis, f"{tid} sem fatores a favor"
        melhor = max(favoraveis, key=lambda c: c.peso_efetivo * (c.normalizada - NEUTRO))
        assert melhor.rotulo in texto


def test_empate_parcial_aparece_no_relatorio(motor):
    res = motor.inferir(perfil(motor, **AMBIGUOS["dados e web"][0]))
    if res.empates_parciais:
        assert "empate parcial" in motor.relatorio(res)


def test_desempate_entre_trilhas_identicas_e_estavel(motor):
    """Compatibilidades idênticas: a ordem não pode mudar entre execuções nem com a ordem das respostas."""
    r1 = perfil(motor, 3)
    r2 = dict(reversed(list(r1.items())))
    assert [x.trilha_id for x in motor.inferir(r1).ranking] == [x.trilha_id for x in motor.inferir(r2).ranking]


# =========================================================================== #
# 2. Perfis sem diferenciação, extremos e parciais
# =========================================================================== #
@pytest.mark.parametrize("valor", [1, 3, 5])
def test_resposta_uniforme_e_marcada_como_indefinida(motor, valor):
    res = motor.inferir(perfil(motor, valor))
    assert res.perfil_indefinido
    assert any("não diferenciam" in a for a in res.avisos)
    assert "Aviso:" in motor.relatorio(res)


def test_perfil_bem_definido_nao_gera_aviso(motor):
    res = motor.inferir(perfil(motor, mobile=5, programacao=5, design_visual=5, experiencia_usuario=5))
    assert res.avisos == ()


def test_poucas_respostas_geram_aviso_de_cobertura(motor):
    res = motor.inferir({"mobile": 5, "programacao": 4})
    assert res.poucas_respostas and res.cobertura == pytest.approx(2 / len(motor.base.perguntas))
    assert any("perguntas foram respondidas" in a for a in res.avisos)


def test_resposta_unica_nao_gera_100_por_cento_para_varias_trilhas(motor):
    res = motor.inferir({"mobile": 5})
    assert sum(r.compatibilidade >= 0.999 for r in res.ranking) == 0
    assert res.ranking[0].trilha_id == "mobile"


def test_respostas_contraditorias_sao_penalizadas_e_explicadas(motor):
    """Quer Mobile, mas diz que não gosta de programar: a penalidade aparece na justificativa."""
    res = motor.inferir(perfil(motor, 3, mobile=5, programacao=1))
    mobile = res.por_id("mobile")
    assert any(r.id == "R04" for r in mobile.regras_ativas)
    assert "R04" in motor.explicar(mobile)
    assert mobile.compatibilidade < mobile.base


def test_penalidade_e_bonus_na_mesma_trilha_somam_liquido(motor):
    # Front-end: R04 (programação <= 2: -15) e R16 (design, UX e web >= 4: +5) ativas juntas.
    res = motor.inferir(perfil(motor, 3, programacao=1, design_visual=5, experiencia_usuario=5, interfaces_web=5))
    fe = res.por_id("frontend_ux")
    ids = {r.id for r in fe.regras_ativas}
    assert {"R04", "R16"} <= ids
    assert fe.ajuste == pytest.approx(-0.15 + 0.05)


def test_todas_as_trilhas_penalizadas_no_maximo_nao_passam_do_teto(motor):
    res = motor.inferir(perfil(motor, 1))
    teto = motor.base.pontuacao["ajuste_maximo_total"]
    assert all(abs(r.ajuste) <= teto and 0 <= r.compatibilidade <= 1 for r in res.ranking)


# =========================================================================== #
# 3. Explicador: coerência
# =========================================================================== #
def test_resposta_neutra_nao_e_citada_nem_a_favor_nem_contra(motor):
    res = motor.inferir(perfil(motor, 3))
    for r in res.ranking:
        texto = motor.explicar(r)
        assert "A favor" not in texto and "Contra" not in texto
        assert "Sem fator determinante" in texto


def test_fator_de_peso_baixo_nao_aparece_na_explicacao(motor):
    res = motor.inferir(perfil(motor, 4, design_visual=1))  # design tem peso 1 em Cientista de Dados
    texto = motor.explicar(res.por_id("cientista_dados"))
    assert "design visual" not in texto


# =========================================================================== #
# 4. Propriedades verificadas com perfis aleatórios (fuzz, semente fixa)
# =========================================================================== #
def sorteio(motor, rng, parcial=False):
    pids = list(motor.base.perguntas)
    if parcial:
        pids = rng.sample(pids, rng.randint(1, len(pids)))
    return {pid: rng.randint(1, 5) for pid in pids}


def test_fuzz_invariantes_gerais(motor):
    rng = random.Random(2026)
    for _ in range(400):
        resp = sorteio(motor, rng, parcial=rng.random() < 0.4)
        res = motor.inferir(resp)
        comps = [r.compatibilidade for r in res.ranking]
        assert len(res.ranking) == 10 and len({r.trilha_id for r in res.ranking}) == 10
        assert all(0 <= c <= 1 for c in comps) and comps == sorted(comps, reverse=True)
        assert res.top == res.ranking[:3] and len({r.trilha_id for r in res.top}) == 3
        assert res == motor.inferir(dict(resp))  # determinístico
        assert 0 <= res.cobertura <= 1
        for r in res.ranking:
            assert 0 <= r.base <= 1
            texto = motor.explicar(r)
            assert texto.startswith(r.nome)


def test_fuzz_ordem_das_respostas_nao_importa(motor):
    rng = random.Random(7)
    for _ in range(60):
        resp = sorteio(motor, rng)
        itens = list(resp.items())
        rng.shuffle(itens)
        assert motor.inferir(resp) == motor.inferir(dict(itens))


def test_fuzz_monotonicidade_da_base(motor):
    """Aumentar uma resposta nunca reduz a pontuação base de nenhuma trilha."""
    rng = random.Random(11)
    for _ in range(200):
        resp = sorteio(motor, rng)
        pid = rng.choice(list(resp))
        if resp[pid] == 5:
            continue
        maior = dict(resp, **{pid: resp[pid] + 1})
        antes, depois = motor.inferir(resp), motor.inferir(maior)
        for r in antes.ranking:
            assert depois.por_id(r.trilha_id).base >= r.base - 1e-12


def test_fuzz_estabilidade_da_base_a_um_ponto_de_mudanca(motor):
    """Mudar UMA resposta em 1 ponto muda a base no máximo (peso / soma dos pesos) / 4."""
    rng = random.Random(13)
    base = motor.base
    for _ in range(200):
        resp = sorteio(motor, rng)
        pid = rng.choice(list(resp))
        if resp[pid] == 5:
            continue
        a, b = motor.inferir(resp), motor.inferir(dict(resp, **{pid: resp[pid] + 1}))
        for tid, trilha in base.trilhas.items():
            if pid not in trilha.pesos:
                assert a.por_id(tid).base == pytest.approx(b.por_id(tid).base)
                continue
            pe = lambda q: trilha.pesos[q] * float(base.etapas[base.perguntas[q].etapa].get("peso_etapa", 1.0))
            soma = sum(pe(q) for q in trilha.pesos)
            limite = pe(pid) / soma / (base.escala_max - base.escala_min)
            assert abs(b.por_id(tid).base - a.por_id(tid).base) <= limite + 1e-12


def test_fuzz_regras_ativas_coincidem_com_avaliacao_independente(motor):
    import operator
    ops = {"<=": operator.le, ">=": operator.ge, "<": operator.lt, ">": operator.gt,
           "==": operator.eq, "!=": operator.ne}
    rng = random.Random(17)
    for _ in range(150):
        resp = sorteio(motor, rng, parcial=rng.random() < 0.3)
        res = motor.inferir(resp)
        for tid in motor.base.trilhas:
            esperadas = {
                reg.id for reg in motor.base.regras
                if tid in reg.ajuste_por_trilha
                and all(c.pergunta in resp and ops[c.op](resp[c.pergunta], c.valor) for c in reg.condicoes)}
            assert {a.id for a in res.por_id(tid).regras_ativas} == esperadas


def test_fuzz_explicacao_coerente_com_as_respostas(motor):
    rng = random.Random(19)
    escala_max = motor.base.escala_max
    for _ in range(100):
        resp = sorteio(motor, rng)
        res = motor.inferir(resp)
        for r in res.ranking:
            linhas = motor.explicar(r).splitlines()
            favor = next((l for l in linhas if l.startswith("  A favor")), "")
            contra = next((l for l in linhas if l.startswith("  Contra")), "")
            for c in r.contribuicoes:
                trecho = f"{c.rotulo} (resposta {c.resposta}/{escala_max})"
                if trecho in favor:
                    assert c.resposta > 3
                if trecho in contra:
                    assert c.resposta < 3
            citadas = {l.split()[1] for l in linhas if l.strip().startswith(("Penalidade", "Bônus"))}
            assert citadas == {a.id for a in r.regras_ativas}


# =========================================================================== #
# 5. Entradas inválidas e base corrompida
# =========================================================================== #
def test_respostas_invalidas_nunca_passam(motor):
    for valor in (0, 6, -1, 2.0, "3", None, True, [3]):
        with pytest.raises(ValueError):
            MemoriaTrabalho().responder(motor.base, "mobile", valor)


def test_arquivo_inexistente(tmp_path):
    with pytest.raises(BaseInvalidaError, match="não encontrado"):
        carregar_base(tmp_path / "nao_existe.json")
    with pytest.raises(HabilidadesInvalidasError, match="não encontrado"):
        carregar_habilidades(tmp_path / "nao_existe.json")


def test_json_malformado(tmp_path):
    arq = tmp_path / "ruim.json"
    arq.write_text("{ isto não é json", encoding="utf-8")
    with pytest.raises(BaseInvalidaError, match="JSON inválido"):
        carregar_base(arq)
    with pytest.raises(HabilidadesInvalidasError, match="JSON inválido"):
        carregar_habilidades(arq)


@pytest.mark.parametrize("remover", [("perguntas", 0, "texto"), ("trilhas", 0, "pesos"), ("regras", 0, "condicoes")])
def test_campo_obrigatorio_ausente_vira_erro_claro(remover):
    with open(CAMINHO_PADRAO, encoding="utf-8") as f:
        bruto = json.load(f)
    secao, i, campo = remover
    del bruto[secao][i][campo]
    with pytest.raises(BaseInvalidaError, match="malformada"):
        validar_e_construir(bruto)


def test_tipo_errado_vira_erro_claro():
    with open(CAMINHO_PADRAO, encoding="utf-8") as f:
        bruto = json.load(f)
    bruto["trilhas"][0]["pesos"] = "muitos"
    with pytest.raises(BaseInvalidaError):
        validar_e_construir(bruto)


def test_habilidades_campo_ausente_vira_erro_claro(base):
    with open(CAMINHO_HABILIDADES, encoding="utf-8") as f:
        bruto = json.load(f)
    del bruto["trilhas"]["backend"]["habilidades"][0]["nivel_junior"]
    with pytest.raises(HabilidadesInvalidasError, match="malformada"):
        validar_habilidades(bruto, base)


# =========================================================================== #
# 6. Plano e relatório em situações extremas
# =========================================================================== #
@pytest.mark.parametrize("horas", [0.5, 1, 80])
def test_plano_com_horas_extremas(base, horas):
    plano = ConsultorGaps(base=base).plano("backend", PerfilUsuario("iniciante", horas))
    assert plano.roadmap.semanas >= 1 and plano.roadmap.total_horas > 0


@pytest.mark.parametrize("nome", ["", "   ", "A\n# Título falso", "<script>alert(1)</script>", "João | Silva", "x" * 500])
def test_relatorio_com_nomes_estranhos(base, motor, nome):
    res = motor.inferir(perfil(motor, mobile=5))
    plano = ConsultorGaps(base=base).plano(res.top[0].trilha_id, PerfilUsuario("basico", 5))
    md = relatorio_markdown(motor, res, plano, nome)
    linhas = md.splitlines()
    assert linhas[0].startswith("# Plano de carreira em TI")
    assert sum(l.startswith("# ") for l in linhas) == 1  # nenhum título extra injetado pelo nome
    assert len(linhas[0]) <= 100


def test_relatorio_inclui_avisos_de_perfil_indefinido(base, motor):
    res = motor.inferir(perfil(motor, 3))
    plano = ConsultorGaps(base=base).plano(res.top[0].trilha_id, PerfilUsuario("basico", 5))
    assert "**Aviso:**" in relatorio_markdown(motor, res, plano)
