"""Interpreta perguntas e executa somente consultas de leitura predefinidas."""

import json
import logging
import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal
from urllib.request import Request, urlopen

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.utils.timezone import localdate

from sector.cross_indicators import CREDIT, VACANCY, SECTORS, SOURCE, company_relationships, cross_snapshot
from sector.models import Sector
from sector.reporting import attendance_for, indicator_dashboard, indicators_for, period_payload

logger = logging.getLogger(__name__)

CROSS_INTENTS = {'ic-01', 'ic-02', 'ic-03', 'ic-04', 'ic-05', 'ic-06', 'ic-07', 'ic-08', 'empresas_multissetoriais'}
INTENTS = CROSS_INTENTS | {'atendimentos', 'empresas_atendidas', 'financiamentos', 'vagas',
                           'crescimento', 'evolucao', 'semestres'}


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold()) if not unicodedata.combining(c))


def sector_code(text):
    for code, keywords in {'SEBRAE': ('sebrae',), 'BP': ('banco do povo',),
                           'PAT': ('pat',), 'PROCON': ('procon',)}.items():
        if any(re.search(r'\b' + term + r'\b', text) for term in keywords):
            return code
    return ''


def intent_for(text):
    code = re.search(r'\bic[ -]?0?([1-8])\b', text)
    if code:
        return f'ic-0{code[1]}'
    if 'semestre' in text and ('compar' in text or 'primeiro e' in text):
        return 'semestres'
    if 'crescimento' in text or 'mais cresceu' in text:
        return 'crescimento'
    if any(term in text for term in ('tres setores', 'tres ou mais', '3 setores', '3 ou mais')):
        return 'ic-03' if 'jornada' in text else 'ic-07'
    if 'multissetor' in text or 'mais de um setor' in text or 'dois ou mais setores' in text:
        return 'empresas_multissetoriais' if any(term in text for term in ('quais', 'listar', 'liste')) else 'ic-06'
    credit = any(term in text for term in ('financi', 'credito', 'emprest', 'liberac'))
    vacancies = any(term in text for term in ('vagas', 'emprego', 'captac'))
    if credit and vacancies:
        if ('relacao' in text or '100 mil' in text) and 'quantas empresas' not in text:
            return 'ic-02'
        return 'ic-05'
    if credit and 'sebrae' in text:
        return 'ic-01' if 'percent' in text or 'taxa' in text else 'ic-08'
    if 'evolu' in text or 'indicador' in text or 'historico' in text:
        return 'evolucao'
    if vacancies:
        return 'vagas'
    if credit:
        return 'financiamentos'
    if 'empresa' in text and ('atendid' in text or 'orientad' in text):
        return 'empresas_atendidas'
    if 'atendiment' in text:
        return 'atendimentos'
    return None


def provider_available():
    return settings.SIGDEI_AI_PROVIDER in ('ollama', 'openai') and (
        settings.SIGDEI_AI_PROVIDER == 'ollama' or bool(settings.SIGDEI_AI_API_KEY)
    )


def classify_with_provider(question):
    if not provider_available():
        return None
    # A pergunta pode ser enviada ao provedor escolhido. O banco e o resultado ficam no SIGDEI.
    masked = re.sub(
        r'[\w.+-]+@[\w.-]+|\b[A-Z0-9]{2}\.?[A-Z0-9]{3}\.?'
        r'[A-Z0-9]{3}/?[A-Z0-9]{4}-?\d{2}\b|\b[\d./-]{7,}\b',
        '[oculto]', question, flags=re.IGNORECASE,
    )
    messages = [
        {'role': 'system', 'content': 'Selecione uma única opção de consulta do SIGDEI e devolva '
         'somente JSON {"intencao":"opção"}. Se não houver opção adequada, use "desconhecida". '
         'As opções são ' + ', '.join(sorted(INTENTS)) + '.'},
        {'role': 'user', 'content': masked},
    ]
    if settings.SIGDEI_AI_PROVIDER == 'ollama':
        url = settings.SIGDEI_AI_URL or 'http://127.0.0.1:11434'
        endpoint = url.rstrip('/') + '/api/chat'
        payload = {'model': settings.SIGDEI_AI_MODEL or 'qwen2.5:1.5b', 'messages': messages,
                   'stream': False, 'format': 'json', 'options': {'num_predict': 64}}
        headers = {}
    else:
        url = settings.SIGDEI_AI_URL or 'https://api.openai.com/v1'
        endpoint = url.rstrip('/') + '/chat/completions'
        payload = {'model': settings.SIGDEI_AI_MODEL or 'gpt-4.1-mini', 'messages': messages,
                   'response_format': {'type': 'json_object'}, 'max_completion_tokens': 100}
        headers = {'Authorization': f'Bearer {settings.SIGDEI_AI_API_KEY}'}
    try:
        request = Request(endpoint, data=json.dumps(payload).encode(),
                          headers={'Content-Type': 'application/json', **headers})
        with urlopen(request, timeout=6) as response:
            result = json.loads(response.read(32768))
        content = (result['message'] if settings.SIGDEI_AI_PROVIDER == 'ollama'
                   else result['choices'][0]['message'])['content']
        intent = json.loads(content)['intencao']
        return intent if isinstance(intent, str) and intent in INTENTS else None
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        logger.warning('Classificador do assistente indisponível (%s)', type(exc).__name__)
        return None


