(async () => {
    const { api, session, element, row, value, options, today, date } = Sigdei;
    const user = session();
    if (!user) return;
    const get = id => document.getElementById(id);
    const form = get('dashboard-filters');
    const fields = form.elements;
    const strategic = ['Administrador', 'Gestor', 'Secretário'].includes(user.nivel_acesso) && user.visao_estrategica;
    const currentDate = today();
    let indicators = [];
    let charts = [];
    fields.inicio.value = `${currentDate.slice(0, 4)}-01-01`;
    fields.fim.value = currentDate;
    fields.inicio.max = fields.fim.max = currentDate;

    function card(label, result) {
        const article = element('article', undefined, 'panel');
        article.append(element('span', label, 'muted'), element('strong', result));
        return article;
    }
    function filterIndicators() {
        const prior = fields.indicador.value;
        const matching = indicators.filter(indicator =>
            (!fields.setor.value || String(indicator.id_setor) === fields.setor.value)
            && (!fields.tipo.value || indicator.tipo_dado === fields.tipo.value)
        );
        options(fields.indicador, matching.map(ind => ({ value: ind.id_indicador, label: ind.nome })), 'Todos');
        if (matching.some(ind => String(ind.id_indicador) === prior)) fields.indicador.value = prior;
    }
    function renderSeries(data) {
        charts.forEach(chart => chart.destroy());
        charts = [];
        const container = get('charts');
        container.replaceChildren();
        if (!data.some(item => item.serie.length && item.valor !== null)) {
            container.append(element('p', 'Sem medições calculáveis no período.', 'muted'));
            return;
        }
        for (const item of data.filter(item => item.serie.length && item.valor !== null)) {
            const panel = element('article', undefined, 'panel');
            panel.append(element('h3', item.nome), element('p', item.setor, 'muted'));
            if (item.tipo === 'porcentagem') {
                const meter = element('meter');
                meter.min = 0;
                meter.max = 100;
                meter.value = Number(item.valor);
                meter.setAttribute('aria-label', item.nome);
                panel.append(meter, element('p', value(item.valor, item.unidade || '%')));
            }
            if (window.Chart) {
                const wrap = element('div', undefined, 'canvas-wrap');
                const canvas = element('canvas');
                canvas.setAttribute('aria-label', `Série mensal de ${item.nome}`);
                canvas.setAttribute('role', 'img');
                wrap.append(canvas);
                panel.append(wrap);
                container.append(panel);
                charts.push(new Chart(canvas, {
                    type: item.tipo === 'tempo' ? 'line' : 'bar',
                    data: {
                        labels: item.serie.map(point => point.mes),
                        datasets: [{
                            label: item.unidade || item.nome,
                            data: item.serie.map(point => point.valor),
                            backgroundColor: '#12857f', borderColor: '#12857f', tension: 0.2,
                        }],
                    },
                    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
                        scales: { y: { beginAtZero: true, max: item.tipo === 'porcentagem' ? 100 : undefined } } },
                }));
            } else {
                container.append(panel);
            }
            const details = element('details');
            details.open = !window.Chart;
            details.append(element('summary', 'Valores por mês'));
            const table = element('table');
            table.append(...item.serie.map(point => row([point.mes, value(point.valor, item.unidade)])));
            details.append(table);
            panel.append(details);
        }
    }
    function render(data) {
        get('summary').replaceChildren(card('Indicadores cadastrados', value(data.total_indicadores)),
            card('Empresas atendidas', value(data.empresas)), card('Atendimentos', value(data.atendimentos)),
            card('Vagas captadas no PAT', value(data.vagas_captadas)));
        get('sector-counts').replaceChildren(...data.setores.map(item => element('p', `${item.nome} · ${item.total}`)));
        get('result-rows').replaceChildren(...data.indicadores.map(item => row([item.nome, item.setor,
            value(item.valor, item.unidade), item.meta === null ? '—' :
                `${item.criterio_meta === 'maxima' ? 'Até' : 'A partir de'} ${value(item.meta, item.unidade)}`,
            value(item.lancamentos), item.meta_alcancada === null ? '—' : item.meta_alcancada ? 'Atingida' : 'Fora da meta'])));
        get('dashboard-content').hidden = false;
        renderSeries(data.indicadores);
    }
    async function load() {
        const button = form.querySelector('button');
        button.disabled = true;
        const status = get('dashboard-status');
        status.dataset.error = 'false';
        status.textContent = 'Atualizando dados…';
        get('dashboard-content').hidden = true;
        try {
            const params = new URLSearchParams([...new FormData(form)].filter(([, entry]) => entry));
            const data = await api(`/dashboard/?${params}`);
            render(data);
            status.textContent = `Período de ${date(data.periodo.inicio)} a ${date(data.periodo.fim)}.`;
            if (strategic) {
                get('strategic').hidden = false;
                get('cross-summary').replaceChildren();
                get('cross-status').textContent = 'Carregando relações entre setores…';
                try {
                    const dates = new URLSearchParams({ inicio: data.periodo.inicio, fim: data.periodo.fim, resumo: '1' });
                    const cross = await api(`/dashboard/cruzados/?${dates}`);
                    get('cross-summary').replaceChildren(...cross.indicadores.filter(item => ['IC-05', 'IC-06', 'IC-07'].includes(item.id))
                        .map(item => card(item.nome, value(item.valor))));
                    get('cross-status').textContent = '';
                } catch (error) {
                    get('cross-status').textContent = error.message;
                }
            }
        } catch (error) {
            status.dataset.error = 'true';
            status.textContent = error.message;
        } finally {
            button.disabled = false;
        }
    }
    fields.setor.addEventListener('change', filterIndicators);
    fields.tipo.addEventListener('change', filterIndicators);
    form.addEventListener('submit', event => { event.preventDefault(); load(); });
    try {
        const [sectors, catalog] = await Promise.all([api('/setores/'), api('/indicadores/')]);
        indicators = catalog;
        options(fields.setor, sectors.filter(item => user.nivel_acesso === 'Administrador' || item.id_setor === user.id_setor)
            .map(item => ({ value: item.id_setor, label: item.nome })), 'Todos os autorizados');
        filterIndicators();
        await load();
    } catch (error) {
        get('dashboard-status').textContent = error.message;
        get('dashboard-status').dataset.error = 'true';
    }
})();
