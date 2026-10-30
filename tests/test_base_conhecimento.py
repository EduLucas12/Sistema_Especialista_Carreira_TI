import copy
import json

import pytest

from carreiras.base_conhecimento import (CAMINHO_PADRAO, BaseInvalidaError,
                                         carregar_base, validar_e_construir)


@pytest.fixture(scope="module")
def bruto():
    with open(CAMINHO_PADRAO, encoding="utf-8") as f:
        return json.load(f)


def test_base_padrao_carrega():
    base = carregar_base()
    assert len(base.trilhas) == 10
    assert len(base.perguntas) >= 15
    assert (base.escala_min, base.escala_max) == (1, 5)


def test_todas_as_etapas_pontuaveis_tem_perguntas():
    base = carregar_base()
    assert base.perguntas_da_etapa("afinidades")
    assert base.perguntas_da_etapa("objetivos")


def test_cada_trilha_tem_pergunta_dominante():
    """Cada trilha deve ter ao menos uma pergunta com peso >= 9 (identidade da trilha)."""
    base = carregar_base()
    for t in base.trilhas.values():
        assert max(t.pesos.values()) >= 9, t.id


def test_pergunta_inexistente_na_trilha(bruto):
    ruim = copy.deepcopy(bruto)
    ruim["trilhas"][0]["pesos"]["nao_existe"] = 5
    with pytest.raises(BaseInvalidaError, match="inexistente"):
        validar_e_construir(ruim)


def test_peso_negativo(bruto):
    ruim = copy.deepcopy(bruto)
    ruim["trilhas"][0]["pesos"]["matematica"] = -1
    with pytest.raises(BaseInvalidaError, match="Peso inválido"):
        validar_e_construir(ruim)


def test_numero_de_trilhas(bruto):
    ruim = copy.deepcopy(bruto)
    ruim["trilhas"].pop()
    with pytest.raises(BaseInvalidaError, match="10 trilhas"):
        validar_e_construir(ruim)


def test_regra_com_operador_invalido(bruto):
    ruim = copy.deepcopy(bruto)
    ruim["regras"][0]["condicoes"][0]["op"] = "=>"
    with pytest.raises(BaseInvalidaError, match="operador"):
        validar_e_construir(ruim)


def test_regra_com_valor_fora_da_escala(bruto):
    ruim = copy.deepcopy(bruto)
    ruim["regras"][0]["condicoes"][0]["valor"] = 9
    with pytest.raises(BaseInvalidaError, match="fora da escala"):
        validar_e_construir(ruim)


def test_regra_com_trilha_inexistente(bruto):
    ruim = copy.deepcopy(bruto)
    ruim["regras"][0]["efeito"]["ajuste_por_trilha"]["xyz"] = 0.1
    with pytest.raises(BaseInvalidaError, match="trilha inexistente"):
        validar_e_construir(ruim)


def test_pergunta_sem_peso_em_nenhuma_trilha(bruto):
    ruim = copy.deepcopy(bruto)
    ruim["perguntas"].append({"id": "orfa", "etapa": "afinidades", "texto": "?", "rotulo": "órfã"})
    with pytest.raises(BaseInvalidaError, match="sem peso"):
        validar_e_construir(ruim)
