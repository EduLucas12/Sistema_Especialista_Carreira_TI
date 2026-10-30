import pytest

from carreiras.base_conhecimento import carregar_base
from carreiras.motor_inferencia import (MemoriaTrabalho, MotorInferencia,
                                        RespostaInvalidaError)


@pytest.fixture(scope="module")
def motor():
    return MotorInferencia(carregar_base())


def todas(motor, valor, **excecoes):
    r = {pid: valor for pid in motor.base.perguntas}
    r.update(excecoes)
    return r


# ---------- validação de entrada (memória de trabalho) ----------
@pytest.mark.parametrize("pid,valor", [("matematica", 0), ("matematica", 6), ("matematica", 2.5),
                                       ("matematica", "5"), ("matematica", True), ("inexistente", 3)])
def test_respostas_invalidas(motor, pid, valor):
    with pytest.raises(RespostaInvalidaError):
        MemoriaTrabalho().responder(motor.base, pid, valor)


def test_sem_respostas_levanta_erro(motor):
    with pytest.raises(RespostaInvalidaError):
        motor.inferir({})


# ---------- propriedades da pontuação ----------
def test_todas_as_respostas_maximas(motor):
    res = motor.inferir(todas(motor, 5))
    assert all(r.base == pytest.approx(1.0) for r in res.ranking)
    assert all(r.compatibilidade <= 1.0 for r in res.ranking)  # clamp com bônus


def test_todas_as_respostas_minimas(motor):
    res = motor.inferir(todas(motor, 1))
    assert all(r.base == 0 and r.compatibilidade == 0 for r in res.ranking)


def test_neutro_gera_50_por_cento_sem_regras(motor):
    res = motor.inferir(todas(motor, 3))
    assert all(r.base == pytest.approx(0.5) and not r.regras_ativas for r in res.ranking)


def test_compatibilidade_sempre_entre_0_e_1(motor):
    import itertools
    pids = list(motor.base.perguntas)
    for valor in itertools.product([1, 3, 5], repeat=3):
        r = todas(motor, 3)
        for pid, v in zip(pids[:3], valor):
            r[pid] = v
        for t in motor.inferir(r).ranking:
            assert 0 <= t.compatibilidade <= 1


def test_ranking_ordenado_e_top3(motor):
    res = motor.inferir(todas(motor, 3, matematica=5, analise_dados=5, machine_learning=5))
    comps = [r.compatibilidade for r in res.ranking]
    assert comps == sorted(comps, reverse=True)
    assert len(res.ranking) == 10 and len(res.top) == 3
    assert res.top == res.ranking[:3]


def test_resultado_deterministico(motor):
    r = todas(motor, 3, seguranca=5)
    assert motor.inferir(r) == motor.inferir(dict(r))


def test_perguntas_nao_respondidas_sao_neutras(motor):
    res = motor.inferir({"mobile": 5})
    assert res.ranking[0].trilha_id == "mobile"
    assert 0.5 < res.por_id("mobile").base < 1.0  # parcial não vira 100%
    outra = motor.inferir({"matematica": 3})
    assert all(r.base == pytest.approx(0.5) for r in outra.ranking)


# ---------- perfis típicos ----------
@pytest.mark.parametrize("perfil,esperado", [
    (dict(matematica=5, analise_dados=5, machine_learning=5, programacao=4), "cientista_dados"),
    (dict(infraestrutura=5, automacao=5, pressao=5), "devops_sre"),
    (dict(interfaces_web=5, design_visual=5, experiencia_usuario=5), "frontend_ux"),
    (dict(seguranca=5, infraestrutura=4), "ciberseguranca"),
    (dict(mobile=5, programacao=4, experiencia_usuario=4), "mobile"),
    (dict(qualidade=5, automacao=3), "qa"),
    (dict(gestao_produto=5, comunicacao=5, obj_lideranca=5, obj_impacto_negocio=5), "product_management"),
    (dict(pipelines_dados=5, apis_bancos=4, programacao=4), "engenheiro_dados"),
    (dict(apis_bancos=5, programacao=5, arquitetura=4), "backend"),
    (dict(arquitetura=5, infraestrutura=4, seguranca=3), "cloud_architecture"),
])
def test_cada_trilha_pode_vencer(motor, perfil, esperado):
    res = motor.inferir(todas(motor, 2, **perfil))
    assert res.ranking[0].trilha_id == esperado


# ---------- regras: penalidades e bônus ----------
def test_penalidade_por_perfil_conflitante(motor):
    # Quer Mobile, mas não gosta de programar: R04 e R10 não; R04 sim.
    com = motor.inferir(todas(motor, 3, mobile=5, programacao=1)).por_id("mobile")
    sem = motor.inferir(todas(motor, 3, mobile=5, programacao=3)).por_id("mobile")
    assert any(r.id == "R04" and r.ajuste < 0 for r in com.regras_ativas)
    assert com.compatibilidade < sem.compatibilidade


def test_bonus_de_sinergia(motor):
    res = motor.inferir(todas(motor, 3, infraestrutura=5, automacao=5)).por_id("devops_sre")
    assert any(r.id == "R14" and r.ajuste > 0 for r in res.regras_ativas)


def test_regra_com_condicao_nao_respondida_nao_dispara(motor):
    res = motor.inferir({"design_visual": 1})  # R01 exige também experiencia_usuario <= 2
    assert not res.por_id("frontend_ux").regras_ativas


def test_ajuste_respeita_teto(motor):
    teto = motor.base.pontuacao["ajuste_maximo_total"]
    for r in motor.inferir(todas(motor, 1)).ranking:
        assert abs(r.ajuste) <= teto + 1e-9


# ---------- empates parciais ----------
def test_empate_parcial_detectado(motor):
    res = motor.inferir(todas(motor, 3))  # todas empatadas em 50%
    assert res.empates_parciais


def test_perfil_ambiguo_dados_e_web(motor):
    """Gosta de dados e de web: ambos devem aparecer no Top 3."""
    res = motor.inferir(todas(motor, 2, analise_dados=5, machine_learning=4, matematica=4,
                              interfaces_web=5, design_visual=4, experiencia_usuario=4, programacao=5))
    ids = {r.trilha_id for r in res.top}
    assert {"cientista_dados", "frontend_ux"} <= ids


# ---------- explicador ----------
def test_explicacao_cita_fatos_e_regras(motor):
    res = motor.inferir(todas(motor, 3, infraestrutura=5, automacao=5, pressao=1))
    texto = motor.explicar(res.por_id("devops_sre"))
    assert "DevOps / SRE" in texto and "A favor" in texto and "R05" in texto and "R14" in texto


def test_relatorio_lista_top3(motor):
    rel = motor.relatorio(motor.inferir(todas(motor, 3, mobile=5)))
    assert rel.count("º ") >= 3
