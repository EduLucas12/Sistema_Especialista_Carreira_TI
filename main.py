"""Consulta interativa no terminal (Fase 2). A interface Streamlit vem na Fase 4.

Uso:
    python main.py              # pergunta tudo no terminal
    python main.py --exemplo dados | devops | frontend
"""
import argparse

from carreiras.base_conhecimento import carregar_base
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


def perguntar(base) -> MemoriaTrabalho:
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exemplo", choices=EXEMPLOS)
    args = ap.parse_args()
    motor = MotorInferencia(carregar_base())
    mem = MemoriaTrabalho.de_dict(motor.base, EXEMPLOS[args.exemplo]) if args.exemplo else perguntar(motor.base)
    print("\n=== Top 3 carreiras compatíveis ===\n")
    print(motor.relatorio(motor.inferir(mem)))


if __name__ == "__main__":
    main()
