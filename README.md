# SIGDEI

Sistema de Gestão do Departamento de Desenvolvimento Econômico de Iracemápolis/SP. Reúne medições do SEBRAE-Aqui, PAT, Banco do Povo e PROCON para o acompanhamento de metas, atendimentos, crédito e vagas captadas.

## Executar com Docker

O ambiente precisa de Git, Docker Engine ou Docker Desktop e Docker Compose v2. A partir da raiz desta árvore de trabalho, execute os comandos para o seu sistema.

**Linux**

```sh
cp .env.example .env
docker compose up --build -d --wait
docker compose exec backend python manage.py bootstrap_admin
```

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
docker compose up --build -d --wait
docker compose exec backend python manage.py bootstrap_admin
```

Abra o sistema em [http://localhost:8080](http://localhost:8080). O primeiro acesso solicita a troca de senha e a configuração da recuperação. Para habilitar a visão geral dos cruzamentos, conceda **Visão estratégica** ao perfil correspondente na tela **Usuários**. A API está em `/api/v1/` e o estado da aplicação e da conexão com o banco em [http://localhost:8080/health/](http://localhost:8080/health/).

O PostgreSQL 16 roda na rede interna do Compose. Os serviços sobem na ordem banco → migrações e aplicação → frontend. O volume `postgres_data` mantém o banco após `docker compose down`. `docker compose down -v` remove os volumes. Em desenvolvimento, o Nginx é publicado apenas em loopback. Para implantação fora do computador de desenvolvimento, configure segredo Django próprio e longo, senha do banco, hosts e origens permitidos, HTTPS e `DJANGO_DEBUG=0`.

### Execução local sem Docker

Use Python 3.11 ou 3.12. Os scripts instalam dependências, executam as migrações e verificam o catálogo de setores. Prepare o administrador em um segundo terminal após a inicialização.

| Sistema | Iniciar na raiz do projeto | Criar o primeiro administrador |
|---|---|---|
| Linux | `sh scripts/iniciar-local.sh` | `.venv/bin/python backend/manage.py bootstrap_admin` |
| Windows PowerShell | `.\scripts\iniciar.bat` | `.\.venv\Scripts\python.exe backend\manage.py bootstrap_admin` |

Abra [http://127.0.0.1:5500](http://127.0.0.1:5500). A API local usa a porta `8000` e a origem do frontend usa a porta `5500`. Sem `POSTGRES_HOST`, o backend usa SQLite em `backend/db_teste.sqlite3`. Para usar um PostgreSQL já instalado, crie o banco e o usuário, preencha `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` e `POSTGRES_PASSWORD` em `.env` e inicie o backend normalmente. `SIGDEI_SQLITE_PATH` permite apontar para uma cópia local do SQLite.

### Configuração de ambiente

| Variável | Finalidade |
|---|---|
| `DJANGO_DEBUG` | Use `1` para desenvolvimento e `0` em produção |
| `DJANGO_SECRET_KEY` | Segredo obrigatório com pelo menos 50 caracteres quando `DJANGO_DEBUG=0` |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ALLOWED_ORIGINS` | Hosts e origens autorizados, separados por vírgula |
| `POSTGRES_*` | Configuração do PostgreSQL. No Compose, o host é `db` |
| `SIGDEI_BIND`, `SIGDEI_PORT` | Endereço de publicação e porta web no Compose |
| `SIGDEI_AI_*` | Provedor opcional, URL, modelo e chave de API |
| `SIGDEI_SHOW_DEMO_DATA` | Use `1` com debug em um banco isolado para consultar registros marcados como demonstração |

O projeto inicia sem medições ou empresas. Em um banco exclusivo para demonstração, habilite `SIGDEI_SHOW_DEMO_DATA=1` e execute os comandos de gerenciamento `seed_demo` e `seed_cross_demo`, após criar o administrador. Registros marcados como demonstração ficam fora das consultas oficiais por padrão.

## Arquitetura

A aplicação mantém Python e Django 5.2, Django REST Framework, JWT, HTML, CSS e JavaScript. O frontend consome a API sob a mesma origem no Compose. Consultas e agregações usam o ORM com PostgreSQL ou SQLite. Gráficos usam Chart.js 4.5.1, distribuído com a respectiva licença MIT.

```text
backend/
  app/               Configuração, rotas e saúde do banco
  sector/            Catálogo, medições, empresas, atendimentos e agregações
  users/             Autenticação, usuários e permissões estratégicas
  ai_docs/           Assistente estruturado, consulta documental opcional e testes
  projects/, oficios/    Migrações históricas para arquivamento
frontend/
  assets/css/        Estilos do SIGDEI
  assets/js/         Cliente da API e lógica das telas
  assets/vendor/     Biblioteca de gráficos e licença
  *.html             Telas web
docs/                Documentação técnica e materiais acadêmicos
documentos/          Documentos locais opcionais para indexação
scripts/             Inicialização em Docker, Windows e Linux
compose.yaml         Orquestração dos serviços
```

