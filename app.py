"""Interface Streamlit em etapas (wizard) do Consultor de Carreiras em TI.

Executar:  streamlit run app.py

Passo 1: Perfil pessoal -> Passo 2: Afinidades técnicas -> Passo 3: Objetivos de carreira -> Resultado
Toda a lógica (inferência, gaps, roadmap) fica em `carreiras/`; este arquivo só cuida da apresentação.
"""
import streamlit as st

from carreiras.base_conhecimento import BaseInvalidaError, carregar_base
from carreiras.gaps_roadmap import ConsultorGaps, HabilidadesInvalidasError, PerfilUsuario
from carreiras.motor_inferencia import MemoriaTrabalho, MotorInferencia
from carreiras.relatorio import relatorio_markdown
from carreiras import visualizacao as viz

st.set_page_config(page_title="Consultor de Carreiras em TI", page_icon=":compass:", layout="wide")

PASSOS = ["perfil", "afinidades", "objetivos", "resultado"]


# --------------------------------------------------------------------------- #
# Infraestrutura
# --------------------------------------------------------------------------- #
@st.cache_resource
def carregar_sistema():
    base = carregar_base()
    return base, MotorInferencia(base), ConsultorGaps(base=base)


def carregar_ou_parar():
    """Mostra um erro legível (em vez de um traceback) se os JSONs da base estiverem inválidos."""
    try:
        return carregar_sistema()
    except (BaseInvalidaError, HabilidadesInvalidasError) as e:
        st.error(f"Não foi possível carregar a base de conhecimento: {e}")
        st.stop()


def estado() -> dict:
    ss = st.session_state
    ss.setdefault("passo", 1)
    ss.setdefault("dados", {"nome": "", "nivel": None, "horas": None, "respostas": {},
                            "avaliacao": {}, "trilha": None})
    return ss["dados"]


def ir_para(passo: int) -> None:
    st.session_state["passo"] = passo
    st.rerun()


def recomecar() -> None:
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()


def restaurar(chave_widget: str, valor) -> None:
    """Streamlit descarta widgets que saem da tela; repõe o valor guardado em `dados`."""
    if chave_widget not in st.session_state and valor is not None:
        st.session_state[chave_widget] = valor


def cabecalho(base, passo: int) -> None:
    titulos = [base.etapas["perfil"]["titulo"], base.etapas["afinidades"]["titulo"],
               base.etapas["objetivos"]["titulo"], "Resultado"]
    st.title("Consultor de Carreiras em TI")
    st.caption("Sistema especialista com pontuação ponderada: descubra trilhas compatíveis, seus gaps e um roadmap.")
    st.progress((passo - 1) / (len(titulos) - 1), text=f"Etapa {passo} de {len(titulos)}: {titulos[passo - 1]}")


def barra_lateral(base) -> None:
    with st.sidebar:
        st.header("Como funciona")
        st.write("Você responde com graus de afinidade (não só sim/não). Cada resposta multiplica o peso da "
                 "regra em cada trilha; regras somam penalidades e bônus para perfis conflitantes ou complementares.")
        st.subheader("Escala de afinidade")
        for k, v in base.rotulos_escala.items():
            st.write(f"**{k}** - {v}")
        st.divider()
        if st.button("Recomeçar", key="btn_recomecar_lateral"):
            recomecar()


def navegacao(passo: int, pode_avancar: bool, msg_bloqueio: str, texto_avancar: str = "Avançar") -> None:
    col_v, col_a, _ = st.columns([1, 1, 4])
    if passo > 1 and col_v.button("Voltar", key="btn_voltar"):
        ir_para(passo - 1)
    if col_a.button(texto_avancar, key="btn_avancar", type="primary"):
        if pode_avancar:
            ir_para(passo + 1)
        else:
            st.warning(msg_bloqueio)


