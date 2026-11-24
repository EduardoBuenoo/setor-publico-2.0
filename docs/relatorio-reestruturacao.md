# Relatório de reestruturação do SIGDEI

Execução em 23 de novembro de 2026, a partir do checkout oficial no commit `3b99a498cf2e6814dc2a8a8f0c698264151c6056`. O histórico Git foi preservado. A entrega foi preparada na branch `codex/sigdei-reestruturado`.

## 1. Diagnóstico inicial

- O projeto já usava Django 5.2 e Django REST Framework, login próprio com SimpleJWT e bcrypt, SQLite e frontend HTML/CSS/JavaScript. PostgreSQL aparecia na documentação, mas a configuração da aplicação usava SQLite fixo.
- O catálogo só registrava nome, setor e tipo. Faltavam campos de governança, edição de definições, uma referência de negócio para distinguir medições e trilha de alterações. A API aplicava somas por indicador dentro da serialização. A aplicação também somava percentuais e permitia que lançamentos apontassem para indicadores fora do setor autorizado.
- O dashboard antigo baixava conjuntos inteiros de registros e dependia da lista de usuários para renderizar. O frontend construía a URL HTTP da API por página. A navegação também podia abrir caminhos de iframe vindos da URL sem conferir se pertenciam ao menu.
- Empresas e atendimentos já estavam modelados por CNPJ. Os quatro indicadores cruzados iniciais materializavam eventos e calculavam boa parte dos resultados em Python. A jornada final usava qualquer atendimento PAT, e a publicação misturava datas de atendimento e de captação de vagas. Faltavam índices específicos para as consultas.
- O assistente tinha rotas com contratos e contextos sobrepostos, análise de projetos e consulta documental redundante com um servidor HTTP independente. Perguntas individuais podiam depender do Ollama mesmo quando o cálculo era viável com dados estruturados.
- Projetos, tarefas e ofícios dependiam de usuários e setores, enquanto o núcleo de indicadores, empresas e atendimentos não dependia deles. A remoção exigia retirar os vínculos operacionais antes de liberar as tabelas para arquivo.
- Havia protótipos, instruções e uma coleção de API da versão anterior. Um export antigo incluía dados de autenticação e um modelo de indicadores descontinuado. A revisão retirou esse arquivo da árvore ativa e manteve o histórico do repositório.

## 2. Estrutura antiga e nova

| Área | Estrutura inicial | Estrutura atual |
|---|---|---|
| Núcleo | `backend/app`, `users`, `sector` e páginas com JavaScript embutido | Mesmos apps Django com serviços do domínio em `sector/reporting.py` e `sector/cross_indicators.py`. A interface usa `frontend/assets/js` e `assets/css` |
| Módulos retirados | Apps ativos `backend/projects`, `backend/oficios` e páginas correspondentes | Apps com migrações históricas e tabelas `arquivo_*`. Rotas e páginas removidas |
| IA | `backend/ai_docs`, `gafia_docs.py`, `web`, `preview` e testes independentes | Assistente, integração opcional documental, comando de indexação e testes em `backend/ai_docs` |
| Execução | Scripts Windows na raiz e exemplo separado de n8n | `compose.yaml`, Dockerfiles do backend e frontend, `.env.example` e scripts em `scripts` |
| Banco | SQLite configurado diretamente | PostgreSQL 16 no Compose e SQLite ou PostgreSQL na execução local. Migrações e integridade no Django |
| Documentação | README distribuído entre protótipos e materiais acadêmicos | README técnico atualizado, relatório e documentos acadêmicos históricos em `docs` |

## 3–5. Inventário de arquivos

Os caminhos registram a diferença entre o checkout original e a entrega. Movimentações aparecem como remoção do caminho original e criação no destino. A lista integral está ao final.

## 6. Funcionalidades implementadas

- Cadastro de indicadores por setor, com descrição, tipo, unidade, fonte, periodicidade, estado, meta e critério mínimo ou máximo.
- Criação, correção e exclusão autorizada de medições, com data de referência normalizada, validação numérica, unicidade e histórico transacional de alterações.
- Painel com filtros de setor, indicador, tipo e intervalo de datas, metas, série mensal, empresas atendidas e vagas captadas. A API usa somas para quantidades e médias simples para tempos e percentuais.
- Fluxo de busca e cadastro de empresas com CNPJ formatado ou sem máscara, tipos de atendimento condicionados ao setor e leituras filtradas pelo perfil.
- Consulta estratégica com oito cruzamentos, metodologia, série mensal e lista de empresas multissetoriais. A classificação por setor respeita o código oficial e os vínculos registrados.
- Execução por Docker com PostgreSQL e encaminhamento da API pelo Nginx. Inicialização local em Linux ou Windows, verificações de saúde, criação de administrador e dados de demonstração opcionais e isolados.
- Permissões por perfil e setor, autor de alterações, bloqueio de operações destrutivas que afetariam vínculos preservados, limitação de requisições e trilha operacional de intenções do assistente.

## 7. Funcionamento dos cruzamentos

