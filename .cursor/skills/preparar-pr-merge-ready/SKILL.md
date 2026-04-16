---
name: preparar-pr-merge-ready
description: Mantém PR pronto para merge com ciclo iterativo de triagem de comentários, resolução de conflitos, execução de CI e ajustes finais. Use quando a PR estiver em revisão, com feedback pendente ou falhas de pipeline.
---

# Preparar PR Merge-Ready

## Objetivo

Conduzir um loop de estabilização até a PR ficar apta para merge.

## Loop padrão

Repita até não haver pendências:

1. **Triagem de comentários**
   - Coletar comentários abertos.
   - Classificar: bug, risco, melhoria, nit.
   - Priorizar itens bloqueantes.

2. **Implementar ajustes**
   - Corrigir itens aprovados.
   - Responder comentário com evidência objetiva da mudança.

3. **Resolver conflitos**
   - Atualizar branch com base atual.
   - Resolver conflito preservando comportamento esperado.

4. **Executar validações**
   - Rodar testes relevantes localmente.
   - Rodar lint/format/checks.
   - Confirmar CI verde.

5. **Reavaliar estado da PR**
   - Verificar se ainda há comentários pendentes.
   - Confirmar diff limpo (sem mudanças acidentais).

## Critérios de pronto para merge

- Sem comentários bloqueantes pendentes.
- CI principal passando.
- Conflitos resolvidos.
- Escopo da PR claro e estável.

## Formato de acompanhamento

```markdown
## Status do loop
- Iteração: <n>
- Comentários pendentes: <qtd>
- CI: <verde|vermelho>
- Conflitos: <sim|não>

## Ações realizadas
- <ação 1>
- <ação 2>

## Próximo passo
- <ação objetiva para fechar pendência>
```

## Regras de segurança

- Não fechar comentário sem evidência.
- Não ignorar falha intermitente sem registrar mitigação.
- Não misturar refactor amplo em PR de correção pontual.
