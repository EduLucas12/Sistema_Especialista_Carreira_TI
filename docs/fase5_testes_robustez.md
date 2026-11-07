# Fase 5 — Testes de Robustez e Casos Limite

Objetivo do enunciado: testar perfis ambíguos (ex.: quem gosta de dados **e** de desenvolvimento web) e verificar se o sistema lida bem com
empates parciais e apresenta justificativas coerentes. Esta fase também procurou fragilidades em perfis degenerados, entradas inválidas e base corrompida.

```bash
pytest                          # 161 testes
python scripts/casos_limite.py  # gera a tabela de cenários abaixo
```

## Fragilidades encontradas e corrigidas
| # | Problema encontrado | Correção |
|---|---|---|
| 1 | Perfil sem diferenciação (tudo 3, tudo 5 ou tudo 1) deixava as 10 trilhas empatadas e o "Top 3" saía em ordem alfabética, parecendo uma recomendação. | O motor calcula a **diferenciação** (mais compatível − menos compatível). Abaixo de 10 p.p. o resultado é marcado como `perfil_indefinido` e a interface, o terminal e o relatório exibem um aviso. Poucas respostas (< 50%) também geram aviso. |
| 2 | O explicador citava resposta 3 (neutra) como "a favor" e fatores de peso 1 como "contra". | "A favor" passa a exigir resposta acima do neutro e "Contra" abaixo; fatores de peso efetivo < 3 não são citados. Se nada é determinante, o texto diz isso. |
| 3 | Campo ausente ou JSON inválido na base gerava `KeyError`/`JSONDecodeError` crus. | A carga converte tudo em `BaseInvalidaError` / `HabilidadesInvalidasError` com mensagem clara; o app exibe o erro em vez de um traceback. |
| 4 | Nome com quebra de linha podia injetar um título extra no relatório Markdown. | O nome é normalizado (espaços colapsados, máx. 60 caracteres). |

Limiar de 10 p.p. calibrado por simulação: só **0,03%** de 3.000 perfis aleatórios completos foram marcados como indefinidos (diferenciação mínima observada: 8,8 p.p.),
contra 8,4% de perfis "quase neutros" (respostas 2–4, maioria 3).

## O que é testado (`tests/test_robustez.py`, 49 testes)
- **Perfis ambíguos (6 pares):** dados+web, dados+eng. de dados, infra+segurança, produto+UX, mobile+web, back-end+nuvem. As duas trilhas devem aparecer no Top 3, o perfil **não** pode
  ser marcado como indefinido, e a justificativa de cada trilha deve citar o fator que mais a puxou.
- **Empates:** desempate estável (mesmo resultado em qualquer ordem de respostas); empate parcial aparece no relatório.
- **Degenerados:** tudo 1/3/5 (aviso de perfil indefinido), uma única resposta (não gera 100% para várias trilhas), respostas contraditórias (penalidade acionada **e** explicada),
  penalidade e bônus na mesma trilha (soma líquida), teto de ajustes.
- **Explicador:** neutro não é citado; fator de peso baixo não aparece; regras citadas = regras realmente ativas.
- **Propriedades com perfis aleatórios (semente fixa):** invariantes gerais (400 perfis, completos e parciais), ordem das respostas irrelevante, **monotonicidade** (subir uma resposta nunca reduz a base de nenhuma trilha),
  **estabilidade** (mudar uma resposta em 1 ponto altera a base no máximo em `peso/Σpesos/4`), regras ativas conferidas por uma avaliação independente, explicação coerente com as respostas.
- **Entradas inválidas e base corrompida:** respostas fora da escala/tipo, arquivo inexistente, JSON malformado, campo ausente, tipo errado.
- **Plano e relatório:** horas semanais extremas (0,5 a 80) e nomes estranhos (vazio, HTML, Markdown, quebra de linha, 500 caracteres).