O serviço relaciona eventos pela entidade `Empresa`, que exige CNPJ canônico e único. Os cálculos usam agregações agrupadas por empresa, contagem distinta e subconsultas de existência para ordenar eventos. Usa-se a data do atendimento para o alcance por setor, a data de liberação para crédito e a data de abertura para vagas. A mesma empresa é contada uma vez em cada cruzamento. Quando faltam eventos necessários, o resultado é indisponível. Se os eventos existem e nenhuma empresa satisfaz a relação, o resultado é zero.

O IC-01 calcula a proporção de orientadas com crédito posterior. O IC-02 calcula vagas posteriores a crédito por R$ 100 mil liberados. O IC-03 identifica orientação, liberação e abertura de vaga nessa ordem. O IC-04 mede o alcance de dois ou mais setores de fomento. O IC-05 conta empresas com crédito e vaga posterior. IC-06 e IC-07 contam vínculos com dois e três setores, respectivamente. IC-08 conta empresas orientadas com crédito posterior. As fórmulas completas e os campos de origem estão no README e na tela de cruzamentos.

As tabelas arquivadas preservam os dados e os vínculos internos dos módulos retirados. As referências a usuários e setores foram mantidas como IDs históricos, sem impor dependências operacionais sobre os cadastros ativos. A migração legada foi exercitada em SQLite e PostgreSQL com uma base preenchida criada para o teste.

## 8. Integração do assistente

A aplicação responde perguntas usuais por consultas parametrizadas do ORM. As intenções determinísticas têm prioridade. O backend aplica a autorização, calcula os resultados e monta a resposta com período e fonte. Para consultas fora das regras reconhecidas, o Ollama ou uma API compatível com OpenAI podem classificar o texto em uma das intenções cadastradas. O classificador recebe somente a pergunta do operador com mascaramento básico e não administra credenciais de banco, consultas SQL ou resultados. A busca documental com LlamaIndex e Ollama é opcional e tem rota e configuração próprias.

## 9. Executar

Na raiz do checkout, copie `.env.example` para `.env`. Execute `docker compose up --build -d --wait` e `docker compose exec backend python manage.py bootstrap_admin`. Abra `http://localhost:8080`.

No Linux, o modo local usa `sh scripts/iniciar-local.sh`. No Windows, use `.\scripts\iniciar.bat` em PowerShell. O frontend local abre em `http://127.0.0.1:5500`. O README detalha credenciais, ambiente, migrações, o catálogo de setores e as modalidades de IA.

## 10. Testes e resultados

| Verificação | Resultado observado |
|---|---|
| SQLite e dependências documentais instaladas | 23 testes passaram. Inclui criação, edição, regras de valores, permissões, CNPJ e migração de base preenchida. O teste documental indexou um arquivo temporário com embeddings simulados |
| PostgreSQL 16.16 do Compose | 22 testes passaram e o teste documental foi pulado por dependência opcional ausente na imagem padrão. A migração de uma base preenchida e a conexão com o banco passaram |
| Docker no Linux | As três verificações de saúde passaram. O build nessa máquina exigiu a CA do ambiente adicionada como segredo BuildKit para acesso ao PyPI |
| Chromium em desktop e largura de 390 px | Primeiro login, troca inicial de senha, concessão pela tela de Usuários, catálogo, edição, medição, histórico, filtros, meta, gráfico, CNPJ com máscara, jornada em três setores e assistente sem chave passaram |
| Inicialização local em Linux | Script iniciou frontend e API com SQLite. As páginas, o arquivo de gráficos e o endpoint de saúde responderam HTTP 200. A origem do frontend foi aceita pelo CORS |
| Verificações estáticas | Django `check`, ausência de migrações pendentes e validação de sintaxe JS e shell passaram |
| Provedores opcionais | Testes de contrato simularam respostas Ollama e OpenAI. O ambiente não tinha modelo Ollama disponível nem credencial externa para chamadas reais |

Os dados usados nos testes foram criados em bancos isolados. A instalação padrão inicia sem dados de demonstração ativos.

## 11. Pendências de validação

- Execução do script Windows e Docker Desktop em Windows precisa de uma máquina com Windows.
- O teste com um servidor Ollama real e com a API externa depende de modelo e chave configurados.
- A migração do banco da Prefeitura e a aferição de latência com o volume de produção dependem de uma cópia autorizada dos dados operacionais. A base preenchida usada aqui foi de teste.
- Registros legados com tipos desconhecidos, setores duplicados ou cadastros incompletos exigem revisão de negócio. Vagas publicadas e emprego efetivado são eventos distintos. O esquema atual registra a captação de vagas.

## 12. Melhorias recomendadas para uma próxima versão

- Medir o desempenho de consultas com `EXPLAIN ANALYZE` em uma cópia representativa e calibrar índices, paginação ou cache com base nos resultados.
- Registrar vagas preenchidas e admissões com identificação de origem e datas próprias para avaliar resultados de emprego.
- Acrescentar regras de qualidade para medir a cobertura de CNPJ por fonte e reconciliar duplicidades legadas com os setores responsáveis.
- Validar classificação de perguntas com exemplos dos gestores e estabelecer monitoramento compartilhado para uma implantação com múltiplas instâncias.

