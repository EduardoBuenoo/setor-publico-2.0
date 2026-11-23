(async () => {
    const { api, session, element, row, options, date, value, today } = Sigdei;
    const user = session();
    if (!user) return;
    const get = id => document.getElementById(id);
    const catalogForm = get('catalog-filters');
    const definition = get('definition');
    const measurement = get('measurement');
    const labels = { quantidade: 'Quantidade', tempo: 'Tempo', porcentagem: 'Porcentagem',
        diaria: 'Diária', mensal: 'Mensal', trimestral: 'Trimestral', anual: 'Anual', ativo: 'Ativo', inativo: 'Inativo', minima: 'Mínima', maxima: 'Máxima' };
    const recordEvents = { indicador_criado: 'Indicador criado', indicador_editado: 'Indicador editado',
        lancamento_criado: 'Medição registrada', lancamento_editado: 'Medição editada', lancamento_excluido: 'Medição excluída' };
    const historyFields = { id_setor: 'Setor', nome: 'Nome', tipo_dado: 'Tipo', unidade: 'Unidade',
        periodicidade: 'Periodicidade', meta: 'Meta', criterio_meta: 'Critério da meta', descricao: 'Descrição', fonte: 'Fonte',
        situacao: 'Situação', periodo_referencia: 'Referência', valor: 'Valor' };
    const canDefine = ['Administrador', 'Gestor'].includes(user.nivel_acesso);
    const canRecord = ['Administrador', 'Gestor', 'Colaborador', 'Usuário'].includes(user.nivel_acesso);
    const isAdmin = user.nivel_acesso === 'Administrador';
    const canDelete = canDefine;
    const sectorNames = new Map();
    let selected = null;
    let editingDefinition = null;
    let editingRecord = null;
    let recordsPage = 1;
    let historyPage = 1;

    get('back').hidden = window.top !== window;
    get('new-indicator').hidden = !canDefine || (!isAdmin && !user.id_setor);
    measurement.elements.periodo_referencia.max = today();

    function status(id, text, error = false) {
        get(id).textContent = text;
        get(id).dataset.error = error;
    }
    function action(label, callback) {
        const button = element('button', label, 'secondary');
        button.type = 'button';
        button.addEventListener('click', callback);
        return button;
    }
    function updateDefinitionType() {
        const fields = definition.elements;
        const percent = fields.tipo_dado.value === 'porcentagem';
        if (percent && !fields.unidade.value) fields.unidade.value = '%';
        fields.meta.max = percent ? '100' : '99999999.99';
    }
    function openDefinition(item) {
        editingDefinition = item;
        definition.reset();
        const fields = definition.elements;
        for (const [key, initial] of Object.entries(item || {})) {
            if (fields[key]) fields[key].value = initial ?? '';
        }
        if (!isAdmin) fields.id_setor.value = user.id_setor;
        fields.id_setor.disabled = !isAdmin;
        get('definition-title').textContent = item ? 'Editar indicador' : 'Novo indicador';
        status('definition-status', item ? 'Se houver medições, setor, tipo, periodicidade e unidade ficam protegidos.' : '');
        updateDefinitionType();
        definition.hidden = false;
        definition.scrollIntoView({ block: 'start' });
        fields.nome.focus({ preventScroll: true });
    }
    async function loadCatalog() {
        status('catalog-status', 'Carregando catálogo…');
        const params = new URLSearchParams();
        if (get('filter-sector').value) params.set('setor', get('filter-sector').value);
        if (get('filter-type').value) params.set('tipo', get('filter-type').value);
        try {
            const list = await api(`/indicadores/?${params}`);
            get('catalog').replaceChildren(...list.map(item => {
                const controls = element('div', undefined, 'actions');
                controls.append(action('Medições', () => showDetail(item)));
                if (canDefine) controls.append(action('Editar', () => openDefinition(item)));
                return row([item.nome, sectorNames.get(item.id_setor) || 'Sem setor',
                    labels[item.tipo_dado] || item.tipo_dado, labels[item.periodicidade], labels[item.situacao], controls]);
            }));
            status('catalog-status', list.length ? `${list.length} indicador(es)` : 'Nenhum indicador encontrado.');
        } catch (error) {
            status('catalog-status', error.message, true);
        }
    }
    function resetMeasurement() {
        editingRecord = null;
        measurement.reset();
        measurement.elements.periodo_referencia.value = today();
        measurement.hidden = !canRecord || !selected.id_setor || selected.situacao === 'inativo';
        get('measurement-title').textContent = 'Registrar medição';
        get('cancel-measurement').hidden = true;
        status('measurement-status', '');
    }
    function editMeasurement(item) {
        editingRecord = item.id_atividade;
        measurement.hidden = false;
        measurement.elements.periodo_referencia.value = item.periodo_referencia;
        measurement.elements.valor.value = item.valor;
        get('measurement-title').textContent = 'Editar medição';
        get('cancel-measurement').hidden = false;
        status('measurement-status', '');
        measurement.scrollIntoView({ block: 'nearest' });
        measurement.elements.valor.focus({ preventScroll: true });
    }
    async function loadRecords(append = false) {
        const id = selected.id_indicador;
        if (!append) {
            recordsPage = 1;
            get('records').replaceChildren();
        }
        status('record-status', 'Carregando medições…');
        try {
            const data = await api(`/atividades/?indicador=${id}&page=${recordsPage}`);
            if (selected.id_indicador !== id) return;
            get('records').append(...data.results.map(item => {
                const controls = element('div', undefined, 'actions');
                if (canRecord) controls.append(action('Editar medição', () => editMeasurement(item)));
                if (canDelete) controls.append(action('Excluir medição', async () => {
                    if (!window.confirm('Excluir esta medição? O valor anterior ficará no histórico.')) return;
                    try {
                        await api(`/atividades/${item.id_atividade}/`, { method: 'DELETE' });
                        resetMeasurement();
                        await loadRecords();
                        if (get('history').open) await loadHistory();
                    } catch (error) {
                        status('record-status', error.message, true);
                    }
                }));
                return row([date(item.periodo_referencia), value(item.valor, selected.unidade),
                    controls.childElementCount ? controls : '—']);
            }));
            get('more-records').hidden = !data.next;
            status('record-status', data.count ? `${data.count} medição(ões)` : 'Ainda não há medições.');
        } catch (error) {
            status('record-status', error.message, true);
        }
    }
    function describeChange(event) {
        const changes = element('dl', undefined, 'history-fields');
        const before = event.anterior || {};
        const after = event.atual || {};
        const display = (key, value) => {
            if (value === undefined || value === null || value === '') return '—';
            if (key === 'id_setor') return sectorNames.get(value) || String(value);
            if (key === 'periodo_referencia') return date(value);
            return labels[value] || String(value);
        };
        for (const [key, label] of Object.entries(historyFields)) {
            if (before[key] === after[key]) continue;
            const text = `${display(key, before[key])} → ${display(key, after[key])}`;
            changes.append(element('dt', label), element('dd', text));
        }
        const details = element('details', undefined, 'history-event');
        const time = new Date(event.data_hora).toLocaleString('pt-BR');
        details.append(element('summary', `${recordEvents[event.evento]} · ${time}`), changes);
        return details;
    }
    async function loadHistory(append = false) {
        const id = selected.id_indicador;
        if (!append) {
            historyPage = 1;
            get('history-events').replaceChildren();
        }
        status('history-status', 'Carregando histórico…');
        try {
            const data = await api(`/indicadores/${id}/historico/?page=${historyPage}`);
            if (selected.id_indicador !== id) return;
            get('history-events').append(...data.results.map(describeChange));
            get('more-history').hidden = !data.next;
            status('history-status', data.count ? '' : 'Nenhuma alteração auditada para este indicador.');
        } catch (error) {
            status('history-status', error.message, true);
        }
    }
    function showDetail(item) {
        selected = item;
        get('detail-title').textContent = item.nome;
        get('detail-description').textContent = item.descricao;
        get('detail-source').textContent = item.fonte ? `Fonte dos dados — ${item.fonte}` : 'Fonte ainda não informada.';
        resetMeasurement();
        get('measurement-unit').textContent = item.unidade ? `Valor registrado (${item.unidade})` : 'Valor registrado';
        measurement.elements.valor.max = item.tipo_dado === 'porcentagem' ? '100' : '99999999.99';
        get('measurement-help').textContent = item.periodicidade === 'diaria' ? 'Uma medição por dia.'
            : 'A referência será registrada pelo primeiro dia do mês, trimestre ou ano correspondente à periodicidade.';
        get('detail').hidden = false;
        get('detail').scrollIntoView({ block: 'start' });
        loadRecords();
        if (get('history').open) loadHistory();
    }
    async function save(form, statusId, path, method, data, afterSave) {
        const button = form.querySelector('[type=submit]');
        button.disabled = true;
        status(statusId, 'Salvando…');
        try {
            const result = await api(path, { method, data });
            await afterSave(result);
            status(statusId, 'Alteração salva.');
        } catch (error) {
            status(statusId, error.message, true);
        } finally {
            button.disabled = false;
        }
    }

    catalogForm.addEventListener('submit', event => { event.preventDefault(); loadCatalog(); });
    get('new-indicator').addEventListener('click', () => openDefinition(null));
    get('cancel-definition').addEventListener('click', () => { definition.hidden = true; });
    definition.elements.tipo_dado.addEventListener('change', updateDefinitionType);
    definition.addEventListener('submit', event => {
        event.preventDefault();
        const data = Object.fromEntries(new FormData(definition));
        if (!isAdmin) data.id_setor = user.id_setor;
        data.meta = data.meta || null;
        const id = editingDefinition?.id_indicador;
        save(definition, 'definition-status', id ? `/indicadores/${id}/` : '/indicadores/', id ? 'PATCH' : 'POST',
            data, async result => {
                definition.hidden = true;
                await loadCatalog();
                showDetail(result);
                status('record-status', 'Indicador salvo.');
            });
    });
    get('cancel-measurement').addEventListener('click', resetMeasurement);
    measurement.addEventListener('submit', event => {
        event.preventDefault();
        const data = { ...Object.fromEntries(new FormData(measurement)), id_indicador: selected.id_indicador };
        const id = editingRecord;
        save(measurement, 'measurement-status', id ? `/atividades/${id}/` : '/atividades/', id ? 'PATCH' : 'POST',
            data, async () => {
                resetMeasurement();
                await loadRecords();
                if (get('history').open) await loadHistory();
            });
    });
    get('more-records').addEventListener('click', () => { recordsPage += 1; loadRecords(true); });
    get('more-history').addEventListener('click', () => { historyPage += 1; loadHistory(true); });
    get('history').addEventListener('toggle', event => { if (event.target.open && selected) loadHistory(); });

    try {
        const sectors = (await api('/setores/')).filter(item => isAdmin || item.id_setor === user.id_setor);
        sectors.forEach(item => sectorNames.set(item.id_setor, item.nome));
        const entries = sectors.map(item => ({ value: item.id_setor, label: item.nome }));
        options(get('filter-sector'), entries, 'Todos os setores acessíveis');
        options(definition.elements.id_setor, entries, 'Selecione');
        await loadCatalog();
    } catch (error) {
        status('catalog-status', error.message, true);
    }
})();
