---
name: migracoes-seguras
description: Avalia migrações de banco para detectar operações perigosas e propor estratégias seguras como expand/contract, RunSQL controlado e backfill em etapas. Use ao revisar migrations, alterações de schema e deploys com risco de downtime.
---

# Migrações Seguras

## Objetivo

Detectar riscos em migrações e sugerir plano executável com mínimo downtime e rollback viável.

## O que considerar perigoso

- Adicionar coluna `NOT NULL` sem default/backfill prévio.
- Remover/renomear coluna usada por código já em produção.
- Alterar tipo de coluna com lock alto ou conversão custosa.
- Criar índice pesado sem modo concorrente quando disponível.
- `RunSQL` sem `reverse_sql` ou sem janela operacional definida.
- Backfill massivo em transação única.

## Estratégia recomendada

1. **Expand**
   - Adicionar estruturas novas de forma compatível.
   - Manter leitura/escrita coexistindo (dual-read/dual-write quando necessário).

2. **Backfill**
   - Migrar dados em lotes idempotentes.
   - Monitorar progresso e impacto.

3. **Contract**
   - Remover estruturas legadas só após código novo estabilizado.
   - Validar ausência de uso antes de drop/rename definitivo.

## Uso de RunSQL

- Exigir justificativa técnica para SQL manual.
- Incluir `reverse_sql` quando possível.
- Documentar pré-condições e pós-validação.

## Formato de saída

```markdown
## Riscos detectados
- [alto|médio|baixo] <operação>: <risco>
  - Evidência: <migration/trecho>

## Estratégia sugerida
- Fase 1 (expand): <passos>
- Fase 2 (backfill): <passos>
- Fase 3 (contract): <passos>

## Plano de validação
- Checks antes: <itens>
- Checks depois: <itens>
- Rollback: <como reverter>
```

## Critérios de qualidade

- Evitar migração não reversível sem mitigação explícita.
- Sempre propor plano em fases para mudanças destrutivas.
- Considerar impacto operacional, não só corretude funcional.