## Inventário integral

### Criados (35)

- `.dockerignore`
- `.env.example`
- `.venv`
- `backend/Dockerfile`
- `backend/ai_docs/assistant.py`
- `backend/ai_docs/documents.py`
- `backend/ai_docs/management/__init__.py`
- `backend/ai_docs/management/commands/__init__.py`
- `backend/ai_docs/management/commands/indexar_documentos.py`
- `backend/ai_docs/test_documents.py`
- `backend/app/health.py`
- `backend/oficios/migrations/0003_arquivar.py`
- `backend/projects/migrations/0003_arquivar.py`
- `backend/requirements-documentos.txt`
- `backend/sector/management/commands/bootstrap_setores.py`
- `backend/sector/migrations/0005_catalogo_historico.py`
- `backend/sector/migrations/0006_preservar_legado.py`
- `backend/sector/migrations/0007_restricoes_medicoes.py`
- `backend/sector/migrations/0008_criterio_meta.py`
- `backend/sector/reporting.py`
- `backend/sector/tests.py`
- `backend/users/migrations/0004_alter_users_id_setor.py`
- `compose.yaml`
- `docs/relatorio-reestruturacao.md`
- `frontend/Dockerfile`
- `frontend/assets/css/gestao.css`
- `frontend/assets/js/api.js`
- `frontend/assets/js/dashboard.js`
- `frontend/assets/js/indicadores.js`
- `frontend/assets/vendor/chartjs/LICENSE.md`
- `frontend/assets/vendor/chartjs/chart.umd.min.js`
- `frontend/nginx.conf`
- `scripts/iniciar-local.sh`
- `scripts/iniciar.bat`
- `scripts/start-backend.sh`

### Modificados (35)

- `.github/workflows/django.yml`
- `.gitignore`
- `README.md`
- `backend/ai_docs/tests.py`
- `backend/ai_docs/urls.py`
- `backend/ai_docs/views.py`
- `backend/app/settings.py`
- `backend/app/urls.py`
- `backend/requirements.txt`
- `backend/sector/cross_indicators.py`
- `backend/sector/management/commands/seed_cross_demo.py`
- `backend/sector/management/commands/seed_demo.py`
- `backend/sector/models.py`
- `backend/sector/serializers.py`
- `backend/sector/urls.py`
- `backend/sector/views.py`
- `backend/users/models.py`
- `backend/users/validators.py`
- `backend/users/views.py`
- `docs/README_apresentacao.md`
- `frontend/assets/js/app-shell.js`
- `frontend/assets/js/assistente.js`
- `frontend/assets/js/atendimentos.js`
- `frontend/assets/js/indicadores-cruzados.js`
- `frontend/assistente.html`
- `frontend/atendimentos.html`
- `frontend/configuracoes.html`
- `frontend/dashboard-content.html`
- `frontend/dashboard.html`
- `frontend/index.html`
- `frontend/indicadores-cruzados.html`
- `frontend/indicadores.html`
- `frontend/primeiro-acesso.html`
- `frontend/recuperar-senha.html`
- `frontend/usuarios.html`

### Removidos (42)

- `PROJETO_CHAT_LOCAL.md`
- `README_fluxo_n8n.md`
- `SIGDEI_Postman_Collection.json`
- `backend/ai_docs/dashboard.py`
- `backend/ai_docs/insights.py`
- `backend/ai_docs/rag.py`
- `backend/oficios/__initi__.py`
- `backend/oficios/models.py`
- `backend/oficios/serializers.py`
- `backend/oficios/urls.py`
- `backend/oficios/views.py`
- `backend/projects/models.py`
- `backend/projects/serializers.py`
- `backend/projects/urls.py`
- `backend/projects/views.py`
- `backup_pimois.json`
- `deploy/n8n/.env.example`
- `deploy/n8n/.gitignore`
- `deploy/n8n/Caddyfile`
- `deploy/n8n/compose.yaml`
- `docs/EAP/Dicionario_EAP_SetorPúblico_PI_IV_v01.pdf`
- `docs/Estimativa de Custos e ROI - SIGDEI (PMBOK).pdf`
- `docs/Integrantes e RA.txt`
- `docs/Ishikawa - Inconsistência entre documentos do SIGDEI (PMBOK).pdf`
- `docs/Matriz_Raci_SetorPúblico_PI_IV_v02.pdf`
- `docs/PDM_Setor_Público_PI_IV.pdf`
- `docs/prototipo/index.html`
- `fluxo_n8n_chat_dashboard_gafia.json`
- `frontend/assets/css/indicadores-cruzados.css`
- `frontend/assets/js/logoBase64.js`
- `frontend/oficios.html`
- `frontend/projetos.html`
- `gafia_docs.py`
- `iniciar.bat`
- `iniciar_rede.bat`
- `preview/assistente.html`
- `requirements.txt`
- `tests/test_index.py`
- `tests/test_server.py`
- `web/app.js`
- `web/index.html`
- `web/style.css`
