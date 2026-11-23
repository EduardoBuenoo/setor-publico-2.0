"""Endpoints autenticados do assistente e das consultas estratégicas."""

import logging
import threading

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdministradorOuGestor, HasStrategicView, CanUseAssistant
from django.conf import settings
from rest_framework import serializers

from sector.cross_indicators import company_relationships, cross_snapshot, cross_timeline
from sector.reporting import ReportFilters, period_payload
from .assistant import answer, provider_available
from . import documents


logger = logging.getLogger(__name__)
query_lock = threading.Lock()
loaded_index = None
loaded_manifest = None


def get_index():
    global loaded_index, loaded_manifest
    manifest = (documents.INDEX_DIR / "manifest.json").read_bytes()
    if loaded_index is None or loaded_manifest != manifest:
        loaded_index = documents.load_index()
        loaded_manifest = manifest
    return loaded_index


class AssistantQuestionInput(ReportFilters):
    pergunta = serializers.CharField(max_length=2000)


class AssistantStatusView(APIView):
    permission_classes = [IsAuthenticated, CanUseAssistant]

    def get(self, request):
        enabled = provider_available()
        return Response({'modo': settings.SIGDEI_AI_PROVIDER if enabled else 'deterministico',
                         'mensagem': 'Consultas estruturadas disponíveis.',
                         'classificador_configurado': enabled})


class AssistantQuestionView(APIView):
    permission_classes = [IsAuthenticated, CanUseAssistant]
    throttle_scope = 'assistente'
    cross_only = False

    def post(self, request):
        form = AssistantQuestionInput(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        return Response(answer(request.user, data['pergunta'], data['inicio'], data['fim'],
                               strategic=HasStrategicView().has_permission(request, self),
                               cross_only=self.cross_only))


class CrossIndicatorsView(APIView):
    permission_classes = [IsAuthenticated, HasStrategicView]

    def get(self, request):
        filters = ReportFilters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        start, end = filters.validated_data['inicio'], filters.validated_data['fim']
        result = {'periodo': period_payload(start, end), 'indicadores': cross_snapshot(start, end)}
        if request.query_params.get('resumo') != '1':
            result.update(serie=cross_timeline(start, end), empresas=company_relationships(start, end))
        return Response(result)


class CrossQuestionView(AssistantQuestionView):
    permission_classes = [IsAuthenticated, HasStrategicView]
    cross_only = True


class DocumentStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdministradorOuGestor]

    def get(self, request):
        ready, message, count = documents.index_status()
        return Response({"pronto": ready, "mensagem": message, "arquivos": count})


class DocumentQuestionView(APIView):
    permission_classes = [IsAuthenticated, IsAdministradorOuGestor]
    throttle_scope = 'assistente'

    def post(self, request):
        question = request.data.get("pergunta") if isinstance(request.data, dict) else None
        if not isinstance(question, str) or not question.strip() or len(question) > documents.MAX_QUESTION_LENGTH:
            return Response({"erro": "Informe uma pergunta de até 2000 caracteres."}, status=400)

        ready, message, _ = documents.index_status()
        if not ready:
            return Response({"erro": message}, status=409)

        try:
            with query_lock:
                result = documents.answer(get_index(), question)
            return Response(result)
        except Exception:
            logger.exception("Falha ao consultar o assistente documental")
            return Response({"erro": "O modelo local não respondeu. Confira se o Ollama está em execução."}, status=503)
