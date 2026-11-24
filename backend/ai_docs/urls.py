from django.urls import path

from .views import (AssistantQuestionView, AssistantStatusView, CrossIndicatorsView,
                    CrossQuestionView, DocumentQuestionView, DocumentStatusView)

urlpatterns = [
    path('assistente/status/', AssistantStatusView.as_view(), name='assistente-status'),
    path('assistente/perguntar/', AssistantQuestionView.as_view(), name='assistente-perguntar'),
    path('dashboard/cruzados/', CrossIndicatorsView.as_view(), name='dashboard-cruzados'),
    path('dashboard/cruzados/perguntar/', CrossQuestionView.as_view(), name='dashboard-cruzados-perguntar'),
    path('dashboard/perguntar/', AssistantQuestionView.as_view(), name='dashboard-perguntar'),
    path('analise-ia/status/', AssistantStatusView.as_view(), name='analise-ia-status'),
    path('analise-ia/perguntar/', AssistantQuestionView.as_view(), name='analise-ia-perguntar'),
    path('documentos/status/', DocumentStatusView.as_view(), name='documentos-status'),
    path('documentos/perguntar/', DocumentQuestionView.as_view(), name='documentos-perguntar'),
]
