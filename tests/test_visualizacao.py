import pytest

pytest.importorskip("plotly")
from carreiras import visualizacao as viz  # noqa: E402
from carreiras.base_conhecimento import carregar_base  # noqa: E402
from carreiras.gaps_roadmap import ConsultorGaps, PerfilUsuario  # noqa: E402
from carreiras.motor_inferencia import MotorInferencia  # noqa: E402
from carreiras.relatorio import relatorio_markdown  # noqa: E402


@pytest.fixture(scope="module")
def contexto():
    base = carregar_base()
    motor = MotorInferencia(base)
    consultor = ConsultorGaps(base=base)
    res = motor.inferir({"mobile": 5, "programacao": 4, "experiencia_usuario": 4, "design_visual": 4})
    plano = consultor.plano(res.top[0].trilha_id, PerfilUsuario("basico", 6))
    return motor, res, plano


def test_df_ranking(contexto):
    _, res, _ = contexto
    df = viz.df_ranking(res)
    assert len(df) == 10 and list(df["Posição"]) == list(range(1, 11))
    assert (df["Top 3"] == "sim").sum() == 3
    assert df["Compatibilidade (%)"].is_monotonic_decreasing


def test_graficos(contexto):
    _, res, plano = contexto
    barras, radar, pront = viz.fig_barras(res), viz.fig_radar(res), viz.fig_prontidao(plano.analise)
    assert len(barras.data[0].y) == 10
    assert len(radar.data[0].r) == 11 and radar.data[0].r[0] == radar.data[0].r[-1]  # polígono fechado
    assert len(pront.data) == 2
    # Top 3 destacado nas barras
    assert sum(c == viz.COR_TOP for c in barras.data[0].marker.color) == 3


def test_tabelas_do_plano(contexto):
    _, _, plano = contexto
    assert len(viz.df_gaps(plano.analise)) == len(plano.analise.itens)
    assert len(viz.df_roadmap(plano.roadmap)) == len(plano.roadmap.itens)
    assert len(viz.df_certificacoes(plano.roadmap)) == 3
    assert len(viz.df_projetos(plano.roadmap)) == 3


def test_relatorio_markdown(contexto):
    motor, res, plano = contexto
    md = relatorio_markdown(motor, res, plano, "Lucas")
    for trecho in ("# Plano de carreira em TI - Lucas", "Top 3", "Análise de gaps", "Roadmap",
                   "Certificações", "Projetos para o portfólio"):
        assert trecho in md
    assert md.count("| 1 |") >= 1