def question_period(text, start, end):
    today = localdate()
    if 'neste ano' in text or 'este ano' in text:
        return date(today.year, 1, 1), today
    if 'ano passado' in text:
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
    match = re.search(r'ultimos? (\d{1,2}|seis|doze) meses', text)
    if match:
        token = match[1]
        count = int(token) if token.isdigit() else {'seis': 6, 'doze': 12}[token]
        if 1 <= count <= 60:
            month = today.year * 12 + today.month - count
            year, offset = divmod(month, 12)
            return date(year, offset + 1, 1), today
    year = re.search(r'\b(20\d{2})\b', text)
    if year and 'semestre' in text and int(year[1]) <= today.year:
        return date(int(year[1]), 1, 1), min(date(int(year[1]), 12, 31), today)
    return start, end


def metric_answer(intent, start, end):
    if intent == 'empresas_multissetoriais':
        rows = company_relationships(start, end)
        return ('\n'.join(f"{row['empresa']} · {row['setores']} setores, {row['atendimentos']} atendimentos"
                          for row in rows) if rows else 'Nenhuma empresa multissetorial encontrada no período.',
                SOURCE + ' · até 30 empresas, por volume de atendimentos')
    metric = next(item for item in cross_snapshot(start, end) if item['id'].lower() == intent)
    if metric['valor'] is None:
        return f"{metric['nome']}. Dados insuficientes para calcular o indicador no período.", metric['origem']
    result = f"{metric['nome']}: {metric['valor']} {metric['unidade']}."
    if intent == 'ic-02':
        result += ' A sequência cronológica indica associação entre os registros. Ela não demonstra geração de empregos.'
    return result, metric['origem'] + ' · ' + metric['formula']


def attendance_answer(intent, records, start, end):
    if intent == 'crescimento':
        if start == end:
            return 'Informe um intervalo com duas janelas comparáveis.'
        days = ((end - start).days + 1) // 2
        first_end = start + timedelta(days=days - 1)
        second_start = end - timedelta(days=days - 1)
        rows = records.values('setor__nome').annotate(
            anterior=Count('pk', filter=attendance_range(start, first_end)),
            recente=Count('pk', filter=attendance_range(second_start, end)),
        )
        rates = [(Decimal(row['recente'] - row['anterior']) * 100 / row['anterior'], row)
                 for row in rows if row['anterior'] and row['recente']]
        if not rates:
            return 'Dados insuficientes de atendimentos nas duas janelas para comparar crescimento.'
        rate, row = max(rates, key=lambda entry: entry[0])
        if rate <= 0:
            return 'Entre os setores com registros nas duas janelas, nenhum teve aumento nos atendimentos.'
        return (f"{row['setor__nome']} teve a maior variação de atendimentos ({rate:.2f}%), "
                f"de {row['anterior']} para {row['recente']}. Janelas de {days} dias.")
    if intent == 'vagas':
        total = records.filter(VACANCY, data_abertura_vaga__range=(start, end)).aggregate(total=Sum('vagas'))['total']
        return f'Foram captadas {total} vagas.' if total is not None else 'Sem registros de vagas captadas no período.'
    if intent == 'financiamentos':
        counts = records.filter(CREDIT, data_liberacao__range=(start, end)).aggregate(
            empresas=Count('empresa', distinct=True), total=Sum('valor_credito'),
        )
        return (f"Crédito liberado para {counts['empresas']} empresas, total de R$ {counts['total']:.2f}."
                if counts['total'] is not None else 'Sem registros de crédito liberado no período.')
    records = records.filter(attendance_range(start, end))
    if intent == 'empresas_atendidas':
        count = records.values('empresa_id').order_by().distinct().count()
        if count == 1:
            return '1 empresa com atendimento registrado no período.'
        return f'{count} empresas distintas com atendimento registrado no período.'
    return f'{records.count()} atendimentos registrados no período.'


