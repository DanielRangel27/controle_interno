# Controle Interno de Processos — PGM

Sistema Django para controle interno de processos administrativos da
Procuradoria do Município, com dois módulos independentes:

- **Procuradoria Fazendária** (PROCSEFOP)
- **Procuradoria Geral**

Funciona offline em uma máquina servidora da rede interna, com backup
automático para um repositório Git privado.

### Recursos principais

- Cadastro, edição e detalhamento de processos por módulo, com situação,
  pareceres, procuradores, destinos e observações.
- Listagens com filtros por busca, ano, situação, procurador, destino,
  assunto, tipo de parecer e **range de datas** (recebimento ou
  distribuição).
- **Exportação CSV/XLSX** com os filtros aplicados (botões na listagem
  e na página de relatório).
- **Dashboard inicial** com cards por módulo, contadores por situação e
  últimos processos cadastrados.
- **Página de relatório por módulo** (`/painel/relatorios/...`) com
  KPIs, distribuição mensal dos últimos 12 meses (gráfico de barras) e
  top 5 procuradores, assuntos, destinos e tipos de parecer.
- **Busca global** no cabeçalho: encontra processos pelo número (ou
  observação/apenso) nos dois módulos.
- Tema claro/escuro/automático com persistência por cookie.

---

## Stack

- Python 3.13 + Django 6
- SQLite (banco local; cópia espelhada no Git como backup)
- Bootstrap-like CSS próprio com tokens (tema claro/escuro automático ou manual)
- Waitress para servir em produção no Windows

---

## Instalação inicial (na máquina servidora)

1. Clone o projeto e entre na pasta:

   ```powershell
   git clone <URL-do-projeto> controle_interno
   cd controle_interno
   ```

