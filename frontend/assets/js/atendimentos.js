(async () => {
    const { api, session, today, options } = Sigdei;
    const user = session();
    if (!user) return;
    const byId = id => document.getElementById(id);
    const isAdmin = user.nivel_acesso === 'Administrador';
    const canRecord = ['Administrador', 'Gestor', 'Colaborador', 'Usuário'].includes(user.nivel_acesso);
    const companyForm = byId('company-form');
    const attendanceForm = byId('attendance-form');
    const companyStatus = byId('company-found');
    const attendanceStatus = byId('attendance-status');
    const attendanceButton = byId('save-attendance');
    const sectorInput = byId('sector');
    const kindInput = byId('attendance-type');
    const cnpjInput = byId('cnpj');
    const currentDate = today();
    const specificTypes = {
        SEBRAE: ['SEBRAE_ORIENTACAO', 'Orientação SEBRAE'],
        BP: ['BP_LIBERACAO', 'Crédito liberado'],
        PAT: ['PAT_VAGA', 'Vaga captada no PAT'],
    };
    let company = null;
    let sectorCodes = new Map();
    byId('attendance-date').value = currentDate;
    ['attendance-date', 'released', 'opened'].forEach(id => { byId(id).max = currentDate; });
    if (!canRecord || (!isAdmin && !user.id_setor)) {
        companyForm.hidden = attendanceForm.hidden = true;
        byId('attendance-access').textContent = 'Seu perfil precisa de acesso de registro e de vínculo com um setor.';
        return;
    }

    function chooseCompany(item) {
        company = item;
        const previous = item.setores_atendidos?.length ? ` Já atendida em: ${item.setores_atendidos.join(', ')}.` : '';
        companyStatus.textContent = `Empresa vinculada: ${item.razao_social} (${item.cnpj}).${previous}`;
        byId('attendance-company').textContent = `Empresa: ${item.razao_social}`;
        byId('company-new').hidden = true;
        attendanceButton.disabled = false;
    }

    cnpjInput.addEventListener('input', () => {
        company = null;
        attendanceButton.disabled = true;
        companyStatus.textContent = '';
        byId('company-new').hidden = true;
        byId('attendance-company').textContent = 'Busque ou cadastre a empresa antes de salvar.';
    });
    byId('company-search').addEventListener('click', async event => {
        const button = event.currentTarget;
        const cnpj = cnpjInput.value.trim();
        button.disabled = true;
        try {
            if (!cnpj) throw new Error('Informe o CNPJ.');
            companyStatus.textContent = 'Buscando empresa…';
            const found = await api(`/empresas/?cnpj=${encodeURIComponent(cnpj)}`);
            if (cnpjInput.value.trim() !== cnpj) return;
            if (found.length) chooseCompany(found[0]);
            else {
                byId('company-new').hidden = false;
                ['razao-social', 'ramo', 'bairro'].forEach(id => { byId(id).value = ''; });
                companyStatus.textContent = 'CNPJ não encontrado. Complete o cadastro.';
            }
        } catch (error) {
            companyStatus.textContent = error.message;
        } finally {
            button.disabled = false;
        }
    });
    companyForm.addEventListener('submit', async event => {
        event.preventDefault();
        const cnpj = cnpjInput.value;
        const button = companyForm.querySelector('[type=submit]');
        button.disabled = true;
        try {
            const item = await api('/empresas/', { method: 'POST', data: {
                cnpj, razao_social: byId('razao-social').value, ramo_atividade: byId('ramo').value,
                bairro: byId('bairro').value,
            } });
            if (cnpjInput.value === cnpj) chooseCompany(item);
        } catch (error) {
            companyStatus.textContent = error.message;
        } finally {
            button.disabled = false;
        }
    });

    function updateType() {
        const kind = kindInput.value;
        document.querySelectorAll('.credit-fields').forEach(field => { field.hidden = kind !== 'BP_LIBERACAO'; });
        document.querySelectorAll('.vacancy-fields').forEach(field => { field.hidden = kind !== 'PAT_VAGA'; });
        byId('credit').required = byId('released').required = kind === 'BP_LIBERACAO';
        byId('vacancies').required = byId('opened').required = kind === 'PAT_VAGA';
    }
    function updateSector() {
        const code = sectorCodes.get(Number(isAdmin ? sectorInput.value : user.id_setor));
        const types = specificTypes[code] ? [specificTypes[code]] : [];
        types.push(['OUTRO', 'Outro atendimento']);
        kindInput.replaceChildren(...types.map(([value, label]) => new Option(label, value)));
        updateType();
    }
    sectorInput.addEventListener('change', updateSector);
    kindInput.addEventListener('change', updateType);
    attendanceForm.addEventListener('submit', async event => {
        event.preventDefault();
        if (!company || attendanceButton.disabled) return;
        const kind = kindInput.value;
        const data = { empresa: company.id, data_atendimento: byId('attendance-date').value,
            tipo: kind, desfecho: byId('outcome').value };
        if (isAdmin) data.setor = Number(sectorInput.value);
        if (kind === 'BP_LIBERACAO') Object.assign(data, { valor_credito: byId('credit').value, data_liberacao: byId('released').value });
        if (kind === 'PAT_VAGA') Object.assign(data, { vagas: Number(byId('vacancies').value), data_abertura_vaga: byId('opened').value });
        attendanceButton.disabled = true;
        try {
            const saved = await api('/atendimentos/', { method: 'POST', data });
            attendanceStatus.textContent = `Atendimento ${saved.id} salvo.`;
            attendanceForm.reset();
            sectorInput.value = data.setor || '';
            byId('attendance-date').value = currentDate;
            updateSector();
        } catch (error) {
            attendanceStatus.textContent = error.message;
        } finally {
            attendanceButton.disabled = !company;
        }
    });
    try {
        const sectors = await api('/setores/');
        sectorCodes = new Map(sectors.map(sector => [sector.id_setor, sector.codigo]));
        if (isAdmin) {
            options(sectorInput, sectors.map(sector => ({ value: sector.id_setor, label: sector.nome })), 'Selecione');
            sectorInput.required = true;
            byId('sector-wrap').hidden = false;
        }
        updateSector();
    } catch (error) {
        attendanceStatus.textContent = error.message;
    }
})();