def attendance_range(start, end):
    return Q(data_atendimento__range=(start, end))


def indicator_answer(intent, text, user, code, start, end):
    scoped = indicators_for(user)
    if code:
        scoped = scoped.filter(id_setor__codigo=code)
    matches = [pk for pk, name in scoped.values_list('pk', 'nome')
               if len(name) >= 3 and re.search(r'(?<!\w)' + re.escape(normalized(name)) + r'(?!\w)', text)]
    filters = {'inicio': start, 'fim': end}
    if len(matches) == 1:
        filters['indicador'] = matches[0]
    if code:
        filters['setor'] = Sector.objects.filter(codigo=code).values_list('pk', flat=True).first() or 0
    if intent == 'semestres':
        july = date(end.year, 7, 1)
        january = date(end.year, 1, 1)
        if end < july:
            return 'O segundo semestre ainda não está disponível no período selecionado.'
        if start >= july or start.year != end.year:
            return 'Selecione um intervalo de um mesmo ano que inclua os dois semestres.'
        first = indicator_dashboard(user, {**filters, 'inicio': max(january, start), 'fim': july - timedelta(days=1)})
        second = indicator_dashboard(user, {**filters, 'inicio': july})
        second_by_id = {row['id']: row for row in second['indicadores']}
        lines = [f"{row['nome']} ({row['setor']}): {format_value(row)} → {format_value(second_by_id[row['id']])}"
                 for row in first['indicadores']
                 if row['valor'] is not None or second_by_id[row['id']]['valor'] is not None]
        header = 'Primeiro → segundo semestre (intervalo selecionado).'
    else:
        results = indicator_dashboard(user, filters)
        lines = [f"{row['nome']} ({row['setor']}): " + ', '.join(
            f"{point['mes']} {format_value({**row, 'valor': point['valor']})}" for point in row['serie']
        ) for row in results['indicadores'] if row['serie'] and row['valor'] is not None]
        header = 'Evolução mensal dos indicadores autorizados.'
    if not lines:
        return 'Sem medições comparáveis disponíveis no período para os indicadores autorizados.'
    return '\n'.join([header, *lines[:12]] + (['Exibidos 12 indicadores. Informe um nome para detalhar.'] if len(lines) > 12 else []))


def format_value(row):
    return f"{row['valor']} {row['unidade']}".strip() if row['valor'] is not None else 'sem medições'


def answer(user, question, start, end, *, strategic=False, cross_only=False):
    text = normalized(question)
    start, end = question_period(text, start, end)
    selected = intent_for(text)
    mode = 'deterministico'
    if selected is None:
        selected = classify_with_provider(question)
        mode = 'classificador_' + settings.SIGDEI_AI_PROVIDER if selected else mode
    code = sector_code(text)
    period = period_payload(start, end)
    source = None
    if selected in CROSS_INTENTS:
        if not strategic:
            response = 'A consulta exige permissão de visão estratégica.'
        else:
            response, source = metric_answer(selected, start, end)
    elif selected is None or cross_only:
        response = ('Não identifiquei uma consulta suportada. Pergunte sobre atendimentos, empresas, '
                    'crédito, vagas, evolução de indicadores ou um indicador cruzado pelo código IC.')
    elif code and user.nivel_acesso != 'Administrador' and not Sector.objects.filter(
        pk=user.id_setor_id, codigo=code,
    ).exists():
        response = 'Seu perfil não tem acesso aos dados do setor solicitado.'
    elif selected in ('evolucao', 'semestres'):
        response = indicator_answer(selected, text, user, code, start, end)
        source = 'Lançamentos autorizados do catálogo de indicadores'
    else:
        records = attendance_for(user)
        if code:
            records = records.filter(setor__codigo=code)
        response = attendance_answer(selected, records, start, end)
        source = SOURCE + (f' · {SECTORS[code]}' if code else ' · setores autorizados')
    logger.info('Consulta do assistente: intenção=%s modo=%s', selected, mode)
    return {'resposta': response, 'modo': mode, 'periodo': period,
            'fontes': [{'rotulo': source, 'periodo': period}] if source else []}
