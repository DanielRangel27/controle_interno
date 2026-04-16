---
name: django-debugger
description: Diagnostica tracebacks de Django para identificar causa raiz provável, sugerir correção objetiva e indicar teste de regressão. Use quando houver traceback, exceção em Django, erro em produção ou falha de teste com stack trace.
---

# Django Debugger

## Objetivo

Dado um traceback, entregar:
1. Causa provável.
2. Fix recomendado.
3. Teste para evitar regressão.

## Fluxo

1. **Ler o traceback por completo**
   - Capturar tipo da exceção, mensagem e último frame da aplicação (não de libs).
   - Ignorar frames de framework quando não forem a origem.

2. **Localizar a causa raiz**
   - Mapear arquivo/função da aplicação onde o erro nasce.
   - Classificar o problema: validação, acesso a atributo nulo, query inválida, chave ausente, serialização, permissão, etc.

3. **Sugerir correção mínima e segura**
   - Priorizar correção no ponto de origem.
   - Evitar “silenciar” erro com `try/except` amplo sem ação corretiva.
   - Indicar mudança concreta (ex.: validação prévia, `select_related`, checagem de `None`, ajuste de serializer, transação atômica).

4. **Indicar teste de regressão**
   - Definir tipo: unitário, integração, API.
   - Descrever cenário de entrada, resultado esperado e assert principal.
   - Garantir que o teste falha antes do fix e passa depois.

## Heurísticas rápidas

- `DoesNotExist` / `MultipleObjectsReturned`: revisar filtros e suposições de unicidade.
- `IntegrityError`: validar constraints, ordem de escrita e transações.
- `AttributeError: 'NoneType'`: validar pré-condições e relações opcionais.
- `KeyError` / `ValidationError`: reforçar contrato de entrada.
- Timeout/lentidão em view: investigar N+1 e falta de índices.

## Formato de resposta

Use este formato:

```markdown
## Diagnóstico
- Exceção: <tipo>
- Causa provável: <causa objetiva>
- Evidências no traceback: <arquivo/função/linha e mensagem>

## Fix sugerido
- Mudança recomendada: <o que alterar e onde>
- Risco/impacto: <baixo|médio|alto> e por quê

## Teste recomendado
- Tipo: <unit|integration|api>
- Cenário: <arranjo>
- Assert principal: <resultado esperado>
```

## Critérios de qualidade

- Ser específico sobre o ponto de falha.
- Não propor refactor amplo quando um fix localizado resolve.
- Sempre incluir teste de regressão.