# --------------------------------------------------------------------------- #
# Passos 1-3
# --------------------------------------------------------------------------- #
def passo_perfil(base, dados: dict) -> None:
    st.subheader(base.etapas["perfil"]["titulo"])
    campos = {c["id"]: c for c in base.perfil}

    restaurar("w_nome", dados["nome"])
    dados["nome"] = st.text_input(campos["nome"]["texto"], key="w_nome")

    nivel = campos["nivel_experiencia"]
    rotulos = {o["valor"]: o["rotulo"] for o in nivel["opcoes"]}
    restaurar("w_nivel", dados["nivel"])
    escolha = st.radio(nivel["texto"], list(rotulos), format_func=rotulos.get, index=None, key="w_nivel")
    dados["nivel"] = escolha

    h = campos["horas_semanais"]
    restaurar("w_horas", dados["horas"])
    horas = st.number_input(h["texto"], min_value=float(h["minimo"]), max_value=float(h["maximo"]),
                            value=6.0, step=1.0, key="w_horas")
    dados["horas"] = horas

    navegacao(1, dados["nivel"] is not None, "Escolha o seu nível atual para continuar.")


def passo_likert(base, dados: dict, etapa: str, passo: int) -> None:
    st.subheader(base.etapas[etapa]["titulo"])
    perguntas = base.perguntas_da_etapa(etapa)
    st.caption(f"Responda de {base.escala_min} ({base.rotulos_escala[base.escala_min]}) "
               f"a {base.escala_max} ({base.rotulos_escala[base.escala_max]}).")
    opcoes = list(range(base.escala_min, base.escala_max + 1))
    for p in perguntas:
        chave = f"w_{p.id}"
        restaurar(chave, dados["respostas"].get(p.id))
        st.markdown(f"**{p.texto}**")
        valor = st.radio(p.texto, opcoes, format_func=lambda v: f"{v} - {base.rotulos_escala[v]}",
                         horizontal=True, index=None, key=chave, label_visibility="collapsed")
        if valor is not None:
            dados["respostas"][p.id] = valor
    respondidas = sum(p.id in dados["respostas"] for p in perguntas)
    st.progress(respondidas / len(perguntas), text=f"{respondidas} de {len(perguntas)} respondidas")
    ultimo = passo == 3
    navegacao(passo, respondidas == len(perguntas), "Responda todas as perguntas para continuar.",
              "Ver resultado" if ultimo else "Avançar")


# --------------------------------------------------------------------------- #
# Resultado
# --------------------------------------------------------------------------- #
def passo_resultado(base, motor: MotorInferencia, consultor: ConsultorGaps, dados: dict) -> None:
    resultado = motor.inferir(MemoriaTrabalho.de_dict(base, dados["respostas"]))
    nome = (dados["nome"] or "").strip()
    st.subheader(f"Resultado{f' de {nome}' if nome else ''}")

    for aviso in resultado.avisos:
        st.warning(aviso)
    cols = st.columns(len(resultado.top))
    for i, (col, r) in enumerate(zip(cols, resultado.top), 1):
        col.metric(f"{i}º lugar: {r.nome}", f"{r.percentual:.1f}%", help="Compatibilidade com o seu perfil")
    if resultado.empates_parciais:
        pares = "; ".join(f"{base.trilhas[a].nome} ≈ {base.trilhas[b].nome}" for a, b in resultado.empates_parciais)
        lim = base.pontuacao["limiar_empate_pontos_percentuais"]
        st.info(f"Empate parcial (diferença de até {lim:.0f} p.p.): {pares}. "
                "Vale explorar as duas trilhas antes de decidir.")

    aba_rank, aba_pq, aba_plano = st.tabs(["Compatibilidade", "Por que esse resultado?", "Plano de ação"])

    with aba_rank:
        c1, c2 = st.columns(2)
        c1.plotly_chart(viz.fig_barras(resultado), width="stretch")
        c2.plotly_chart(viz.fig_radar(resultado), width="stretch")
        st.dataframe(viz.df_ranking(resultado), hide_index=True, width="stretch")

    with aba_pq:
        st.caption("Explicação do sistema: respostas que mais pesaram a favor e contra, e regras acionadas.")
        for i, r in enumerate(resultado.top, 1):
            with st.expander(f"{i}º {r.nome} - {r.percentual:.1f}%", expanded=(i == 1)):
                st.text(motor.explicar(r))

    with aba_plano:
        plano_de_acao(base, motor, consultor, dados, resultado)

    st.divider()
    col_v, col_r, _ = st.columns([1, 1, 4])
    if col_v.button("Voltar", key="btn_voltar"):
        ir_para(3)
    if col_r.button("Nova consulta", key="btn_recomecar"):
        recomecar()


