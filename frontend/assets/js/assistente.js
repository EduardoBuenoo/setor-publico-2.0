(() => {
    const { api, session, today, element, date } = Sigdei;
    const user = session();
    if (!user) return;
    const get = id => document.getElementById(id);
    const status = get('assistant-status');
    const messages = get('assistant-messages');
    const form = get('assistant-form');
    const question = get('assistant-question');
    const button = get('assistant-send');
    const start = get('assistant-start');
    const end = get('assistant-end');
    const source = get('assistant-source');
    get('assistant-source-label').hidden = !['Administrador', 'Gestor'].includes(user.nivel_acesso);
    start.value = `${today().slice(0, 4)}-01-01`;
    end.value = today();
    start.max = end.max = today();

    function sourceLabel(item) {
        if (item.arquivo) return `${item.arquivo}${item.pagina ? `, página ${item.pagina}` : ''}`;
        const period = item.periodo ? `, de ${date(item.periodo.inicio)} a ${date(item.periodo.fim)}` : '';
        return `${item.rotulo || item.indicador || item.referencia}${period}`;
    }
    function addMessage(role, content, sources = []) {
        const box = element('article', undefined, `assistant-message ${role}`);
        box.append(element('strong', role === 'user' ? 'Você' : 'Assistente'), element('div', content));
        if (sources.length) box.append(element('div', sources.map(sourceLabel).join('\n'), 'assistant-sources'));
        messages.append(box);
        box.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
    async function refreshStatus() {
        const documents = source.value === 'documentos';
        start.disabled = end.disabled = documents;
        try {
            const data = await api(documents ? '/documentos/status/' : '/assistente/status/');
            status.textContent = data.mensagem;
            if (data.classificador_configurado) status.textContent += ` Classificador configurado (${data.modo}).`;
        } catch (error) {
            status.textContent = error.message;
        }
    }
    source.addEventListener('change', refreshStatus);
    form.addEventListener('submit', async event => {
        event.preventDefault();
        const text = question.value.trim();
        if (!text) return;
        addMessage('user', text);
        const documents = source.value === 'documentos';
        button.disabled = source.disabled = true;
        status.textContent = 'Consultando fontes autorizadas…';
        try {
            const path = documents ? '/documentos/perguntar/' : '/assistente/perguntar/';
            const data = { pergunta: text };
            if (!documents) Object.assign(data, { inicio: start.value, fim: end.value });
            const response = await api(path, { method: 'POST', data });
            addMessage('assistant', response.resposta, response.fontes);
            question.value = '';
        } catch (error) {
            addMessage('assistant', error.message);
        } finally {
            button.disabled = source.disabled = false;
            refreshStatus();
            question.focus();
        }
    });
    refreshStatus();
})();
