from django.utils.timezone import localdate
from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import Sector, Indicador, Atividade, Empresa, Atendimento, HistoricoIndicador
from .cnpj import normalize_cnpj, validate_cnpj


class SectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sector
        fields = '__all__'


def validate_number(value, kind):
    if value is None:
        return
    if value < 0:
        raise serializers.ValidationError('Informe um valor maior ou igual a zero.')
    if kind == Indicador.PORCENTAGEM and value > 100:
        raise serializers.ValidationError('Informe uma porcentagem entre 0 e 100.')


class IndicadorSerializer(serializers.ModelSerializer):
    tipo_dado = serializers.ChoiceField(choices=Indicador.TIPOS)

    class Meta:
        model = Indicador
        fields = ['id_indicador', 'id_setor', 'nome', 'tipo_dado', 'descricao',
                  'unidade', 'periodicidade', 'meta', 'criterio_meta', 'fonte', 'situacao']
        extra_kwargs = {field: {'required': True, 'allow_blank': False}
                        for field in ('descricao', 'unidade', 'fonte', 'periodicidade')}

    def validate(self, attrs):
        instance = self.instance
        user = self.context['request'].user
        sector = attrs.get('id_setor', instance.id_setor if instance else None)
        if user.nivel_acesso != 'Administrador':
            sector = user.id_setor
            if 'id_setor' in attrs and attrs['id_setor'] != sector:
                raise serializers.ValidationError({'id_setor': 'Selecione somente o seu setor.'})
            attrs['id_setor'] = sector
        if not sector:
            raise serializers.ValidationError({'id_setor': 'Informe o setor responsável.'})
        name = attrs.get('nome', instance.nome if instance else '')
        if Indicador.objects.filter(id_setor=sector, nome__iexact=name).exclude(pk=getattr(instance, 'pk', None)).exists():
            if not instance or instance.nome != name or instance.id_setor_id != sector.pk:
                raise serializers.ValidationError({'nome': 'Já existe um indicador com este nome no setor.'})
        kind = attrs.get('tipo_dado', instance.tipo_dado if instance else None)
        if instance and instance.atividade_set.exists():
            for field in ('id_setor', 'tipo_dado', 'unidade', 'periodicidade'):
                if field in attrs and attrs[field] != getattr(instance, field):
                    # Permite documentar a unidade que faltava em um cadastro legado.
                    if field == 'unidade' and not instance.unidade:
                        continue
                    raise serializers.ValidationError({field: 'Há lançamentos vinculados a este indicador.'})
        if not instance or 'unidade' in attrs or 'tipo_dado' in attrs:
            unit = attrs.get('unidade', instance.unidade if instance else '')
            if kind == Indicador.PORCENTAGEM and unit != '%':
                raise serializers.ValidationError({'unidade': 'Use % para indicadores de porcentagem.'})
            if kind == Indicador.TEMPO and unit.casefold() not in ('segundos', 'minutos', 'horas', 'dias'):
                raise serializers.ValidationError({'unidade': 'Use segundos, minutos, horas ou dias.'})
        try:
            validate_number(attrs.get('meta', instance.meta if instance else None), kind)
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({'meta': exc.detail}) from exc
        return attrs