### Indicadores e permissões

O catálogo identifica o setor, o tipo, a unidade, a fonte, a situação, a periodicidade e a meta facultativa, mínima ou máxima. Uma medição exige valor numérico não negativo e data de referência. Porcentagens aceitam valores de 0 a 100 com unidade `%`. Tempos aceitam segundos, minutos, horas ou dias. Quantidades podem ter unidades como atendimentos ou reais.

As frequências diária, mensal, trimestral e anual admitem uma medição por indicador e referência. Para frequências superiores à diária, a API usa o primeiro dia do período civil. O painel soma quantidades e calcula a média simples de tempos e porcentagens. Quando faltam medições, o resultado aparece como **Sem dados**. O número zero registrado é exibido como zero. O histórico registra criações, edições e exclusões com data, autor e valores anteriores e posteriores. Um indicador inativo preserva o histórico e fica fechado para novas medições.

- Administradores gerenciam o catálogo inteiro, os setores e os usuários.
- Gestores gerenciam definições e medições do próprio setor.
- Colaboradores registram e editam medições no próprio setor. Secretários consultam os registros autorizados.
- A visão estratégica é concedida individualmente a administradores, gestores ou secretários e dá acesso aos cruzamentos do departamento.
- O assistente estruturado atende administradores e gestores. Secretários também podem usá-lo quando têm visão estratégica. Consultas individuais seguem o escopo de setor.

| Finalidade | Rotas sob `/api/v1/` |
|---|---|
| Sessão e usuários | `login/`, `usuarios/`, `usuarios/<id>/`, `usuarios/primeiro-acesso/`, `usuarios/alterar-senha/`, `recuperar-senha/{pergunta,verificar,redefinir}/` |
| Setores e catálogo | `setores/`, `indicadores/`, `indicadores/<id>/`, `indicadores/<id>/historico/` |
| Medições e painel | `atividades/`, `atividades/<id>/`, `dashboard/` |
| Registro de eventos | `empresas/?cnpj=...`, `atendimentos/` |
| Consulta estratégica | `dashboard/cruzados/`, `dashboard/cruzados/perguntar/` |
| Assistente | `assistente/status/`, `assistente/perguntar/`, `documentos/status/`, `documentos/perguntar/` |

Use `Authorization: Bearer <access>`. O painel aceita `setor`, `indicador`, `tipo`, `inicio` e `fim`. Datas usam `AAAA-MM-DD`. As rotas de medições e histórico retornam páginas com `results` e `next`. A API aceita `periodo_referencia` e mantém `data_cadastro` como alias para clientes anteriores.

### Indicadores cruzados

Cada vínculo usa a mesma empresa cadastrada pelo CNPJ normalizado e validado, numérico ou alfanumérico. O banco conta CNPJs distintos em cada grupo. Todos os eventos da comparação devem ocorrer no período selecionado, segundo a data pertinente de orientação, atendimento, liberação ou abertura. Para ordenação, o segundo evento precisa ter data posterior ao primeiro. A resolução diária não estabelece ordem entre dois eventos do mesmo dia.

| Código | Resultado e fórmula | Fonte |
|---|---|---|
| IC-01 | Empresas orientadas com crédito posterior ÷ empresas orientadas × 100 | Orientação SEBRAE, liberação Banco do Povo |
| IC-02 | Vagas abertas após o crédito da mesma empresa ÷ (valor de todo crédito liberado ÷ R$ 100 mil) | Liberação Banco do Povo, abertura de vagas PAT |
| IC-03 | Empresas com orientação, liberação e abertura de vaga em ordem de datas | SEBRAE, Banco do Povo e PAT |
| IC-04 | Empresas atendidas em dois ou mais setores de fomento ÷ empresas atendidas nos setores de fomento × 100 | SEBRAE, Banco do Povo e PAT |
| IC-05 | Empresas com crédito seguido da abertura de vaga | Banco do Povo e PAT |
| IC-06 | Empresas com atendimento em dois ou mais setores | SEBRAE, Banco do Povo, PAT e PROCON |
| IC-07 | Empresas com atendimento em três ou mais setores | SEBRAE, Banco do Povo, PAT e PROCON |
| IC-08 | Empresas orientadas com liberação de crédito posterior | SEBRAE e Banco do Povo |

Para os cruzamentos que exigem duas ou três bases, a ausência de eventos de uma etapa produz **Sem dados**. Se as bases têm eventos e nenhuma empresa satisfaz a sequência, o resultado é zero. O painel traz evolução por mês e até 30 empresas multissetoriais, ordenadas pelo número de atendimentos registrados. Vagas captadas medem oportunidades registradas no PAT. Empregos efetivados exigiriam uma fonte de preenchimento de vagas ou admissões. A sequência indica associação cronológica.

### Assistente e documentos

