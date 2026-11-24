from collections.abc import Mapping

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .cnpj import validate_cnpj
from .models import Atendimento, Atividade, Empresa, HistoricoIndicador, Sector
from .reporting import ReportFilters, attendance_for, filter_indicators, indicator_dashboard, indicators_for
from .serializers import (AtendimentoSerializer, AtividadeSerializer, EmpresaSerializer,
                          HistoricoIndicadorSerializer, IndicadorSerializer, SectorSerializer)


class SectorAccess(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS or request.user.nivel_acesso == 'Administrador'


class IndicatorAccess(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS or request.user.nivel_acesso in ('Administrador', 'Gestor')


class RecordAccess(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == 'DELETE':
            return request.user.nivel_acesso in ('Administrador', 'Gestor')
        return request.method in permissions.SAFE_METHODS or request.user.nivel_acesso in (
            'Administrador', 'Gestor', 'Colaborador', 'Usuário',
        )


class SectorCreateListView(generics.ListCreateAPIView):
    queryset = Sector.objects.order_by('nome')
    serializer_class = SectorSerializer
    permission_classes = [permissions.IsAuthenticated, SectorAccess]


class SectorRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Sector.objects.all()
    serializer_class = SectorSerializer
    permission_classes = [permissions.IsAuthenticated, SectorAccess]

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as exc:
            raise ValidationError('O setor possui registros vinculados.') from exc


class IndicatorScope:
    def get_queryset(self):
        return indicators_for(self.request.user).order_by('nome', 'pk')

    def snapshot(self, instance):
        return dict(self.get_serializer(instance).data)

    def log(self, instance, event, before=None):
        HistoricoIndicador.objects.create(indicador=instance, autor=self.request.user,
                                          evento=event, anterior=before, atual=self.snapshot(instance))


class IndicadorCreateListView(IndicatorScope, generics.ListCreateAPIView):
    serializer_class = IndicadorSerializer
    permission_classes = [permissions.IsAuthenticated, IndicatorAccess]

    def filter_queryset(self, queryset):
        filters = ReportFilters(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return filter_indicators(queryset, filters.validated_data)

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                instance = serializer.save()
                self.log(instance, 'indicador_criado')
        except IntegrityError as exc:
            raise ValidationError({'nome': 'Já existe um indicador com este nome no setor.'}) from exc


class IndicadorDetailView(IndicatorScope, generics.RetrieveUpdateAPIView):
    serializer_class = IndicadorSerializer
    permission_classes = [permissions.IsAuthenticated, IndicatorAccess]

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_for_update() if self.request.method in ('PUT', 'PATCH') else queryset

    def perform_update(self, serializer):
        before = self.snapshot(serializer.instance)
        try:
            with transaction.atomic():
                instance = serializer.save()
                if before != self.snapshot(instance):
                    self.log(instance, 'indicador_editado', before)
        except IntegrityError as exc:
            raise ValidationError({'nome': 'Já existe um indicador com este nome no setor.'}) from exc


class HistoryPagination(PageNumberPagination):
    page_size = 30


class IndicadorHistoryView(generics.ListAPIView):
    serializer_class = HistoricoIndicadorSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = HistoryPagination

    def get_queryset(self):
        indicator = generics.get_object_or_404(indicators_for(self.request.user), pk=self.kwargs['pk'])
        return indicator.historico.all()


class ActivityScope:
    serializer_class = AtividadeSerializer
    permission_classes = [permissions.IsAuthenticated, RecordAccess]

    def get_queryset(self):
        return Atividade.objects.filter(id_indicador__in=indicators_for(self.request.user)).select_related(
            'id_indicador',
        ).order_by('-data_cadastro', '-pk')

    def snapshot(self, instance):
        return dict(self.get_serializer(instance).data) if instance else None

    def log(self, instance, event, before=None, after=None):
        HistoricoIndicador.objects.create(indicador_id=instance.id_indicador_id, autor=self.request.user,
                                          evento=event, anterior=before, atual=after)

    def save_measurement(self, serializer, **kwargs):
        try:
            with transaction.atomic():
                return serializer.save(**kwargs)
        except IntegrityError as exc:
            raise ValidationError({'periodo_referencia': 'Já existe uma medição nesta referência.'}) from exc

    def lock_indicator(self, pk):
        return generics.get_object_or_404(indicators_for(self.request.user).select_for_update(), pk=pk)


class AtividadeCreateListView(ActivityScope, generics.ListCreateAPIView):
    pagination_class = HistoryPagination

    def filter_queryset(self, queryset):
        filters = ReportFilters(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        data = filters.validated_data
        catalog = filter_indicators(indicators_for(self.request.user), data)
        queryset = queryset.filter(id_indicador__in=catalog)
        if 'inicio' in self.request.query_params or 'fim' in self.request.query_params:
            queryset = queryset.filter(data_cadastro__range=(data['inicio'], data['fim']))
        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if not isinstance(request.data, Mapping):
            raise ValidationError('Envie os dados de uma medição.')
        field = self.get_serializer().fields['id_indicador']
        try:
            indicator = field.run_validation(request.data.get('id_indicador'))
        except ValidationError as exc:
            raise ValidationError({'id_indicador': exc.detail}) from exc
        self.lock_indicator(indicator.pk)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = self.save_measurement(serializer, id_usuario=self.request.user)
            self.log(instance, 'lancamento_criado', after=self.snapshot(instance))


class AtividadeRetrieveUpdateDestroyView(ActivityScope, generics.RetrieveUpdateDestroyAPIView):
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        self.lock_indicator(self.get_object().id_indicador_id)
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        self.lock_indicator(self.get_object().id_indicador_id)
        return super().destroy(request, *args, **kwargs)

    def perform_update(self, serializer):
        before = self.snapshot(serializer.instance)
        instance = self.save_measurement(serializer)
        if before != self.snapshot(instance):
            self.log(instance, 'lancamento_editado', before=before, after=self.snapshot(instance))

    def perform_destroy(self, instance):
        self.log(instance, 'lancamento_excluido', before=self.snapshot(instance))
        instance.delete()


class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        filters = ReportFilters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        return Response(indicator_dashboard(request.user, filters.validated_data))


class EmpresaCreateListView(generics.ListCreateAPIView):
    serializer_class = EmpresaSerializer
    permission_classes = [permissions.IsAuthenticated, RecordAccess]

    def get_queryset(self):
        cnpj = self.request.query_params.get('cnpj')
        if not cnpj:
            return Empresa.objects.none()
        try:
            companies = Empresa.objects.filter(cnpj=validate_cnpj(cnpj))
            if not settings.SIGDEI_SHOW_DEMO_DATA:
                companies = companies.exclude(razao_social__startswith='[DEMO]')
            return companies
        except DjangoValidationError as exc:
            raise ValidationError({'cnpj': exc.messages}) from exc

    def perform_create(self, serializer):
        try:
            serializer.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict) from exc
        except IntegrityError as exc:
            raise ValidationError({'cnpj': 'Esta empresa já está cadastrada.'}) from exc


class AtendimentoCreateListView(generics.ListCreateAPIView):
    serializer_class = AtendimentoSerializer
    permission_classes = [permissions.IsAuthenticated, RecordAccess]

    def get_queryset(self):
        return attendance_for(self.request.user).order_by('-data_atendimento', '-pk')

    def perform_create(self, serializer):
        try:
            serializer.save(colaborador=self.request.user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages) from exc
