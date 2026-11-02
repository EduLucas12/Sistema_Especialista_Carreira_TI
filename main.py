"""Consulta no terminal (Fases 2 e 3). A interface Streamlit vem na Fase 4.

Uso:
    python main.py                                   # consulta interativa completa
    python main.py --exemplo dados                   # perfil de exemplo: dados | devops | frontend
    python main.py --exemplo devops --nivel basico --horas 8
    python main.py --exemplo dados --trilha engenheiro_dados   # plano para outra trilha do Top 3
"""
import argparse

from carreiras.base_conhecimento import carregar_base
from carreiras.gaps_roadmap import ConsultorGaps, PerfilUsuario, formatar_plano
from carreiras.motor_inferencia import MemoriaTrabalho, MotorInferencia

EXEMPLOS = {
    "dados": {"matematica": 5, "programacao": 4, "analise_dados": 5, "machine_learning": 5,
              "pipelines_dados": 3, "apis_bancos": 3, "qualidade": 3, "comunicacao": 3,
              "obj_especializacao": 5, "interfaces_web": 1, "design_visual": 1, "mobile": 1},
    "devops": {"infraestrutura": 5, "automacao": 5, "pressao": 4, "arquitetura": 4, "seguranca": 3,
               "programacao": 3, "obj_especializacao": 4, "design_visual": 1, "gestao_produto": 1},
    "frontend": {"interfaces_web": 5, "design_visual": 5, "experiencia_usuario": 5, "programacao": 4,
                 "obj_criatividade": 5, "infraestrutura": 1, "matematica": 2, "machine_learning": 1},
}
NIVEIS_EXPERIENCIA = ["iniciante", "basico", "intermediario", "avancado"]


def perguntar_afinidades(base) -> MemoriaTrabalho:
    mem = MemoriaTrabalho()
    esc = ", ".join(f"{k}={v}" for k, v in base.rotulos_escala.items())
    print(f"Responda de {base.escala_min} a {base.escala_max} ({esc}). Enter = pular.\n")
    for etapa in ("afinidades", "objetivos"):
        print(f"== {base.etapas[etapa]['titulo']} ==")
        for p in base.perguntas_da_etapa(etapa):
            while True:
                txt = input(f"- {p.texto} ").strip()
                if not txt:
                    break
                try:
                    mem.responder(base, p.id, int(txt))
                    break
                except ValueError as e:
                    print(f"  ! {e}")
    return mem


def perguntar_perfil() -> PerfilUsuario:
    print("\n== Perfil ==")
    while True:
        nivel = input(f"Seu nível atual {NIVEIS_EXPERIENCIA}: ").strip().lower()
        if nivel in NIVEIS_EXPERIENCIA:
            break
    while True:
        try:
            horas = float(input("Horas por semana para estudar: ").replace(",", "."))
            if 0 < horas <= 80:
                break
        except ValueError:
            pass
    return PerfilUsuario(nivel, horas)


def perguntar_habilidades(consultor: ConsultorGaps, trilha_id: str) -> dict[str, int]:
    niveis = ", ".join(f"{k}={v}" for k, v in consultor.hab.niveis.items())
    print(f"\n== Seu conhecimento atual na trilha ({niveis}). Enter = estimar pelo seu nível ==")
    avaliacao: dict[str, int] = {}
    for h in consultor.hab.trilhas[trilha_id].habilidades.values():
        while True:
            txt = input(f"- {h.nome}: ").strip()
            if not txt:
                break
            if txt in {"0", "1", "2", "3"}:
                avaliacao[h.id] = int(txt)
                break
    return avaliacao


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exemplo", choices=EXEMPLOS)
    ap.add_argument("--nivel", choices=NIVEIS_EXPERIENCIA, default="iniciante")
    ap.add_argument("--horas", type=float, default=6.0)
    ap.add_argument("--trilha", help="id da trilha para o plano (padrão: a 1ª do ranking)")
    args = ap.parse_args()

    base = carregar_base()
    motor = MotorInferencia(base)
    consultor = ConsultorGaps(base=base)
    interativo = args.exemplo is None

    mem = perguntar_afinidades(base) if interativo else MemoriaTrabalho.de_dict(base, EXEMPLOS[args.exemplo])
    perfil = perguntar_perfil() if interativo else PerfilUsuario(args.nivel, args.horas)

    resultado = motor.inferir(mem)
    print("\n=== Top 3 carreiras compatíveis ===\n")
    print(motor.relatorio(resultado))

    trilha_id = args.trilha or resultado.top[0].trilha_id
    avaliacao = perguntar_habilidades(consultor, trilha_id) if interativo else None
    print()
    print(formatar_plano(consultor.plano(trilha_id, perfil, avaliacao)))


if __name__ == "__main__":
    main()
