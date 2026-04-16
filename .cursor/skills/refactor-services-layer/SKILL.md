---
name: refactor-services-layer
description: Guia refatoração para camada de services com DTOs e testes, migrando lógica de views.py para serviços coesos e testáveis. Use ao organizar regras de negócio, reduzir views inchadas ou padronizar arquitetura backend.
---

# Refactor Services Layer

## Objetivo

Extrair regra de negócio de `views.py` para `services/`, definir DTOs de entrada/saída e garantir cobertura de testes.

## Padrão alvo

- `views.py`: orquestra request/response, autenticação e serialização HTTP.
- `services/`: concentra regra de negócio e transações.
- DTOs: contrato explícito de entrada/saída entre view e service.
- Repositórios/ORM: acesso a dados encapsulado quando necessário.

## Fluxo de migração

1. **Mapear responsabilidades atuais**
   - Separar lógica HTTP da lógica de negócio.
   - Identificar efeitos colaterais (email, fila, auditoria).

2. **Criar DTOs**
   - Definir DTO de entrada com campos validados.
   - Definir DTO de saída com payload de domínio.

3. **Extrair service**
   - Criar função/método com nome orientado a caso de uso.
   - Mover transações e regras para o service.

4. **Adaptar view**
   - Construir DTO de entrada.
   - Chamar service e converter DTO de saída em resposta HTTP.

5. **Adicionar testes**
   - Testes de service cobrindo regra e bordas.
   - Teste de integração/API validando contrato HTTP.

## Estrutura sugerida

```text
app/
  services/
    create_order.py
  dtos/
    order_dto.py
  views.py
  tests/
    test_create_order_service.py
    test_create_order_api.py
```

## Checklist de revisão

- [ ] View sem regra de negócio complexa.
- [ ] Service sem dependência direta de `HttpRequest`.
- [ ] DTOs claros e estáveis.
- [ ] Erros de domínio mapeados para status code adequado.
- [ ] Testes de regressão adicionados.

## Formato de saída

```markdown
## Plano de refactor
- Caso de uso: <nome>
- Lógica a extrair: <trecho/responsabilidade>
- DTOs: <entrada/saída>

## Mudanças propostas
- Service: <arquivo e assinatura>
- View: <simplificação aplicada>
- Testes: <novos cenários>
```
