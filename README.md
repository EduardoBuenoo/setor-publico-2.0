# SIGDEI — Sistema de Gestão do Departamento de Desenvolvimento Econômico

**Prefeitura Municipal de Iracemápolis/SP** · Projeto Interdisciplinar (PI-IV) — Sistemas de Informação — Fundação Hermínio Ometto (FHO)

Repositório único do projeto **setor-publico-2.0**: interface web, API Django e assistente de IA local (GAFIA) reunidos na mesma base de código.

## Sobre o projeto

O Departamento de Desenvolvimento Econômico da Prefeitura de Iracemápolis não dispunha de ferramentas para centralizar e acompanhar as informações produzidas por seus setores. Este **sistema web** ajuda os gestores a conferir o cumprimento de metas e a analisar a realidade do desenvolvimento municipal, com foco em criação de empresas, geração de vagas de emprego e fortalecimento do empreendedorismo local.

O projeto está alinhado ao **ODS nº 9** (Indústria, Inovação e Infraestrutura) da Agenda 2030 da ONU.

## Setores contemplados

| Setor | Função |
|---|---|
| **SEBRAE-Aqui** | Orientação e capacitação de micro e pequenas empresas/MEIs |
| **PAT** (Posto de Atendimento ao Trabalhador) | Intermediação de mão de obra e cadastro de vagas |
| **Banco do Povo** | Microcrédito a empreendedores locais |
| **PROCON** | Defesa e orientação ao consumidor |

## Funcionalidades

- Autenticação JWT e controle de acesso por perfil (Administrador, Gestor, Secretário, Colaborador), com primeiro acesso, alteração de senha e recuperação por pergunta de segurança.
- Indicadores por setor, lançamentos de atividades e dashboard com gráficos.
- Registro de ofícios com numeração única por ano.
- Projetos e tarefas por setor, com status visual (em andamento, concluído no prazo, atrasado).
- Cadastro de empresas por **CNPJ** (numérico e alfanumérico, com validação dos dígitos verificadores) e registro de atendimentos por setor.
- **Indicadores cruzados IC-01 a IC-04**, calculados a partir dos atendimentos (`backend/sector/cross_indicators.py`).
- **Assistente de IA local** (Ollama + LlamaIndex) com quatro modos: indicadores cruzados, lançamentos do dashboard, análise de indicadores/projetos e consulta a documentos.

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.11/3.12, Django 5.2, Django REST Framework, SimpleJWT, bcrypt, django-cors-headers |
| Frontend | HTML5, CSS3 e JavaScript (sem build) |
| Banco de dados | SQLite para desenvolvimento e testes locais; PostgreSQL previsto para produção |
| IA | Ollama (modelos locais) + LlamaIndex |
| Automação | n8n (protótipo em `fluxo_n8n_chat_dashboard_gafia.json`, sem integração ativa) |

## Estrutura do repositório

```text
setor-publico-2.0/
├── backend/              API Django (apps: users, sector, projects, oficios, ai_docs)
│   ├── app/              configurações e rotas do projeto Django
│   ├── ai_docs/          rotas autenticadas do assistente (dashboard, IC, análise IA, documentos)
│   └── requirements.txt  dependências do backend (inclui ../requirements.txt)
├── frontend/             interface HTML/CSS/JS do SIGDEI
├── docs/                 documentação acadêmica (TAP, EAP, RACI, cronograma, protótipo…)
├── web/                  interface do chat documental independente (gafia_docs.py serve)
├── tests/                testes do chat documental (gafia_docs.py)
├── deploy/n8n/           exemplo de implantação do n8n (compose + Caddy)
├── preview/              prévia estática da tela do assistente
├── documentos/           arquivos extras para o assistente indexar (conteúdo não versionado)
├── gafia_docs.py         indexação e consulta local com LlamaIndex + Ollama
├── requirements.txt      dependências do assistente (LlamaIndex/Ollama)
├── iniciar.bat           inicia backend e frontend no Windows (somente este computador)
├── iniciar_rede.bat      inicia backend e frontend acessíveis na rede local
└── SIGDEI_Postman_Collection.json
```

## Como executar

