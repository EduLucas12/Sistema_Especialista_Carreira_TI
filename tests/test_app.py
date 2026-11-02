"""Testes da interface Streamlit (sem navegador) com streamlit.testing.v1.AppTest."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from carreiras.base_conhecimento import carregar_base  # noqa: E402

BASE = carregar_base()
APP = str(Path(__file__).resolve().parent.parent / "app.py")


def novo_app() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception
    return at


def clicar(at: AppTest, chave: str) -> None:
    at.button(chave).click()
    at.run()
    assert not at.exception


def passo1(at: AppTest, nivel="basico", horas=8.0, nome="Ana"):
    at.text_input("w_nome").set_value(nome)
    at.radio("w_nivel").set_value(nivel)
    at.number_input("w_horas").set_value(horas)
    at.run()
    clicar(at, "btn_avancar")


def responder(at: AppTest, etapa: str, valores: dict[str, int], padrao=3):
    for p in BASE.perguntas_da_etapa(etapa):
        at.radio(f"w_{p.id}").set_value(valores.get(p.id, padrao))
    at.run()


def consulta_completa(afinidades: dict[str, int], nivel="basico") -> AppTest:
    at = novo_app()
    passo1(at, nivel)
    responder(at, "afinidades", afinidades)
    clicar(at, "btn_avancar")
    responder(at, "objetivos", {})
    clicar(at, "btn_avancar")
    return at


def test_abre_no_passo_1():
    at = novo_app()
    assert at.session_state["passo"] == 1
    assert "Perfil pessoal" in at.get("progress")[0].proto.text


def test_passo1_exige_nivel():
    at = novo_app()
    clicar(at, "btn_avancar")
    assert at.session_state["passo"] == 1
    assert any("nível" in w.value for w in at.warning)


def test_passo2_exige_todas_as_respostas():
    at = novo_app()
    passo1(at)
    assert at.session_state["passo"] == 2
    at.radio("w_matematica").set_value(4)
    at.run()
    clicar(at, "btn_avancar")
    assert at.session_state["passo"] == 2
    assert any("todas" in w.value for w in at.warning)


def test_voltar_preserva_respostas():
    at = novo_app()
    passo1(at, nome="Bia", horas=12.0)
    responder(at, "afinidades", {"matematica": 5})
    clicar(at, "btn_voltar")
    assert at.session_state["passo"] == 1
    assert at.text_input("w_nome").value == "Bia"
    assert at.number_input("w_horas").value == 12.0
    clicar(at, "btn_avancar")
    assert at.radio("w_matematica").value == 5


def test_fluxo_completo_mostra_resultado_coerente():
    at = consulta_completa({"matematica": 5, "analise_dados": 5, "machine_learning": 5, "programacao": 4})
    assert at.session_state["passo"] == 4
    assert not at.exception
    primeiro = at.metric[0]
    assert "Cientista de Dados" in primeiro.label and primeiro.value.endswith("%")
    assert len(at.tabs) >= 3
    assert any(m.label == "Prontidão para Júnior" for m in at.metric)


def test_trocar_trilha_do_plano_atualiza_o_plano():
    at = consulta_completa({"infraestrutura": 5, "automacao": 5, "pressao": 5})
    at.selectbox("w_trilha").set_value("backend")
    at.run()
    assert not at.exception
    assert at.session_state["dados"]["trilha"] == "backend"
    chaves = {s.key for s in at.selectbox}
    assert "w_av_backend_framework" in chaves and "w_av_devops_sre_docker" not in chaves


def test_avaliacao_de_habilidade_aumenta_a_prontidao():
    at = consulta_completa({"infraestrutura": 5, "automacao": 5, "pressao": 5}, nivel="iniciante")
    antes = next(m for m in at.metric if m.label == "Prontidão para Júnior").value
    tid = at.selectbox("w_trilha").value
    for h in ("linux", "git"):
        chave = f"w_av_{tid}_{h}"
        if any(s.key == chave for s in at.selectbox):
            at.selectbox(chave).set_value(2)
    at.run()
    depois = next(m for m in at.metric if m.label == "Prontidão para Júnior").value
    assert float(depois.rstrip("%")) > float(antes.rstrip("%"))


def test_nova_consulta_reinicia():
    at = consulta_completa({"mobile": 5})
    clicar(at, "btn_recomecar")
    assert at.session_state["passo"] == 1
    assert at.session_state["dados"]["respostas"] == {}