Na interface (`tests/test_app.py`, 22 testes no total): aviso de perfil indefinido, nomes estranhos, horas nos limites, troca repetida de trilha, avaliação de uma trilha sem vazar para outra e erro legível com base corrompida.

## Cenários (saída de `scripts/casos_limite.py`)
Nos cenários "A + B", as demais perguntas foram respondidas com 2 (baixa afinidade), o que também aciona penalidades de outras trilhas.

| Cenário | Top 3 (compatibilidade) | Diferenciação | Empates parciais | Avisos |
|---|---|---|---|---|
| Tudo neutro (3) | Back-end 50%; Cibersegurança 50%; Cientista de Dados 50% | 0 p.p. | Back-end ≈ Cibersegurança, Cibersegurança ≈ Cientista de Dados, Cientista de Dados ≈ Cloud Architecture | perfil indefinido |
| Tudo máximo (5) | Back-end 100%; Cibersegurança 100%; Cientista de Dados 100% | 0 p.p. | Back-end ≈ Cibersegurança, Cibersegurança ≈ Cientista de Dados, Cientista de Dados ≈ Cloud Architecture | perfil indefinido |
| Tudo mínimo (1) | Back-end 0%; Cibersegurança 0%; Cientista de Dados 0% | 0 p.p. | Back-end ≈ Cibersegurança, Cibersegurança ≈ Cientista de Dados, Cientista de Dados ≈ Cloud Architecture | perfil indefinido |
| Apenas 1 pergunta respondida (mobile = 5) | Mobile 58%; Front-end / UX 52%; QA / Qualidade 51% | 8 p.p. | Front-end / UX ≈ QA / Qualidade, QA / Qualidade ≈ Cibersegurança | perfil indefinido; poucas respostas |
| Dados + Web | Front-end / UX 65%; Cientista de Dados 63%; Engenheiro de Dados 37% | 62 p.p. | Front-end / UX ≈ Cientista de Dados, Engenheiro de Dados ≈ Mobile | - |
| Dados + Engenharia de Dados | Engenheiro de Dados 58%; Back-end 51%; Cientista de Dados 29% | 49 p.p. | - | - |
| Infraestrutura + Segurança | DevOps / SRE 54%; Cibersegurança 50%; Cloud Architecture 42% | 54 p.p. | - | - |
| Produto + UX | Product Management 67%; Front-end / UX 36%; QA / Qualidade 27% | 67 p.p. | - | - |
| Mobile + Web | Front-end / UX 71%; Mobile 64%; QA / Qualidade 28% | 71 p.p. | - | - |
| Contraditório: quer Mobile, não gosta de programar | Product Management 50%; Cibersegurança 47%; Cloud Architecture 47% | 28 p.p. | Cibersegurança ≈ Cloud Architecture, Cloud Architecture ≈ QA / Qualidade | - |
| Contraditório: design máximo, sem web nem código | Product Management 55%; QA / Qualidade 47%; Cientista de Dados 47% | 34 p.p. | QA / Qualidade ≈ Cientista de Dados, Cientista de Dados ≈ Cloud Architecture | - |
| Gosta de tudo, menos de gestão/comunicação | DevOps / SRE 100%; Cientista de Dados 99%; Engenheiro de Dados 99% | 48 p.p. | DevOps / SRE ≈ Cientista de Dados, Cientista de Dados ≈ Engenheiro de Dados, Engenheiro de Dados ≈ Front-end / UX | - |

## Limitações conhecidas
- Em perfis indefinidos o desempate final é alfabético (determinístico, mas arbitrário); por isso o sistema **avisa** em vez de fingir uma recomendação.
- O aviso de "perfil indefinido" não distingue "gosto de tudo" de "não gosto de nada" nem de "estou em dúvida"; a mensagem pede mais contraste nas respostas.
- Os pesos são heurísticos: os testes verificam coerência interna e comportamento esperado em perfis típicos, não a "verdade" do mercado.