class AtividadeSerializer(serializers.ModelSerializer):
    periodo_referencia = serializers.DateField(source='data_cadastro', required=False)

    class Meta:
        model = Atividade
        fields = ['id_atividade', 'id_indicador', 'id_usuario', 'valor', 'data_cadastro',
                  'periodo_referencia', 'legado']
        read_only_fields = ['id_usuario', 'legado']
        validators = []  # A unicidade usa a referência normalizada em validate().
        extra_kwargs = {'data_cadastro': {'required': False}, 'id_indicador': {'allow_null': False}}

    def validate(self, attrs):
        instance = self.instance
        indicador = attrs.get('id_indicador', instance.id_indicador if instance else None)
        user = self.context['request'].user
        if not indicador or not indicador.id_setor_id:
            raise serializers.ValidationError({'id_indicador': 'Selecione um indicador vinculado a um setor.'})
        if user.nivel_acesso != 'Administrador' and indicador.id_setor_id != user.id_setor_id:
            raise serializers.ValidationError({'id_indicador': 'Indicador fora do seu setor.'})
        if instance and instance.id_indicador_id != indicador.pk:
            raise serializers.ValidationError({'id_indicador': 'O indicador do lançamento é permanente.'})
        if not instance and indicador.situacao != 'ativo':
            raise serializers.ValidationError({'id_indicador': 'O indicador está inativo.'})
        if indicador.tipo_dado not in dict(Indicador.TIPOS):
            raise serializers.ValidationError({'id_indicador': 'O tipo legado precisa de revisão administrativa.'})
        if 'periodo_referencia' in self.initial_data and 'data_cadastro' in self.initial_data:
            legacy_date = self.fields['data_cadastro'].run_validation(self.initial_data['data_cadastro'])
            if legacy_date != attrs.get('data_cadastro'):
                raise serializers.ValidationError({'periodo_referencia': 'Informe uma única data de referência.'})
        raw_date = attrs.get('data_cadastro', instance.data_cadastro if instance else None)
        if not raw_date or raw_date > localdate():
            raise serializers.ValidationError({'periodo_referencia': 'Informe uma referência válida, sem data futura.'})
        if not instance or raw_date != instance.data_cadastro:
            period = indicador.periodicidade
            if period == 'mensal':
                raw_date = raw_date.replace(day=1)
            elif period == 'trimestral':
                raw_date = raw_date.replace(month=(raw_date.month - 1) // 3 * 3 + 1, day=1)
            elif period == 'anual':
                raw_date = raw_date.replace(month=1, day=1)
            if Atividade.objects.filter(id_indicador=indicador, data_cadastro=raw_date).exclude(pk=getattr(instance, 'pk', None)).exists():
                raise serializers.ValidationError({'periodo_referencia': 'Já existe um lançamento para esta referência.'})
            attrs['data_cadastro'] = raw_date
        try:
            validate_number(attrs.get('valor', instance.valor if instance else None), indicador.tipo_dado)
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({'valor': exc.detail}) from exc
        return attrs


class HistoricoIndicadorSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricoIndicador
        fields = ['id', 'autor', 'evento', 'data_hora', 'anterior', 'atual']


class EmpresaSerializer(serializers.ModelSerializer):
    cnpj = serializers.CharField(max_length=32)
    setores_atendidos = serializers.SerializerMethodField()

    class Meta:
        model = Empresa
        fields = ['id', 'cnpj', 'razao_social', 'ramo_atividade', 'bairro', 'setores_atendidos']

    def get_setores_atendidos(self, obj):
        request = self.context.get('request')
        queryset = obj.atendimentos.exclude(setor__codigo='PROCON').exclude(setor__nome__iexact='PROCON')
        if request and request.user.nivel_acesso != 'Administrador':
            queryset = queryset.filter(setor_id=request.user.id_setor_id)
        return sorted(set(queryset.values_list('setor__nome', flat=True)))

    def validate_cnpj(self, value):
        normalized = normalize_cnpj(value)
        try:
            validate_cnpj(normalized)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        if Empresa.objects.filter(cnpj=normalized).exists():
            raise serializers.ValidationError('Esta empresa já está cadastrada.')
        return normalized


class AtendimentoSerializer(serializers.ModelSerializer):
    colaborador = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Atendimento
        fields = ['id', 'empresa', 'setor', 'colaborador', 'data_atendimento',
                  'desfecho', 'tipo', 'valor_credito', 'data_liberacao',
                  'vagas', 'data_abertura_vaga']
        extra_kwargs = {'setor': {'required': False}}

    def validate(self, attrs):
        user = self.context['request'].user
        if user.nivel_acesso != 'Administrador':
            if not user.id_setor_id:
                raise serializers.ValidationError('Seu usuário precisa estar vinculado a um setor.')
            attrs['setor'] = user.id_setor
        elif not (attrs.get('setor') or getattr(self.instance, 'setor_id', None)):
            raise serializers.ValidationError({'setor': 'Informe o setor.'})
        if self.instance:
            for field in ('empresa', 'setor'):
                old = getattr(self.instance, f'{field}_id')
                new = attrs.get(field)
                if new is not None and new.pk != old:
                    raise serializers.ValidationError({field: 'Este vínculo não pode ser alterado.'})
        return attrs
