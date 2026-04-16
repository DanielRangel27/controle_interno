---
name: api-review-checklist
description: Audita endpoints de API com checklist de autenticação, validação, status codes, performance (N+1), paginação e observabilidade. Use ao revisar endpoints, PRs de backend ou qualidade de contrato HTTP.
---

# API Review Checklist

## Objetivo

Executar uma auditoria rápida e prática de endpoint com foco em segurança, corretude e performance.

## Checklist principal

- [ ] **Autenticação e autorização**
  - Endpoint exige autenticação quando necessário.
  - Regras de autorização (perfil/owner/tenant) estão explícitas.
- [ ] **Validação de entrada**
  - Campos obrigatórios, tipos, limites e formatos validados.
  - Campos desconhecidos tratados de forma consistente.
- [ ] **Status codes e contrato**
  - Códigos HTTP coerentes (`200/201/204/400/401/403/404/409/422/500`).
  - Erros retornam payload padronizado.
- [ ] **N+1 e acesso a dados**
  - Listagens usam `select_related/prefetch_related` (ou equivalente).
  - Consultas repetidas por item foram eliminadas.
- [ ] **Paginação**
  - Endpoints de lista paginam por padrão.
  - Há limite máximo de `page_size/limit`.
- [ ] **Logs e rastreabilidade**
  - Eventos importantes logados sem dados sensíveis.
  - Correlação por request id / trace id quando aplicável.

## Fluxo de auditoria

1. Ler código do endpoint e camada de serviço/repositório.
2. Validar checklist por categoria.
3. Classificar achados por severidade: `crítico`, `alto`, `médio`, `baixo`.
4. Sugerir correção objetiva para cada achado.
5. Indicar testes faltantes.

## Formato de saída

```markdown
## Achados
- [severidade] <tema>: <problema>
  - Evidência: <arquivo/símbolo/comportamento>
  - Correção sugerida: <ação objetiva>

## Cobertura de testes recomendada
- <teste 1>
- <teste 2>

## Decisão
- Aprovado com ressalvas | Requer ajustes antes do merge
```

## Critérios de qualidade

- Priorizar riscos reais sobre estilo.
- Sempre sugerir mudanças implementáveis.
- Não aprovar endpoint de lista sem paginação, salvo exceção explícita de negócio.
