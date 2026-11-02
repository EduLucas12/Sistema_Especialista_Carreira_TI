# Fase 3 — Módulo de Recomendação de Gaps e Roadmap

Código em `carreiras/gaps_roadmap.py`; conhecimento em `data/habilidades_roadmap.json` (separado do código, como na Fase 1).

## Base de conhecimento da fase
Para cada uma das 10 trilhas: 10–11 **habilidades** (id, nome, prioridade `essencial/importante/desejavel`, nível exigido para Júnior,
horas por nível, pré-requisitos, bloco, tecnologias), 3 **certificações** (com a prontidão mínima para recomendá-las) e 3 **projetos de portfólio**
(dificuldade 1–3 e habilidades que exercitam). Também há as boas práticas de portfólio no GitHub.

Escala de nível de habilidade: `0` nunca estudei · `1` conheço o básico · `2` aplico com autonomia · `3` domino.
Para ser **Júnior**, cada habilidade exige nível 1 ou 2 (`nivel_junior`).

## Como o nível atual do usuário é obtido
1. **Informado:** o usuário avalia as habilidades da trilha (0–3). Tem prioridade.
2. **Estimado:** o que não foi informado vem do nível de experiência do Passo 1 (`iniciante`, `basico`, `intermediario`, `avancado`), por bloco:

| Experiência | Fundamentos | Ferramentas | Prática |
|---|---|---|---|
| iniciante | 0 | 0 | 0 |
| basico | 1 | 0 | 0 |
| intermediario | 2 | 1 | 0 |
| avancado | 2 | 2 | 1 |

## Análise de gaps
- `gap = max(0, nivel_junior − nivel_atual)` (nível acima do exigido não gera "crédito" extra).
- `prontidão = Σ(peso · min(atual, exigido)) / Σ(peso · exigido)`, com pesos essencial = 3, importante = 2, desejável = 1.
- **Classificação:** `Pronto para vagas Júnior` (≥ 85% e nenhuma essencial pendente) · `Quase lá` (≥ 65%) · `Em formação` (≥ 35%) · `Início da jornada`.
  Prontidão alta com uma habilidade essencial pendente nunca é "pronto".

## Roadmap
- Entram só as habilidades com gap. Ordem: **pré-requisitos primeiro** (ordenação topológica), agrupadas em **Fundamentos → Ferramentas → Prática**;
  dentro de cada bloco, vem antes o que tem maior `prioridade × gap`.
- Horas = `horas_por_nivel × gap`; semanas = `⌈horas totais / horas por semana⌉`.
- **Tecnologias a estudar** vêm de cada habilidade; **certificações** são marcadas como "agora" quando a prontidão atinge o mínimo da certificação.
- **Projetos** vêm do mais simples ao mais avançado; "agora" para dificuldade 1 (prontidão < 50%), até 2 (< 80%) ou 3 (≥ 80%), com a lista de lacunas que cada um treina.

## Validação da base (`validar_habilidades`)
Rejeita: trilhas diferentes das de `regras_carreiras.json`, prioridade/bloco/nível inválidos, pré-requisito inexistente, **ciclo** de pré-requisitos,
pré-requisito em bloco posterior, projeto com habilidade inexistente e certificação com prontidão fora de [0, 1].

## Como testar
```bash
python main.py --exemplo devops --nivel basico --horas 8
python main.py --exemplo dados --trilha engenheiro_dados     # plano para outra trilha do Top 3
python main.py                                               # consulta completa, com avaliação das habilidades
pytest                                                       # 86 testes
```

## Limitações (para o relatório)
- Habilidades, horas e certificações são estimativas do engenheiro do conhecimento, não dados de mercado em tempo real; certificações e preços mudam.
- A estimativa por nível de experiência é grosseira; a avaliação individual (0–3) é mais fiel e a interface da Fase 4 vai pedi-la.
