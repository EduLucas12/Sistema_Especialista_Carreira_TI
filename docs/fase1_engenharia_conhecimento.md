# Fase 1 — Engenharia do Conhecimento e Modelagem JSON

## 1. Papéis (aula de Sistemas Especialistas)
- **Especialista:** conhecimento comum de mercado sobre o que cada trilha de TI exige (fonte: descrições de vagas, roadmaps públicos).
- **Engenheiro do Conhecimento:** converte esse conhecimento em pesos e regras SE–ENTÃO (este documento + JSON).
- **Implementador:** código Python que lê o JSON (`carreiras/base_conhecimento.py`).

## 2. Estrutura do `regras_carreiras.json`

| Seção | Conteúdo |
|---|---|
| `metadados` | nome, versão, fase |
| `escala_likert` | mínimo/máximo (1–5) e rótulos ("Nenhuma afinidade" … "Muita afinidade") |
| `etapas` | as 3 etapas do wizard; `afinidades` (peso 1.0) e `objetivos` (peso 0.6) pontuam; `perfil` não pontua |
| `perfil` | campos do Passo 1 (nome, nível atual, horas semanais) — usados nos gaps/roadmap (Fase 3) |
| `pontuacao` | fórmula, `top_n`, teto de ajustes, limiar de empate |
| `perguntas` | 22 perguntas Likert (18 afinidades + 4 objetivos), cada uma com `rotulo` curto para justificativas |
| `trilhas` | as 10 trilhas, cada uma com `pesos` esparsos `{pergunta: peso 0–10}` |
| `regras` | 17 regras (13 penalidades, 4 bônus) com condições E-lógicas e ajustes por trilha |

## 3. Modelo de incerteza / ponderação

1. Resposta Likert `r ∈ [1,5]` é normalizada: `n = (r − 1) / 4` → 0 a 1 (respostas graduais, não binárias).
2. Pontuação base da trilha: `base = Σ(peso · peso_etapa · n) / Σ(peso · peso_etapa)`.
3. Regras ativas somam ajustes (penalidade = −, bônus = +) à `base`.
4. `compatibilidade = clamp(base + ajustes, 0, 1)` → exibida em %.

Regra em formato SE–ENTÃO (exemplo `R04`):
> SE `programacao ≤ 2` ENTÃO penalizar Back-end (−20 p.p.), Mobile (−20), Eng. de Dados (−15), Front-end (−15), DevOps (−5).

Isso trata **perfis conflitantes** (ex.: quer Mobile mas não gosta de programar) e **sinergias** (ex.: infraestrutura + automação altas reforçam DevOps).

## 4. Matriz de pesos (pergunta × trilha)

Rodar `python scripts/inspecionar_base.py` imprime a matriz completa. Princípios usados:
- Cada trilha tem uma pergunta "identidade" com peso 10 (ex.: `mobile` → Mobile, `seguranca` → Cibersegurança).
- Trilhas vizinhas compartilham pesos médios (ex.: Eng. de Dados e Cientista de Dados em `analise_dados`; DevOps e Cloud em `infraestrutura`).
- Objetivos têm peso menor que afinidades (`peso_etapa = 0.6`), pois indicam preferência, não aptidão.

## 5. Decisões e limitações (para o relatório)
- Pesos são **heurísticos**, definidos pelo engenheiro do conhecimento; podem ser calibrados na Fase 5 com casos de teste.
- Normalizar por `Σ peso` evita favorecer trilhas com mais perguntas relevantes.
- Gaps e roadmap (tecnologias, certificações, projetos) ficam em arquivo de conhecimento próprio na Fase 3, pois dependem do nível atual do usuário.

## 6. Validação automática
`carreiras/base_conhecimento.py` rejeita a base se houver: pergunta/trilha/regra duplicada, referência inexistente, peso negativo,
operador inválido, valor fora da escala, ajuste fora de (0,1], pergunta órfã ou número de trilhas ≠ 10. Coberto por `tests/test_base_conhecimento.py`.