Pré-requisito: Python 3.11 ou 3.12. Para o assistente de IA, instale também o [Ollama](https://ollama.com).

### 1. Ambiente e dependências

```powershell
# Windows (PowerShell), na raiz do repositório
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

```bash
# Linux/macOS
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
```

### 2. Banco de dados e primeiro usuário

```powershell
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py bootstrap_admin   # pede a senha de forma interativa
```

O banco SQLite (`backend/db_teste.sqlite3`) é gerado localmente e **não** é versionado.

Dados fictícios opcionais para demonstração (todos marcados com `[DEMO]`, sem duplicar ao repetir):

```powershell
.\.venv\Scripts\python.exe backend\manage.py seed_demo
.\.venv\Scripts\python.exe backend\manage.py seed_cross_demo
```

### 3. Subir backend e frontend

No Windows, basta executar `iniciar.bat` (ou `iniciar_rede.bat` para acesso por outros dispositivos da rede). Manualmente, em dois terminais:

```powershell
.\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000
.\.venv\Scripts\python.exe -m http.server 5500 --directory frontend
```

Abra `http://127.0.0.1:5500/index.html`. O frontend usa o mesmo host da página para chamar a API na porta 8000.

### 4. Assistente de IA (opcional)

```powershell
ollama pull llama3.2:3b
ollama pull nomic-embed-text
ollama pull qwen2.5:1.5b
.\.venv\Scripts\python.exe gafia_docs.py index    # indexa docs/, README.md e documentos/
```

O índice (`.local_index/`) é gerado localmente; rode `index` de novo quando os documentos mudarem. O modo de documentos exige o índice; os demais modos não. Detalhes em [PROJETO_CHAT_LOCAL.md](PROJETO_CHAT_LOCAL.md).

## Configuração por variáveis de ambiente

| Variável | Padrão | Uso |
|---|---|---|
| `DJANGO_SECRET_KEY` | chave de desenvolvimento | **Obrigatória** quando `DJANGO_DEBUG=0` |
| `DJANGO_DEBUG` | `1` | `0` desativa o modo de depuração |
| `DJANGO_ALLOWED_HOSTS` | `*` (debug) / `127.0.0.1,localhost` | hosts aceitos, separados por vírgula |
| `DJANGO_CORS_ALLOWED_ORIGINS` | `http://127.0.0.1:5500,http://localhost:5500` | origens permitidas do frontend |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | endereço do Ollama |
| `GAFIA_CHAT_MODEL` | `llama3.2:3b` | modelo de chat |
| `GAFIA_EMBED_MODEL` | `nomic-embed-text` | modelo de embeddings |
| `GAFIA_INSIGHTS_MODEL` | `qwen2.5:1.5b` | modelo da análise de indicadores e projetos |
| `GAFIA_RAG_MODEL` | `qwen2.5:1.5b` | modelo do assistente unificado |
| `GAFIA_CHAT_TOKEN` | — | token do chat independente (`gafia_docs.py serve`) |

Nunca versione segredos: `.env` está no `.gitignore`.

## API (prefixo `/api/v1/`)

| Área | Rotas |
|---|---|
| Autenticação e usuários | `login/`, `usuarios/`, `usuarios/<id>/`, `usuarios/primeiro-acesso/`, `usuarios/alterar-senha/`, `recuperar-senha/pergunta/`, `recuperar-senha/verificar/`, `recuperar-senha/redefinir/` |
| Setores e indicadores | `setores/`, `setores/<id>/`, `indicadores/`, `atividades/`, `atividades/<id>/` |
| Empresas e atendimentos | `empresas/`, `atendimentos/` |
| Ofícios | `oficios/`, `oficios/<id>/` |
| Projetos e tarefas | `projetos/`, `projetos/<id>/`, `tarefas/`, `tarefas/<id>/` |
| Assistente | `assistente/status/`, `assistente/perguntar/`, `dashboard/perguntar/`, `dashboard/cruzados/`, `dashboard/cruzados/perguntar/`, `analise-ia/status/`, `analise-ia/perguntar/`, `documentos/status/`, `documentos/perguntar/` |

A coleção [SIGDEI_Postman_Collection.json](SIGDEI_Postman_Collection.json) cobre as rotas originais do sistema.

### Permissões do assistente

- **Indicadores cruzados:** Administrador, Gestor ou Secretário **e** `visao_estrategica=true`, concedida individualmente pelo Administrador na tela de Usuários.
- **Dashboard, análise IA e documentos:** Administrador ou Gestor.
- O Django calcula os ICs oficiais antes de responder e **nunca envia CNPJ ao modelo**.

## Testes

```powershell
# Backend (Django)
cd backend
..\.venv\Scripts\python.exe manage.py test

# Chat documental (gafia_docs.py) — na raiz
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

A integração contínua (`.github/workflows/django.yml`) executa verificação de migrações e ambos os conjuntos de testes em Python 3.11 e 3.12.

## Equipe

| Nome | Papel |
|---|---|
| Giovana Jacobucci | Engenheira de IA e Dados |
| Kael Vicente Dipres | Scrum Master |
| Kaio Bueno de Camargo | Desenvolvedor Back-end (IA) / QA |
| Sofia Camargo Nunes | Product Owner e Arquiteta de Software |
| Virna Karina do Amaral | Desenvolvedora Front-end |

## Documentação

Proposta, EAP, RACI, cronograma, TAP e demais artefatos estão em [`docs/`](./docs). A apresentação do projeto (arquitetura, metodologia e endpoints originais) está em [docs/README_apresentacao.md](docs/README_apresentacao.md). O fluxo n8n de referência está em [README_fluxo_n8n.md](README_fluxo_n8n.md).

## Licença

Projeto acadêmico desenvolvido para a disciplina de Projeto Interdisciplinar IV. Uso restrito a fins educacionais, salvo autorização em contrário.
