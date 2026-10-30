# Consultor de Carreiras em TI — Sistema Especialista com Pontuação Ponderada

**UNIPAC Barbacena · Ciência da Computação · Inteligência Artificial**
Prof. Felipe Roncalli de Paula Carneiro · Trabalho Etapa 2

Sistema Especialista baseado em regras, com tratamento de incerteza (escala Likert 1–5) e pontuação ponderada, que
recomenda um **Top 3** entre 10 trilhas de TI, identifica **gaps** de competência e gera um **roadmap** personalizado.

## Arquitetura (conforme as aulas de Sistemas Especialistas)

| Componente | Onde fica |
|---|---|
| Base de Conhecimento (perguntas, pesos, regras) | `data/regras_carreiras.json` |
| Memória de Trabalho (respostas da sessão) | Fase 2 |
| Motor de Inferência (pontuação ponderada + regras) | Fase 2 |
| Explicador (por que / como) | Fase 2–3 |
| Interface com o usuário (Streamlit, wizard) | Fase 4 |

## Fases

- [x] **Fase 1 — Engenharia do Conhecimento e modelagem JSON** (`docs/fase1_engenharia_conhecimento.md`)
- [ ] Fase 2 — Motor de Inferência com pontuação
- [ ] Fase 3 — Gaps e Roadmap
- [ ] Fase 4 — Interface Streamlit
- [ ] Fase 5 — Testes de robustez e casos limite

## Como rodar (PyCharm / terminal)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
python scripts/inspecionar_base.py   # valida a base e mostra a matriz de pesos
pytest                               # testes da base de conhecimento
```

No PyCharm: *File → Open* na pasta do projeto, configure o interpretador (`.venv`) e marque a pasta raiz como
*Sources Root* se necessário.

## Estrutura

```
carreiras/            pacote Python (loader/validador da base; motor entra na Fase 2)
data/                 regras_carreiras.json (conhecimento fora do código)
docs/                 documentação por fase
scripts/              utilitários (inspeção da base)
tests/                testes automatizados
```