def plano_de_acao(base, motor, consultor: ConsultorGaps, dados: dict, resultado) -> None:
    ids = [r.trilha_id for r in resultado.ranking]
    pos = {r.trilha_id: i for i, r in enumerate(resultado.ranking, 1)}
    restaurar("w_trilha", dados["trilha"] if dados["trilha"] in ids else None)
    if "w_trilha" not in st.session_state:
        st.session_state["w_trilha"] = resultado.top[0].trilha_id
    trilha_id = st.selectbox("Trilha para o plano", ids, key="w_trilha",
                             format_func=lambda t: f"{pos[t]}º {base.trilhas[t].nome} "
                                                   f"({resultado.por_id(t).percentual:.0f}%)")
    dados["trilha"] = trilha_id

    niveis = consultor.hab.niveis
    habilidades = consultor.hab.trilhas[trilha_id].habilidades
    avaliacao = dados["avaliacao"].setdefault(trilha_id, {})
    with st.expander("Avalie seus conhecimentos nesta trilha (opcional, deixa o plano mais preciso)"):
        st.caption("Sem resposta, o nível é estimado a partir da sua experiência informada no Passo 1.")
        opcoes = [None, *niveis]
        for h in habilidades.values():
            chave = f"w_av_{trilha_id}_{h.id}"
            restaurar(chave, avaliacao.get(h.id))
            st.selectbox(h.nome, opcoes, key=chave,
                         format_func=lambda v: "Não sei informar (estimar)" if v is None else f"{v} - {niveis[v]}",
                         help="Tecnologias: " + ", ".join(h.tecnologias))
            valor = st.session_state.get(chave)
            if valor is None:
                avaliacao.pop(h.id, None)
            else:
                avaliacao[h.id] = valor

    perfil = PerfilUsuario(dados["nivel"], dados["horas"] or 6.0, dados["nome"] or None)
    plano = consultor.plano(trilha_id, perfil, dict(avaliacao))
    a, r = plano.analise, plano.roadmap

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Prontidão para Júnior", f"{a.percentual:.1f}%")
    m2.metric("Situação", a.classificacao)
    m3.metric("Horas de estudo", f"{r.total_horas:.0f} h")
    m4.metric("Prazo estimado", f"~{r.semanas} semanas", help=f"Considerando {perfil.horas_semanais:g} h por semana.")
    if a.essenciais_pendentes:
        st.warning("Habilidades essenciais pendentes: " + "; ".join(a.essenciais_pendentes))
    else:
        st.success("Nenhuma habilidade essencial pendente.")

    t_gaps, t_road, t_cert, t_proj = st.tabs(["Gaps", "Roadmap", "Certificações", "Projetos de portfólio"])
    with t_gaps:
        st.plotly_chart(viz.fig_prontidao(a), width="stretch")
        st.dataframe(viz.df_gaps(a), hide_index=True, width="stretch")
    with t_road:
        if not r.itens:
            st.success("Sem lacunas: foque em projetos de portfólio e em candidaturas.")
        for e in r.etapas:
            st.markdown(f"**{e.titulo}** - {e.horas:.0f} h")
        if r.itens:
            st.dataframe(viz.df_roadmap(r), hide_index=True, width="stretch")
    with t_cert:
        st.dataframe(viz.df_certificacoes(r), hide_index=True, width="stretch")
        st.caption("Certificações mudam com o tempo; confira requisitos e valores no site do emissor.")
    with t_proj:
        st.dataframe(viz.df_projetos(r), hide_index=True, width="stretch")
        st.markdown("**Boas práticas para o seu GitHub**")
        for b in r.boas_praticas:
            st.markdown(f"- {b}")

    st.download_button("Baixar plano (Markdown)", relatorio_markdown(motor, resultado, plano, dados["nome"] or None),
                       file_name="plano_carreira_ti.md", mime="text/markdown", key="btn_download")


# --------------------------------------------------------------------------- #
def main() -> None:
    base, motor, consultor = carregar_ou_parar()
    dados = estado()
    passo = st.session_state["passo"]
    cabecalho(base, passo)
    barra_lateral(base)
    if passo == 1:
        passo_perfil(base, dados)
    elif passo == 2:
        passo_likert(base, dados, "afinidades", 2)
    elif passo == 3:
        passo_likert(base, dados, "objetivos", 3)
    else:
        passo_resultado(base, motor, consultor, dados)


main()
