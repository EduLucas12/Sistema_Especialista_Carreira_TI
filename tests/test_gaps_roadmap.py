import copy
import json
import math

import pytest

from carreiras.base_conhecimento import carregar_base
from carreiras.gaps_roadmap import (CAMINHO_HABILIDADES, ConsultorGaps,
                                    EntradaInvalidaError,
                                    HabilidadesInvalidasError, PerfilUsuario,
                                    formatar_plano, validar_habilidades)
from carreiras.motor_inferencia import MotorInferencia


@pytest.fixture(scope="module")
def base():
    return carregar_base()


@pytest.fixture(scope="module")
def consultor(base):
    return ConsultorGaps(base=base)


@pytest.fixture(scope="module")
def bruto():
    with open(CAMINHO_HABILIDADES, encoding="utf-8") as f:
        return json.load(f)


def nivel_total(consultor, tid, nivel):
    return {h: nivel for h in consultor.hab.trilhas[tid].habilidades}


# ---------- validação da base de habilidades ----------
def test_base_cobre_as_10_trilhas(consultor):
    assert len(consultor.hab.trilhas) == 10
    for t in consultor.hab.trilhas.values():
        assert len(t.habilidades) >= 8
        assert len(t.certificacoes) == 3 and len(t.projetos) == 3
        assert any(h.prioridade == "essencial" for h in t.habilidades.values())
        assert sorted(p.dificuldade for p in t.projetos) == [1, 2, 3]


def test_trilhas_diferentes_da_base_principal(bruto, base):
    ruim = copy.deepcopy(bruto)
    ruim["trilhas"].pop("qa")
    with pytest.raises(HabilidadesInvalidasError, match="mesmas"):
        validar_habilidades(ruim, base)


def test_ciclo_de_pre_requisitos(bruto, base):
    ruim = copy.deepcopy(bruto)
    hs = {h["id"]: h for h in ruim["trilhas"]["backend"]["habilidades"]}
    hs["logica"]["pre_requisitos"] = ["estruturas"]  # estruturas já depende de logica
    with pytest.raises(HabilidadesInvalidasError, match="ciclo"):
        validar_habilidades(ruim, base)


def test_pre_requisito_inexistente(bruto, base):
    ruim = copy.deepcopy(bruto)
    ruim["trilhas"]["backend"]["habilidades"][0]["pre_requisitos"] = ["nao_existe"]
    with pytest.raises(HabilidadesInvalidasError, match="pré-requisito"):
        validar_habilidades(ruim, base)


def test_pre_requisito_em_bloco_posterior(bruto, base):
    ruim = copy.deepcopy(bruto)
    hs = {h["id"]: h for h in ruim["trilhas"]["backend"]["habilidades"]}
    hs["git"]["pre_requisitos"] = ["docker"]  # git (fundamentos) dependendo de docker (ferramentas)
    with pytest.raises(HabilidadesInvalidasError, match="bloco posterior"):
        validar_habilidades(ruim, base)


def test_projeto_com_habilidade_inexistente(bruto, base):
    ruim = copy.deepcopy(bruto)
    ruim["trilhas"]["backend"]["projetos"][0]["habilidades"].append("xyz")
    with pytest.raises(HabilidadesInvalidasError, match="inexistente"):
        validar_habilidades(ruim, base)


# ---------- gaps ----------
@pytest.mark.parametrize("tid", ["backend", "frontend_ux", "cientista_dados", "engenheiro_dados", "ciberseguranca",
                                 "devops_sre", "cloud_architecture", "mobile", "qa", "product_management"])
def test_extremos_por_trilha(consultor, tid):
    perfil = PerfilUsuario("iniciante", 10)
    zero = consultor.analisar_gaps(tid, perfil, nivel_total(consultor, tid, 0))
    pleno = consultor.analisar_gaps(tid, perfil, nivel_total(consultor, tid, 3))
    assert zero.prontidao == 0 and zero.classificacao_id == "inicio"
    assert pleno.prontidao == pytest.approx(1.0) and pleno.classificacao_id == "apto"
    assert not pleno.lacunas and not pleno.essenciais_pendentes


def test_gap_e_calculo_de_prontidao(consultor):
    perfil = PerfilUsuario("iniciante", 10)
    a = consultor.analisar_gaps("backend", perfil, {"git": 1, "logica": 2})
    assert a.por_id("git").gap == 1 and a.por_id("logica").gap == 0
    assert a.por_id("git").estimado is False and a.por_id("sql").estimado is True
    # nível acima do exigido não conta além do exigido
    b = consultor.analisar_gaps("backend", perfil, {"logica": 3})
    assert b.por_id("logica").gap == 0
    assert b.prontidao == pytest.approx(a.prontidao - (1 * 3 * 1) / sum(
        consultor.hab.pesos_prioridade[i.habilidade.prioridade] * i.habilidade.nivel_junior for i in a.itens))


def test_estimativa_pelo_nivel_de_experiencia(consultor):
    prontidoes = [consultor.analisar_gaps("devops_sre", PerfilUsuario(n, 5)).prontidao
                  for n in ("iniciante", "basico", "intermediario", "avancado")]
    assert prontidoes == sorted(prontidoes) and prontidoes[0] == 0 and prontidoes[-1] > prontidoes[0]
    assert all(i.estimado for i in consultor.analisar_gaps("devops_sre", PerfilUsuario("basico", 5)).itens)


def test_prontidao_alta_com_essencial_pendente_nao_e_apto(consultor):
    avaliacao = nivel_total(consultor, "backend", 3)
    avaliacao["framework"] = 0  # essencial zerado, o resto domina
    a = consultor.analisar_gaps("backend", PerfilUsuario("iniciante", 5), avaliacao)
    assert a.prontidao >= consultor.hab.limiares["apto"]
    assert a.classificacao_id == "quase_la" and "Framework web" in a.essenciais_pendentes


