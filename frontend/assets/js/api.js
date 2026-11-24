(() => {
    const { hostname, port, protocol } = window.location;
    const base = port === '5500' ? `${protocol}//${hostname}:8000/api/v1` : '/api/v1';
    const user = () => JSON.parse(localStorage.getItem('user') || 'null');
    function session() {
        if (!localStorage.getItem('jwt_token') || !user()) {
            window.top.location.replace('index.html');
            return null;
        }
        return user();
    }
    function errorText(data) {
        return Object.entries(data).map(([key, value]) =>
            ['detail', 'erro', 'error', 'non_field_errors'].includes(key)
                ? String(value) : `${key.replaceAll('_', ' ')} — ${value}`
        ).join('\n');
    }
    async function api(path, { method = 'GET', data } = {}) {
        const headers = { Authorization: `Bearer ${localStorage.getItem('jwt_token')}` };
        if (data !== undefined) headers['Content-Type'] = 'application/json';
        const response = await fetch(base + path, { method, headers, body: JSON.stringify(data) });
        if (response.status === 401) {
            localStorage.removeItem('jwt_token');
            localStorage.removeItem('user');
            window.top.location.replace('index.html');
        }
        if (response.status === 204) return null;
        const body = await response.json();
        if (!response.ok) throw new Error(errorText(body) || 'A consulta falhou.');
        return body;
    }
    const today = () => new Date().toLocaleDateString('sv-SE', { timeZone: 'America/Sao_Paulo' });
    const date = value => value ? value.split('-').reverse().join('/') : '—';
    const number = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 });
    function value(amount, unit = '') {
        if (amount === null || amount === undefined) return 'Sem dados';
        return `${number.format(amount)}${unit === '%' ? '%' : unit ? ' ' + unit : ''}`;
    }
    function element(tag, content, className) {
        const node = document.createElement(tag);
        if (content !== undefined) node.textContent = content;
        if (className) node.className = className;
        return node;
    }
    function row(values) {
        const tr = element('tr');
        values.forEach(value => {
            const cell = element('td');
            if (value instanceof Node) cell.append(value);
            else cell.textContent = value;
            tr.append(cell);
        });
        return tr;
    }
    function options(select, entries, placeholder) {
        select.replaceChildren(new Option(placeholder, ''), ...entries.map(item => new Option(item.label, item.value)));
    }
    window.Sigdei = { api, base, session, today, date, value, element, row, options };
})();