O modo padrão, `SIGDEI_AI_PROVIDER=deterministico`, interpreta perguntas usuais sobre atendimentos, crédito, vagas, evolução, semestres, crescimento e os códigos IC. As consultas operam sobre filtros e agregações previamente implementados, com permissões aplicadas antes da leitura. A resposta cita a fonte e o período. A comparação de crescimento usa volumes de atendimentos em duas janelas de mesma duração com registros disponíveis.

Para perguntas fora do vocabulário reconhecido, um provedor opcional pode selecionar uma intenção na lista permitida. O sistema envia o texto digitado, com mascaramento básico de e-mails e sequências numéricas, e mantém os registros consultados e o resultado calculado dentro do SIGDEI. Digite perguntas sem informação pessoal ou sigilosa ao habilitar um provedor externo.

| Modalidade | Configuração |
|---|---|
| Ollama local | Instale o Ollama, execute `ollama pull qwen2.5:1.5b` e defina `SIGDEI_AI_PROVIDER=ollama`. Configure `SIGDEI_AI_URL` para o endereço alcançável pelo backend e `SIGDEI_AI_MODEL` se usar outro modelo |
| OpenAI ou compatível | Defina `SIGDEI_AI_PROVIDER=openai`, `SIGDEI_AI_API_KEY` e opcionalmente `SIGDEI_AI_MODEL`. `SIGDEI_AI_URL` deve apontar para a base compatível com `/v1` e `/chat/completions` |
| Documentos com LlamaIndex | Instale `backend/requirements-documentos.txt`, configure `OLLAMA_URL`, execute `ollama pull llama3.2:3b` e `ollama pull nomic-embed-text`. Gere o índice com `python backend/manage.py indexar_documentos`. No Compose, use `SIGDEI_DOCUMENTOS=1` no build e `docker compose exec backend python manage.py indexar_documentos` |

No Compose, `host.docker.internal` referencia o host quando o serviço estiver acessível a partir do contêiner. Localmente, o índice lê `docs/`, `README.md` e `documentos/`. Para documentos particulares no Compose, acrescente um bind mount somente leitura em `/app/documentos`, com acesso de leitura pelo usuário do backend. O volume do índice é independente do banco. Após alterações de arquivos ou modelos, reconstrua o índice. A consulta documental usa a área **Fonte → Documentos locais** para administradores e gestores.

## Atualizar uma instalação existente

Faça uma cópia verificável do SQLite com o aplicativo parado ou um backup PostgreSQL com `pg_dump`. Execute as migrações primeiro sobre uma cópia. As migrações de catálogo normalizam os rótulos conhecidos de tipo, preservam IDs e valores, e sinalizam registros anteriores para manter históricos e duplicidades legadas. Os registros dos módulos descontinuados passam a `arquivo_projetos`, `arquivo_tarefas` e `arquivo_oficios`. Os vínculos internos do arquivo são mantidos, e suas referências a usuários e setores ficam como IDs históricos. Para restauração operacional, use o backup anterior em uma instalação da versão correspondente. Mudar o motor de SQLite para PostgreSQL exige uma transferência de dados separada.

Uma instalação atualizada no mesmo banco mantém usuários, empresas, atendimentos, setores e medições. Use `bootstrap_setores` para verificar os códigos oficiais. Quando dois setores legados representam o mesmo órgão, revise seus vínculos antes de atribuir o código oficial. O antigo arquivo de exportação versionado tinha estrutura de uma versão anterior e conteúdo de autenticação. Trate sua recuperação como backup administrativo restrito.

## Testes e diagnóstico

```sh
cd backend
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --noinput
```

Para executar a mesma suíte no PostgreSQL do Compose, rode `docker compose exec backend python manage.py test --noinput`. O Django cria um banco de testes separado. Para incluir o teste do índice documental, instale as dependências opcionais. A CI executa SQLite e PostgreSQL.

| Sintoma | Verificação |
|---|---|
| O site não abre | Consulte `docker compose ps` e `docker compose logs backend db frontend`. Verifique se a porta está livre |
| O build apresenta erro TLS no PyPI | Em rede com CA própria, forneça o certificado confiável ao BuildKit como segredo `pip_cert` no build do backend |
| Django recusa o host | Ajuste `DJANGO_ALLOWED_HOSTS` em `.env` e recrie o serviço |
| A API local é bloqueada pelo navegador | Use a porta 5500 para o frontend e confira `DJANGO_CORS_ALLOWED_ORIGINS` |
| Cruzamentos retornam 403 | Verifique se o usuário tem perfil compatível e recebeu Visão estratégica |
| Uma relação consta como Sem dados | Revise o período, os tipos e datas dos eventos e a vinculação ao CNPJ |
| O índice está ausente ou desatualizado | Confira os modelos do Ollama e execute `indexar_documentos` novamente |

Os materiais acadêmicos originais estão em [docs/](docs/). Projeto interdisciplinar desenvolvido na Fundação Hermínio Ometto (FHO), com uso restrito a fins educacionais salvo autorização em contrário.