@pytest.mark.parametrize("perfil,avaliacao,msg", [
    (PerfilUsuario("guru", 5), None, "nivel_experiencia"),
    (PerfilUsuario("iniciante", 0), None, "horas_semanais"),
    (PerfilUsuario("iniciante", 100), None, "horas_semanais"),
    (PerfilUsuario("iniciante", 5), {"nao_existe": 1}, "não existe"),
    (PerfilUsuario("iniciante", 5), {"git": 4}, "Nível"),
    (PerfilUsuario("iniciante", 5), {"git": -1}, "Nível"),
    (PerfilUsuario("iniciante", 5), {"git": 1.5}, "Nível"),
])
def test_entradas_invalidas(consultor, perfil, avaliacao, msg):
    with pytest.raises(EntradaInvalidaError, match=msg):
        consultor.analisar_gaps("backend", perfil, avaliacao)


def test_trilha_desconhecida(consultor):
    with pytest.raises(EntradaInvalidaError, match="Trilha"):
        consultor.analisar_gaps("astronauta", PerfilUsuario())


# ---------- roadmap ----------
@pytest.mark.parametrize("tid", ["backend", "frontend_ux", "cientista_dados", "engenheiro_dados", "ciberseguranca",
                                 "devops_sre", "cloud_architecture", "mobile", "qa", "product_management"])
def test_roadmap_respeita_pre_requisitos_e_blocos(consultor, tid):
    plano = consultor.plano(tid, PerfilUsuario("iniciante", 6))
    ordem = {i.habilidade.id: i.ordem for i in plano.roadmap.itens}
    for item in plano.roadmap.itens:
        for pre in item.habilidade.pre_requisitos:
            if pre in ordem:
                assert ordem[pre] < item.ordem
    blocos = [e.bloco_id for e in plano.roadmap.etapas]
    assert blocos == sorted(blocos, key=consultor.hab.blocos.index)
    # todas as lacunas viram item de roadmap, sem duplicidade
    assert sorted(ordem) == sorted(i.habilidade.id for i in plano.analise.lacunas)
    assert [i.ordem for i in plano.roadmap.itens] == list(range(1, len(ordem) + 1))


def test_horas_e_semanas(consultor):
    plano = consultor.plano("backend", PerfilUsuario("iniciante", 10))
    esperado = sum(g.gap * g.habilidade.horas_por_nivel for g in plano.analise.lacunas)
    assert plano.roadmap.total_horas == pytest.approx(esperado)
    assert plano.roadmap.semanas == math.ceil(esperado / 10)
    dobro = consultor.plano("backend", PerfilUsuario("iniciante", 20)).roadmap.semanas
    assert dobro <= plano.roadmap.semanas / 2 + 1


def test_sem_lacunas_roadmap_vazio(consultor):
    plano = consultor.plano("qa", PerfilUsuario("avancado", 5), nivel_total(consultor, "qa", 3))
    assert plano.roadmap.itens == () and plano.roadmap.semanas == 0 and plano.roadmap.total_horas == 0
    assert "Nenhuma lacuna" in formatar_plano(plano)


def test_prerequisito_ja_atendido_nao_entra_no_roadmap(consultor):
    avaliacao = {"linux": 2}
    plano = consultor.plano("devops_sre", PerfilUsuario("iniciante", 5), avaliacao)
    ids = {i.habilidade.id for i in plano.roadmap.itens}
    assert "linux" not in ids and "scripts" in ids


def test_certificacoes_liberadas_pela_prontidao(consultor):
    iniciante = consultor.plano("cloud_architecture", PerfilUsuario("iniciante", 5)).roadmap
    pleno = consultor.plano("cloud_architecture", PerfilUsuario("avancado", 5),
                            nivel_total(consultor, "cloud_architecture", 3)).roadmap
    assert not any(c.disponivel_agora for c in iniciante.certificacoes)
    assert all(c.disponivel_agora for c in pleno.certificacoes)
    minimos = [c.certificacao.min_prontidao for c in pleno.certificacoes]
    assert minimos == sorted(minimos)


def test_projetos_ordenados_e_momento(consultor):
    ini = consultor.plano("mobile", PerfilUsuario("iniciante", 5)).roadmap.projetos
    pleno = consultor.plano("mobile", PerfilUsuario("avancado", 5), nivel_total(consultor, "mobile", 3)).roadmap.projetos
    assert [p.projeto.dificuldade for p in ini] == [1, 2, 3]
    assert [p.momento for p in ini] == ["agora", "depois", "depois"]
    assert all(p.momento == "agora" for p in pleno)
    assert all(p.treina_lacunas == () for p in pleno)
    assert ini[0].treina_lacunas  # o projeto inicial treina lacunas reais


# ---------- integração com o motor de inferência ----------
def test_integracao_motor_e_plano(base, consultor):
    motor = MotorInferencia(base)
    res = motor.inferir({"matematica": 5, "analise_dados": 5, "machine_learning": 5, "programacao": 4})
    vencedora = res.top[0].trilha_id
    assert vencedora == "cientista_dados"
    plano = consultor.plano(vencedora, PerfilUsuario("basico", 8))
    assert plano.analise.trilha_nome == "Cientista de Dados"
    assert 0 <= plano.analise.prontidao <= 1 and plano.roadmap.itens


def test_formatar_plano_contem_secoes(consultor):
    txt = formatar_plano(consultor.plano("backend", PerfilUsuario("basico", 6)))
    for trecho in ("Análise de gaps", "Roadmap", "Certificações", "Projetos", "GitHub"):
        assert trecho in txt
