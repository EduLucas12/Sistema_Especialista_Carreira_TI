# Fase 2 — Motor de Inferência com Pontuação

Implementação em `carreiras/motor_inferencia.py`. Lê a base (`data/regras_carreiras.json`), processa as respostas e devolve o ranking.

## Componentes (arquitetura das aulas)
| Componente | Classe/função |
|---|---|
| Memória de Trabalho (fatos da sessão) | `MemoriaTrabalho` — valida pergunta existente, inteiro e dentro da escala 1–5 |
| Base de Conhecimento | `BaseConhecimento` (Fase 1) |
| Máquina de Inferência | `MotorInferencia.inferir` |
| Explicador ("por quê / como") | `MotorInferencia.explicar` e `relatorio` |

## Algoritmo (para cada uma das 10 trilhas)
1. **Normalização:** `n = (resposta − 1) / 4`. Pergunta **não respondida** = `0,5` (neutro: falta de informação não favorece nem prejudica).
2. **Pontuação base:** `base = Σ(peso · peso_etapa · n) / Σ(peso · peso_etapa)` — cada resposta multiplica o peso da regra correspondente.
3. **Regras (encadeamento para frente):** para cada regra cujas condições (E lógico) casam com a memória de trabalho, soma-se o ajuste da trilha — negativo para penalidade, positivo para bônus. Condição sobre pergunta não respondida é falsa.
4. **Teto:** `ajuste = clamp(Σ ajustes, −0,5, +0,5)`.
5. **Final:** `compatibilidade = clamp(base + ajuste, 0, 1)`.
6. **Ranking:** ordena por compatibilidade, depois `base`, depois nome (resultado determinístico). Devolve Top 3 e todas as 10 trilhas.
7. **Empate parcial:** pares consecutivos entre as posições 1–4 com diferença ≤ 2 p.p. são sinalizados (`empates_parciais`) — a interface (Fase 4) mostrará o aviso.

## Explicador
Para cada trilha: respostas que mais a favor (`A favor`), o que pesa contra (`Contra`) e as regras acionadas, com o ajuste em pontos percentuais. Exemplo:

```
1º Cientista de Dados: 81.5% (base 76.5% +5.0 p.p. das regras)
  A favor: análise de dados (resposta 5/5); machine learning e IA (resposta 5/5); ...
  Bônus R15 (+5 p.p.): Matemática, análise de dados e machine learning juntos reforçam Ciência de Dados.
```

## Como testar
```bash
python main.py --exemplo dados     # ou devops | frontend
python main.py                     # consulta interativa no terminal
pytest                             # 42 testes
```

## Decisão de projeto: perguntas não respondidas
A primeira versão ignorava perguntas não respondidas. O teste `test_perguntas_nao_respondidas_sao_neutras` revelou o defeito: quem respondia
só "mobile = 5" fazia várias trilhas chegarem a 100% (cada uma só "via" a pergunta favorável) e o desempate virava ordem alfabética.
Por isso, resposta ausente agora conta como neutra (0,5).

## Limitações conhecidas (tratadas na Fase 5)
- Pesos heurísticos; podem ser calibrados com os casos de borda.
- Em perfis com tudo em 3 (neutro) todas as trilhas ficam em 50%: o sistema sinaliza o empate, mas não consegue recomendar.
