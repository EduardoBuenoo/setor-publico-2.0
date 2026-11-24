(() => {
    const { api, session, today, date, value, element, row } = Sigdei;
    if (!session()) return;
    const get = id => document.getElementById(id);
    const form = get('cross-form');
    const status = get('cross-status');
    const currentDate = today();
    form.elements.inicio.value = `${currentDate.slice(0, 4)}-01-01`;
    form.elements.fim.value = currentDate;
    form.elements.inicio.max = form.elements.fim.max = currentDate;

    function render(data) {
        get('cross-table').replaceChildren(...data.indicadores.map(item => {
            const method = element('div');
            method.append(element('p', item.formula), element('p', item.setores.join(' · '), 'muted'),
                element('p', item.origem, 'muted'));
            const result = element('div');
            result.append(element('strong', value(item.valor, item.unidade)));
            if (Number.isInteger(item.numerador) && item.denominador) {
                result.append(element('p', `${item.numerador} de ${item.denominador} empresas`, 'muted'));
            }
            return row([`${item.id} · ${item.nome}`, result, method]);
        }));
        get('cross-series').replaceChildren(...data.serie.map(item => row([item.mes, value(item.empresas_atendidas),
            value(item.empresas_financiadas), value(item.vagas_captadas)])));
        get('cross-companies').replaceChildren(...data.empresas.map(item =>
            row([item.empresa, value(item.setores), value(item.atendimentos)])));
        get('series-empty').hidden = Boolean(data.serie.length);
        get('companies-empty').hidden = Boolean(data.empresas.length);
    }
    async function load() {
        const apply = form.querySelector('[type=submit]');
        status.textContent = 'Atualizando indicadores…';
        status.dataset.error = 'false';
        apply.disabled = true;
        get('cross-data').hidden = true;
        try {
            const params = new URLSearchParams(new FormData(form));
            const data = await api(`/dashboard/cruzados/?${params}`);
            render(data);
            get('cross-data').hidden = false;
            status.textContent = `Período de ${date(data.periodo.inicio)} a ${date(data.periodo.fim)}.`;
        } catch (error) {
            status.textContent = error.message;
            status.dataset.error = 'true';
        } finally {
            apply.disabled = false;
        }
    }
    form.addEventListener('submit', event => { event.preventDefault(); load(); });
    get('cross-print').addEventListener('click', () => window.print());
    load();
})();
