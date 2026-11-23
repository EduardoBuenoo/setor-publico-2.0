from datetime import date

from django.conf import settings
from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncMonth
from django.utils.timezone import localdate
from rest_framework import serializers

from .models import Atividade, Atendimento, Indicador


class ReportFilters(serializers.Serializer):
    inicio = serializers.DateField(required=False)
    fim = serializers.DateField(required=False)
    setor = serializers.IntegerField(min_value=1, required=False)
    indicador = serializers.IntegerField(min_value=1, required=False)
    tipo = serializers.ChoiceField(choices=Indicador.TIPOS, required=False)

    def validate(self, attrs):
        today = localdate()
        end = attrs.setdefault('fim', today)
        start = attrs.setdefault('inicio', date(end.year, 1, 1))
        if start > end or end > today:
            raise serializers.ValidationError('Selecione um período em ordem e sem datas futuras.')
        if (end - start).days > 366 * 5:
            raise serializers.ValidationError('Selecione um intervalo de até cinco anos.')
        return attrs


def indicators_for(user):
    queryset = Indicador.objects.all()
    if not settings.SIGDEI_SHOW_DEMO_DATA:
        queryset = queryset.exclude(nome__startswith='[DEMO]')
    if user.nivel_acesso == 'Administrador':
        return queryset
    if user.id_setor_id is None:
        return queryset.none()
    return queryset.filter(id_setor_id=user.id_setor_id)


def filter_indicators(queryset, filters):
    for parameter, field in [('setor', 'id_setor_id'), ('indicador', 'pk'), ('tipo', 'tipo_dado')]:
        if parameter in filters:
            queryset = queryset.filter(**{field: filters[parameter]})
    return queryset


def period_payload(start, end):
    return {'inicio': start.isoformat(), 'fim': end.isoformat()}


def indicator_value(kind, row):
    if not row:
        return None
    if kind == Indicador.QUANTIDADE:
        return row['soma']
    if kind in (Indicador.TEMPO, Indicador.PORCENTAGEM):
        return round(row['media'], 2)
    return None


def indicator_dashboard(user, filters):
    start, end = filters['inicio'], filters['fim']
    catalog = filter_indicators(indicators_for(user), filters)
    records = Atividade.objects.filter(id_indicador__in=catalog, data_cadastro__range=(start, end))
    aggregates = {'soma': Sum('valor'), 'media': Avg('valor'), 'lancamentos': Count('pk')}
    totals = {row['id_indicador_id']: row for row in records.values('id_indicador_id').annotate(**aggregates)}
    series = {}
    for row in (records.annotate(mes=TruncMonth('data_cadastro')).values('id_indicador_id', 'mes')
                .annotate(**aggregates).order_by('mes')):
        series.setdefault(row['id_indicador_id'], []).append(row)

    indicators = []
    sectors = {}
    for item in catalog.select_related('id_setor').order_by('nome', 'pk'):
        sector = item.id_setor.nome if item.id_setor else 'Sem setor'
        group = sectors.setdefault(item.id_setor_id, {'id': item.id_setor_id, 'nome': sector, 'total': 0})
        group['total'] += 1
        total = totals.get(item.pk)
        value = indicator_value(item.tipo_dado, total)
        target_met = None
        if value is not None and item.meta is not None:
            target_met = value <= item.meta if item.criterio_meta == 'maxima' else value >= item.meta
        indicators.append({
            'id': item.pk, 'nome': item.nome, 'setor': sector, 'tipo': item.tipo_dado,
            'unidade': item.unidade, 'meta': item.meta, 'criterio_meta': item.criterio_meta, 'fonte': item.fonte,
            'situacao': item.situacao, 'valor': value,
            'meta_alcancada': target_met,
            'lancamentos': total['lancamentos'] if total else 0,
            'serie': [{'mes': row['mes'].strftime('%Y-%m'), 'valor': indicator_value(item.tipo_dado, row),
                       'lancamentos': row['lancamentos']} for row in series.get(item.pk, [])],
        })

    attendance = attendance_for(user, filters.get('setor'))
    companies = attendance.filter(data_atendimento__range=(start, end)).aggregate(
        empresas=Count('empresa', distinct=True), atendimentos=Count('pk'),
    )
    vacancies = attendance.filter(tipo=Atendimento.VAGA, setor__codigo='PAT',
                                  data_abertura_vaga__range=(start, end)).aggregate(total=Sum('vagas'))
    return {'periodo': period_payload(start, end), 'total_indicadores': len(indicators),
            'setores': list(sectors.values()), 'indicadores': indicators,
            **companies, 'vagas_captadas': vacancies['total']}


def attendance_records():
    records = Atendimento.objects.all()
    if not settings.SIGDEI_SHOW_DEMO_DATA:
        records = records.exclude(empresa__razao_social__startswith='[DEMO]')
    return records


def attendance_for(user, sector_id=None):
    attendance = attendance_records()
    if user.nivel_acesso != 'Administrador':
        attendance = attendance.filter(setor_id=user.id_setor_id) if user.id_setor_id else attendance.none()
    if sector_id is not None:
        attendance = attendance.filter(setor_id=sector_id)
    return attendance
