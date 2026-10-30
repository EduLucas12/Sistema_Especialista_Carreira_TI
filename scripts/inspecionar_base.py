"""Valida a base e imprime a matriz de pesos (perguntas x trilhas) com pandas.

Uso:  python scripts/inspecionar_base.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from carreiras.base_conhecimento import carregar_base


def matriz_pesos(base) -> pd.DataFrame:
    dados = {t.nome: {pid: t.pesos.get(pid, 0) for pid in base.perguntas} for t in base.trilhas.values()}
    return pd.DataFrame(dados)


if __name__ == "__main__":
    base = carregar_base()
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", None)
    print(f"Base v{base.metadados['versao']} OK: {len(base.perguntas)} perguntas, "
          f"{len(base.trilhas)} trilhas, {len(base.regras)} regras\n")
    m = matriz_pesos(base)
    print(m.to_string())
    print("\nSoma dos pesos por trilha:")
    print(m.sum().to_string())
