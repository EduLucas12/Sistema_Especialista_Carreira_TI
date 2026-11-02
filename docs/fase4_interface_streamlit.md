# Fase 4 — Interface Web (Streamlit)

Arquivo principal: `app.py`. Como a lógica está toda em `carreiras/`, o app só cuida da apresentação.

```bash
pip install -r requirements.txt
streamlit run app.py          # abre em http://localhost:8501
```

No PyCharm: *Run → Edit Configurations → + → Python*, escolha **Module name** `streamlit`, **Parameters** `run app.py`
e como *Working directory* a pasta do projeto. Ou use o terminal do PyCharm com o comando acima.

## Fluxo (wizard em etapas)
| Etapa | Conteúdo |
|---|---|
| 1. Perfil pessoal | nome (opcional), nível atual, horas por semana (campos lidos do `regras_carreiras.json`) |
| 2. Afinidades técnicas | 18 perguntas na escala Likert 1–5 |
| 3. Objetivos de carreira | 4 perguntas Likert (liderança, criatividade, especialização, impacto no negócio) |
| Resultado | Top 3, gráficos, justificativas e plano de ação |

- Barra de progresso, botões *Voltar/Avançar* e bloqueio com aviso se faltar resposta.
- As respostas ficam guardadas em `st.session_state["dados"]`: ao voltar, nada se perde.
- Barra lateral explica o funcionamento e a escala; botão *Recomeçar*.

## Tela de resultado
- **Compatibilidade:** métricas do Top 3, aviso de **empate parcial**, gráfico de **barras** (Top 3 destacado), **radar** das 10 trilhas e tabela completa.
- **Por que esse resultado?:** o texto do Explicador (respostas a favor/contra e regras acionadas) para cada trilha do Top 3.
- **Plano de ação:** escolha da trilha (padrão: a 1ª), avaliação opcional das habilidades (0–3, senão estima pelo nível do Passo 1),
  métricas (prontidão, situação, horas, prazo) e abas **Gaps**, **Roadmap**, **Certificações** e **Projetos de portfólio**.
  Há botão para baixar o plano em Markdown (`carreiras/relatorio.py`).

## Organização do código
| Arquivo | Papel |
|---|---|
| `app.py` | telas, navegação e estado da sessão |
| `carreiras/visualizacao.py` | tabelas (pandas) e gráficos (plotly), testáveis sem navegador |
| `carreiras/relatorio.py` | relatório em Markdown |

## Testes
`tests/test_app.py` usa o `AppTest` do Streamlit para percorrer o wizard sem navegador: bloqueios de avanço, preservação de respostas ao voltar,
fluxo completo com resultado coerente, troca de trilha, efeito da avaliação de habilidades e reinício. `tests/test_visualizacao.py` cobre tabelas,
gráficos e relatório. Total do projeto: 98 testes (`pytest`).

## Decisões
- Perguntas sem resposta bloqueiam o avanço na interface (o motor aceitaria respostas parciais, tratadas como neutras).
- `streamlit>=1.50`: o app usa `width="stretch"` nos gráficos e tabelas.
