"""Executa cenários limite/ambíguos e imprime uma tabela em Markdown (usada em docs/fase5).

Uso:  python scripts/casos_limite.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from carreiras.base_conhecimento import carregar_base
from carreiras.motor_inferencia import MotorInferencia


def uniforme(base, v, **kw):
    r = {p: v for p in base.perguntas}
    r.update(kw)
    return r


def cenarios(base):
    return {
        "Tudo neutro (3)": uniforme(base, 3),
        "Tudo máximo (5)": uniforme(base, 5),
        "Tudo mínimo (1)": uniforme(base, 1),
        "Apenas 1 pergunta respondida (mobile = 5)": {"mobile": 5},
        "Dados + Web": uniforme(base, 2, analise_dados=5, machine_learning=4, matematica=4,
                                interfaces_web=5, design_visual=4, experiencia_usuario=4, programacao=5),
        "Dados + Engenharia de Dados": uniforme(base, 2, analise_dados=5, pipelines_dados=5,
                                                programacao=5, apis_bancos=4),
        "Infraestrutura + Segurança": uniforme(base, 2, infraestrutura=5, seguranca=5, automacao=4, pressao=4),
        "Produto + UX": uniforme(base, 2, gestao_produto=5, comunicacao=5, experiencia_usuario=5,
                                 design_visual=4, obj_impacto_negocio=5),
        "Mobile + Web": uniforme(base, 2, mobile=5, interfaces_web=5, design_visual=4,
                                 experiencia_usuario=5, programacao=5),
        "Contraditório: quer Mobile, não gosta de programar": uniforme(base, 3, mobile=5, programacao=1),
        "Contraditório: design máximo, sem web nem código": uniforme(base, 3, design_visual=5, experiencia_usuario=5,
                                                                      interfaces_web=1, programacao=1),
        "Gosta de tudo, menos de gestão/comunicação": uniforme(base, 5, gestao_produto=1, comunicacao=1),
    }


def main() -> None:
    base = carregar_base()
    motor = MotorInferencia(base)
    print("| Cenário | Top 3 (compatibilidade) | Diferenciação | Empates parciais | Avisos |")
    print("|---|---|---|---|---|")
    for nome, resp in cenarios(base).items():
        res = motor.inferir(resp)
        top = "; ".join(f"{r.nome} {r.percentual:.0f}%" for r in res.top)
        emp = ", ".join(f"{base.trilhas[a].nome} ≈ {base.trilhas[b].nome}" for a, b in res.empates_parciais) or "-"
        avisos = "perfil indefinido" if res.perfil_indefinido else ""
        if res.poucas_respostas:
            avisos = (avisos + "; " if avisos else "") + "poucas respostas"
        print(f"| {nome} | {top} | {res.diferenciacao * 100:.0f} p.p. | {emp} | {avisos or '-'} |")


if __name__ == "__main__":
    main()