2. Crie um virtualenv (recomendado) e instale as dependências:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. Copie o `.env.example` para `.env` e edite os valores:

   ```powershell
   copy .env.example .env
   notepad .env
   ```

   Itens importantes para produção:
   - `DJANGO_SECRET_KEY=<chave-aleatoria>` (gere uma com
     `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
   - `DJANGO_DEBUG=false`
   - `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,<IP-da-maquina-na-rede>`
   - `DJANGO_CSRF_TRUSTED_ORIGINS=http://<IP-da-maquina>:8088`

4. Aplique as migrations e crie o superusuário inicial:

   ```powershell
   python manage.py migrate
   python manage.py createsuperuser
   ```

5. (Opcional) Importe a aba do ano corrente das planilhas legadas:

   ```powershell
   python manage.py importar_planilhas `
       --fazendaria "CONTROLE DE PA - PROCSEFOP 2021-22 (Recuperado) - Copia.xlsx" `
       --geral "001 - Controle Interno de Processos copia.xlsm"
   ```

   Use `--dry-run` para pré-visualizar sem gravar.

---

## Servir o sistema na rede interna

### Para uso diário

```powershell
.\scripts\runserver.bat
```

Esse script roda o `waitress` em `0.0.0.0:8088`. Os outros usuários da rede
acessam em `http://NOME-DA-MAQUINA:8088/` ou `http://IP-DA-MAQUINA:8088/`.

### Modo desenvolvimento

```powershell
python manage.py runserver 127.0.0.1:8088
```

Atenção: no Windows, a porta `8000` costuma estar reservada — use `8088`.

---

## Cadastros e autenticação

- O **superusuário** (criado pelo `createsuperuser`) acessa `/admin/` para:
  - cadastrar usuários (procuradores/secretárias que vão entrar no sistema);
  - cadastrar **Procuradores**, **Setores** (destinos), **Assuntos** e
    **Tipos de parecer**.
- Os tipos de parecer são pré-criados automaticamente na primeira importação
  com os códigos da planilha (`D`, `P`, `Pd`, `Pi`, `R`).
- Cada Procurador/Assunto pertence a um módulo (`fazendaria`, `geral` ou
  `ambos`); só aparece no formulário do módulo correspondente.

Para criar um usuário comum manualmente:

```powershell
python manage.py createsuperuser
# ou
python manage.py shell -c "from django.contrib.auth.models import User; User.objects.create_user('nome', password='troque')"
```

---

## Backup automático para o GitHub

O comando `backup_git`:

1. Clona (1ª vez) ou puxa atualizações do repositório configurado.
2. Gera um dump JSON do banco.
3. Copia o arquivo `db.sqlite3` para o repo de backup.
4. Faz commit + push se houver mudanças (não cria commit vazio).

### Pré-requisitos

- O Git deve estar instalado e disponível no `PATH` (`git --version`).
- Configure as credenciais do repositório uma única vez:

  ```powershell
  git config --global credential.helper manager
  ```

  Na primeira execução, o Windows abrirá uma tela pedindo o **Personal Access
  Token (PAT)** do GitHub. Gere o token em
  https://github.com/settings/tokens com permissão `repo` para o repositório
  privado e cole quando solicitado. As credenciais ficam armazenadas no
  Credential Manager.

- O repositório de destino é configurado em `.env` via `BACKUP_GIT_REMOTE`
  (padrão: `https://github.com/DanielRangel27/backups.git`).

### Rodar manualmente

```powershell
python manage.py backup_git           # commit + push
python manage.py backup_git --no-push  # commit local apenas
```

### Agendar (Windows)

1. Edite `scripts\backup.bat` e ajuste `PROJECT_DIR` para o caminho real do
   projeto.
2. Abra o **Agendador de Tarefas** do Windows → **Criar Tarefa Básica**.
3. Configure:
   - **Nome**: "Backup Controle Interno PGM"
   - **Disparador**: "Diariamente, às 18:00" (ou frequência desejada)
   - **Ação**: "Iniciar um programa"
     - Programa: `C:\Users\pgm-a\controle_interno\scripts\backup.bat`
     - Iniciar em: `C:\Users\pgm-a\controle_interno`
4. Em "Configurações", marque "Executar com privilégios mais altos" e "Iniciar
   a tarefa apenas se o computador estiver conectado à rede".

Os logs do `.bat` aparecem no histórico da tarefa do Agendador.

---

## Estrutura do projeto

```
controle_interno/
├── controle_interno/   # settings + urls raiz
├── core/               # cadastros (Procurador, Setor, Assunto, TipoParecer),
│                       # autenticação, base template, importadores e backup
├── fazendaria/         # módulo Fazendária (modelo + CBVs + templates próprios)
├── geral/              # módulo Geral (idem)
├── scripts/
│   ├── backup.bat      # script para Agendador de Tarefas
│   └── runserver.bat   # script para servir via waitress
├── requirements.txt
├── .env.example
└── manage.py
```

---

## Testes

```powershell
python manage.py test
```

A suíte cobre:

- todos os parsers de importação das planilhas (variações reais de 2026);
- services e forms de cada módulo (filtros, validações, permissões por módulo);
- comando `backup_git` (clone, dump, commit, push, idempotência);
- exportação CSV/XLSX (cabeçalhos, anexos, formato XLSX abrindo no openpyxl);
- relatórios por módulo (KPIs, distribuição mensal, top procuradores/assuntos);
- busca global cross-módulo.

Total: **80 testes**.

---

## Solução de problemas

**"You don't have permission to access that port" ao usar 8000**
A porta 8000 é reservada em algumas instalações do Windows. Use `8088` (já
configurada nos scripts).

**Backup falha com `could not read Username for 'https://github.com'`**
Configure o credential manager (ver seção "Pré-requisitos" acima) e rode
`git ls-remote https://github.com/DanielRangel27/backups.git` uma vez para
salvar o PAT.

**Tema escuro não persiste**
O tema é salvo em cookie. Se o navegador rejeita cookies do site, a escolha
volta para "auto" a cada acesso.

**Como redefinir senha de um usuário**
```powershell
python manage.py changepassword <username>
```

---

## Atalhos no app

| O que | Onde |
| --- | --- |
| Dashboard inicial com últimos cadastros | `/painel/` |
| Relatório Fazendária (KPIs + barras) | `/painel/relatorios/fazendaria/` |
| Relatório Geral (KPIs + barras) | `/painel/relatorios/geral/` |
| Busca global por número de processo | barra no topo (ou `/painel/buscar/?q=...`) |
| Listagem Fazendária com filtros | `/fazendaria/` |
| Listagem Geral com filtros | `/geral/` |
| Exportar listagem filtrada (CSV) | botão "CSV" no topo de cada lista |
| Exportar listagem filtrada (XLSX) | botão "XLSX" no topo de cada lista |
| Cadastros mestres (admin) | `/admin/` (apenas staff) |
