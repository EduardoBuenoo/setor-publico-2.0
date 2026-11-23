"""Agregações por empresa canônica, identificada pelo CNPJ único do cadastro."""

from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, Exists, F, Max, Min, OuterRef, Q, Sum
from django.db.models.functions import TruncMonth

from .models import Atendimento, Empresa
from .reporting import attendance_records


SECTORS = {'SEBRAE': 'SEBRAE-Aqui', 'BP': 'Banco do Povo', 'PAT': 'PAT', 'PROCON': 'PROCON'}
FOMENTO = ('SEBRAE', 'BP', 'PAT')
SOURCE = 'Atendimentos vinculados ao cadastro de empresas por CNPJ'
ORIENTATION = Q(setor__codigo='SEBRAE', tipo=Atendimento.SEBRAE)
CREDIT = Q(setor__codigo='BP', tipo=Atendimento.CREDITO, valor_credito__gt=0)
VACANCY = Q(setor__codigo='PAT', tipo=Atendimento.VAGA, vagas__gt=0)


def percent(numerator, denominator):
    if numerator is None or not denominator:
        return None
    return str((Decimal(numerator) * 100 / denominator).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def cross_groups(start, end):
    attended = Q(data_atendimento__range=(start, end))
    orientation = ORIENTATION & attended
    credit = CREDIT & Q(data_liberacao__range=(start, end))
    vacancy = VACANCY & Q(data_abertura_vaga__range=(start, end))
    groups = attendance_records().filter(
        (attended & Q(setor__codigo__in=SECTORS)) | credit | vacancy,
    ).order_by().values('empresa_id').annotate(
        setores=Count('setor', distinct=True, filter=attended & Q(setor__codigo__in=SECTORS)),
        fomento=Count('setor', distinct=True, filter=attended & Q(setor__codigo__in=FOMENTO)),
        atendimentos=Count('pk', filter=attended & Q(setor__codigo__in=SECTORS)),
        primeira_orientacao=Min('data_atendimento', filter=orientation),
        ultimo_credito=Max('data_liberacao', filter=credit),
        primeiro_credito=Min('data_liberacao', filter=credit),
        ultima_vaga=Max('data_abertura_vaga', filter=vacancy),
    )
    return groups, orientation, credit, vacancy


def cross_snapshot(start, end):
    groups, orientation, credit, vacancy = cross_groups(start, end)
    totals = groups.aggregate(
        orientadas=Count('empresa_id', filter=Q(primeira_orientacao__isnull=False)),
        financiadas=Count('empresa_id', filter=Q(primeiro_credito__isnull=False)),
        com_vagas=Count('empresa_id', filter=Q(ultima_vaga__isnull=False)),
        orientadas_financiadas=Count('empresa_id', filter=Q(ultimo_credito__gt=F('primeira_orientacao'))),
        financiadas_com_vagas=Count('empresa_id', filter=Q(ultima_vaga__gt=F('primeiro_credito'))),
        atendidas=Count('empresa_id', filter=Q(setores__gte=1)),
        fomento_atendidas=Count('empresa_id', filter=Q(fomento__gte=1)),
        fomento_multi=Count('empresa_id', filter=Q(fomento__gte=2)),
        multissetoriais=Count('empresa_id', filter=Q(setores__gte=2)),
        tres_setores=Count('empresa_id', filter=Q(setores__gte=3)),
    )
    oriented_credit = totals['orientadas_financiadas'] if totals['orientadas'] and totals['financiadas'] else None
    credit_vacancies = totals['financiadas_com_vagas'] if totals['financiadas'] and totals['com_vagas'] else None
    credits = attendance_records().filter(credit)
    vacancies = attendance_records().filter(vacancy)
    credit_total = credits.aggregate(total=Sum('valor_credito'))['total']
    earlier_credit = credits.filter(empresa_id=OuterRef('empresa_id'), data_liberacao__lt=OuterRef('data_abertura_vaga'))
    vacancies_after_credit = None
    if credit_vacancies is not None:
        vacancies_after_credit = vacancies.filter(Exists(earlier_credit)).aggregate(total=Sum('vagas'))['total'] or 0
    first_orientation = attendance_records().filter(orientation, empresa_id=OuterRef('empresa_id'))
    later_vacancy = vacancies.filter(empresa_id=OuterRef('empresa_id'), data_abertura_vaga__gt=OuterRef('data_liberacao'))
    journey = None
    if oriented_credit is not None and credit_vacancies is not None:
        journey = credits.filter(Exists(first_orientation.filter(data_atendimento__lt=OuterRef('data_liberacao'))),
                                 Exists(later_vacancy)).aggregate(total=Count('empresa', distinct=True))['total']
    ratio = None if vacancies_after_credit is None else str(
        (Decimal(vacancies_after_credit) * 100000 / credit_total).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    )
    fomento = [SECTORS[code] for code in FOMENTO]
    all_sectors = list(SECTORS.values())

    def metric(code, name, value, unit, formula, sectors, **details):
        return {'id': code, 'nome': name, 'valor': value, 'unidade': unit, 'formula': formula,
                'setores': sectors, 'origem': SOURCE, **details}

    return [
        metric('IC-01', 'Orientação seguida de crédito', percent(oriented_credit, totals['orientadas']), '%',
               'CNPJs com orientação antes da liberação ÷ CNPJs orientados × 100', fomento[:2],
               numerador=oriented_credit, denominador=totals['orientadas']),
        metric('IC-02', 'Vagas captadas após liberação de crédito', ratio, 'vagas por R$ 100 mil',
               'Vagas posteriores ao crédito da mesma empresa ÷ (valor de todo crédito liberado ÷ 100.000)',
               fomento[1:], vagas_apos_credito=vacancies_after_credit, credito_liberado_reais=credit_total),
        metric('IC-03', 'Jornada SEBRAE, Banco do Povo e PAT', journey, 'empresas',
               'CNPJs com orientação, liberação de crédito e abertura de vaga, em ordem estrita de datas', fomento),
        metric('IC-04', 'Empresas atendidas por mais de um setor de fomento',
               percent(totals['fomento_multi'], totals['fomento_atendidas']), '%',
               'CNPJs atendidos em 2 ou mais setores de fomento ÷ CNPJs atendidos nesses setores × 100', fomento,
               numerador=totals['fomento_multi'], denominador=totals['fomento_atendidas']),
        metric('IC-05', 'Empresas financiadas com vagas posteriores', credit_vacancies, 'empresas',
               'CNPJs com liberação de crédito anterior à abertura de vaga', fomento[1:]),
        metric('IC-06', 'Empresas atendidas em dois ou mais setores', totals['multissetoriais'] if totals['atendidas'] else None,
               'empresas', 'CNPJs atendidos em pelo menos dois dos quatro setores', all_sectors),
        metric('IC-07', 'Empresas atendidas em três ou mais setores', totals['tres_setores'] if totals['atendidas'] else None,
               'empresas', 'CNPJs atendidos em pelo menos três dos quatro setores', all_sectors),
        metric('IC-08', 'Empresas orientadas que receberam crédito', oriented_credit, 'empresas',
               'CNPJs com orientação do SEBRAE anterior à data de liberação', fomento[:2]),
    ]


def company_relationships(start, end, *, limit=30):
    groups, _, _, _ = cross_groups(start, end)
    # A subconsulta agrupa a base de eventos apenas uma vez e elimina repetições por empresa.
    rows = list(groups.filter(setores__gte=2).order_by('-atendimentos', 'empresa_id')
                .values('empresa_id', 'setores', 'atendimentos')[:limit])
    companies = Empresa.objects.in_bulk(row['empresa_id'] for row in rows)
    return [{'empresa': companies[row['empresa_id']].razao_social,
             'setores': row['setores'], 'atendimentos': row['atendimentos']} for row in rows]


def cross_timeline(start, end):
    groups = (
        (attendance_records().filter(setor__codigo__in=SECTORS), 'data_atendimento', 'empresas_atendidas', Count('empresa', distinct=True)),
        (attendance_records().filter(CREDIT), 'data_liberacao', 'empresas_financiadas', Count('empresa', distinct=True)),
        (attendance_records().filter(VACANCY), 'data_abertura_vaga', 'vagas_captadas', Sum('vagas')),
    )
    months = {}
    for queryset, field, label, aggregate in groups:
        data = (queryset.filter(**{f'{field}__range': (start, end)})
                .annotate(mes=TruncMonth(field)).values('mes').annotate(valor=aggregate).order_by('mes'))
        for row in data:
            month = row['mes'].strftime('%Y-%m')
            months.setdefault(month, {'mes': month, 'empresas_atendidas': None,
                                      'empresas_financiadas': None, 'vagas_captadas': None})[label] = row['valor']
    return [months[month] for month in sorted(months)]
