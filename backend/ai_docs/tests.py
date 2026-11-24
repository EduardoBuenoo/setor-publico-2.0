from types import SimpleNamespace
from unittest.mock import patch
from datetime import date

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from sector.models import Sector, Empresa, Atendimento
from sector.cnpj import cnpj_check_digits
from sector.cross_indicators import cross_snapshot
from sector.serializers import EmpresaSerializer
from sector.views import AtendimentoCreateListView
from .views import DocumentQuestionView, DocumentStatusView, CrossIndicatorsView, CrossQuestionView


class DocumentRoutesTest(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def request_as(self, role, question="Quais são os objetivos?"):
        request = self.factory.post("/api/v1/documentos/perguntar/", {"pergunta": question}, format="json")
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True, nivel_acesso=role, pk=1))
        return request

    def test_collaborator_cannot_query_documents(self):
        response = DocumentQuestionView.as_view()(self.request_as("Colaborador"))
        self.assertEqual(response.status_code, 403)

    def test_manager_receives_answer_with_sources(self):
        with (
            patch("ai_docs.views.documents.index_status", return_value=(True, "Índice pronto.", 8)),
            patch("ai_docs.views.get_index", return_value=object()),
            patch("ai_docs.views.documents.answer", return_value={"resposta": "Texto", "fontes": []}),
        ):
            response = DocumentQuestionView.as_view()(self.request_as("Gestor"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["resposta"], "Texto")

    def test_missing_index_is_reported(self):
        with patch("ai_docs.views.documents.index_status", return_value=(False, "Reindexe.", 8)):
            response = DocumentQuestionView.as_view()(self.request_as("Administrador"))
        self.assertEqual(response.status_code, 409)

    def test_status_requires_login(self):
        response = DocumentStatusView.as_view()(self.factory.get("/api/v1/documentos/status/"))
        self.assertEqual(response.status_code, 401)


class CrossIndicatorTest(TestCase):
    def setUp(self):
        self.sebrae = Sector.objects.create(nome='SEBRAE Aqui', codigo='SEBRAE')
        self.bank = Sector.objects.create(nome='Banco do Povo', codigo='BP')
        self.pat = Sector.objects.create(nome='PAT', codigo='PAT')
        self.procon = Sector.objects.create(nome='PROCON', codigo='PROCON')
        from users.models import Users
        self.admin = Users.objects.create(matricula='admin-test', nome='Teste', senha_hash='x',
                                          nivel_acesso='Administrador', visao_estrategica=True)

    def company(self, number):
        base = f'ZZZZZZZZ{number:04d}'
        return Empresa.objects.create(cnpj=base + cnpj_check_digits(base),
                                      razao_social=f'Empresa {number}', ramo_atividade='Serviços', bairro='Centro')

    def attendance(self, company, sector, month, day, kind=Atendimento.OUTRO, credit=None, vacancies=None):
        when = date(2026, month, day)
        return Atendimento.objects.create(
            empresa=company, setor=sector, colaborador=self.admin, data_atendimento=when,
            desfecho='Resolvido', tipo=kind, valor_credito=credit,
            data_liberacao=when if credit else None, vagas=vacancies,
            data_abertura_vaga=when if vacancies else None)

    def test_formulas_use_same_company_and_chronological_order(self):
        first = self.company(1)
        self.attendance(first, self.sebrae, 9, 10, Atendimento.SEBRAE)
        self.attendance(first, self.bank, 9, 20, Atendimento.CREDITO, credit=100000)
        self.attendance(first, self.pat, 10, 5, Atendimento.VAGA, vacancies=3)
        second = self.company(2)
        self.attendance(second, self.bank, 9, 10, Atendimento.CREDITO, credit=100000)
        self.attendance(second, self.sebrae, 9, 20, Atendimento.SEBRAE)
        self.attendance(second, self.pat, 9, 5, Atendimento.VAGA, vacancies=7)
        procon_only = self.company(3)
        self.attendance(procon_only, self.procon, 9, 11)

        results = {item['id']: item for item in cross_snapshot(date(2026, 9, 1), date(2026, 10, 26))}
        self.assertEqual((results['IC-01']['numerador'], results['IC-01']['denominador'], results['IC-01']['valor']), (1, 2, '50.00'))
        self.assertEqual((results['IC-02']['vagas_apos_credito'], results['IC-02']['valor']), (3, '1.50'))
        self.assertEqual(results['IC-03']['valor'], 1)
        self.assertEqual((results['IC-04']['numerador'], results['IC-04']['denominador']), (2, 2))
        self.assertFalse(any('cnpj' in item or 'razao_social' in item for item in results.values()))

    def test_zero_denominators_are_not_reported_as_zero_percent(self):
        results = {item['id']: item for item in cross_snapshot(date(2026, 9, 1), date(2026, 10, 26))}
        self.assertIsNone(results['IC-01']['valor'])
        self.assertIsNone(results['IC-02']['valor'])
        self.assertIsNone(results['IC-04']['valor'])

    def test_invalid_cnpj_is_rejected(self):
        with self.assertRaises(ValidationError):
            Empresa.objects.create(cnpj='ZZZZZZZZ000100', razao_social='Teste',
                                   ramo_atividade='Serviços', bairro='Centro')

    def test_company_lookup_reuses_normalized_cnpj_and_hides_procon_sector(self):
        company = self.company(5)
        self.attendance(company, self.procon, 9, 11)
        self.attendance(company, self.sebrae, 9, 12, Atendimento.SEBRAE)
        data = EmpresaSerializer(company).data
        self.assertEqual(data['setores_atendidos'], ['SEBRAE Aqui'])
        formatted = f"{company.cnpj[:2]}.{company.cnpj[2:5]}.{company.cnpj[5:8]}/{company.cnpj[8:12]}-{company.cnpj[12:]}"
        serializer = EmpresaSerializer(data={
            'cnpj': formatted, 'razao_social': 'Outra', 'ramo_atividade': 'Serviços', 'bairro': 'Centro',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('cnpj', serializer.errors)

    def test_api_registers_formatted_cnpj(self):
        from rest_framework.test import APIClient

        base = 'ZZZZZZZZ0022'
        cnpj = base + cnpj_check_digits(base)
        formatted = f'{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}'
        client = APIClient()
        client.force_authenticate(self.admin)
        data = {'cnpj': formatted, 'razao_social': 'Empresa teste', 'ramo_atividade': 'Serviços', 'bairro': 'Centro'}
        result = client.post('/api/v1/empresas/', data, format='json')
        self.assertEqual(result.status_code, 201, result.data)
        self.assertEqual(result.data['cnpj'], cnpj)
        self.assertEqual(client.get('/api/v1/empresas/', {'cnpj': formatted}).data[0]['id'], result.data['id'])
        self.assertEqual(client.post('/api/v1/empresas/', data, format='json').status_code, 400)

    def test_cross_endpoint_requires_individual_permission(self):
        factory = APIRequestFactory()
        request = factory.get('/api/v1/dashboard/cruzados/?inicio=2026-09-01&fim=2026-10-26')
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True, nivel_acesso='Administrador', visao_estrategica=False))
        self.assertEqual(CrossIndicatorsView.as_view()(request).status_code, 403)
        request = factory.get('/api/v1/dashboard/cruzados/?inicio=2026-09-01&fim=2026-10-26')
        force_authenticate(request, user=self.admin)
        self.assertEqual(CrossIndicatorsView.as_view()(request).status_code, 200)

    def test_attendance_cannot_be_registered_in_another_sector(self):
        company = self.company(4)
        request = APIRequestFactory().post('/api/v1/atendimentos/', {
            'empresa': company.pk, 'setor': self.sebrae.pk,
            'data_atendimento': '2026-10-05', 'desfecho': 'Resolvido',
            'tipo': Atendimento.VAGA, 'vagas': 2, 'data_abertura_vaga': '2026-10-05',
        }, format='json')
        # A autenticação usa um usuário real para persistir a autoria.
        self.admin.nivel_acesso = 'Gestor'
        self.admin.id_setor = self.pat
        self.admin.save(update_fields=['nivel_acesso', 'id_setor'])
        force_authenticate(request, user=self.admin)
        response = AtendimentoCreateListView.as_view()(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Atendimento.objects.get(pk=response.data['id']).setor_id, self.pat.pk)

    def test_chat_uses_computed_cross_values_without_provider(self):
        request = APIRequestFactory().post('/api/v1/dashboard/cruzados/perguntar/', {
            'pergunta': 'Qual o IC-01?', 'inicio': '2026-09-01', 'fim': '2026-10-26',
        }, format='json')
        force_authenticate(request, user=self.admin)
        with patch('ai_docs.assistant.urlopen') as model:
            response = CrossQuestionView.as_view()(request)
        model.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertIn('Dados insuficientes', response.data['resposta'])
        self.assertEqual(response.data['modo'], 'deterministico')


class StructuredAssistantTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        from django.utils.timezone import localdate
        from sector.models import Atividade, Indicador
        from users.models import Users

        cache.clear()
        self.date = localdate()
        self.pat = Sector.objects.create(nome='PAT', codigo='PAT')
        self.sebrae = Sector.objects.create(nome='SEBRAE Aqui', codigo='SEBRAE')
        self.manager = Users.objects.create(matricula='manager', nome='Gestor', senha_hash='x',
                                            nivel_acesso='Gestor', id_setor=self.pat)
        for sector, name, value in ((self.pat, 'Vagas registradas', 13), (self.sebrae, 'Orientações', 99)):
            indicator = Indicador.objects.create(nome=name, tipo_dado='quantidade', unidade='registros', id_setor=sector)
            Atividade.objects.create(id_indicador=indicator, data_cadastro=self.date, valor=value)
        base = 'ZZZZZZZZ0101'
        company = Empresa.objects.create(cnpj=base + cnpj_check_digits(base), razao_social='Empresa A',
                                         ramo_atividade='Serviços', bairro='Centro')
        Atendimento.objects.create(empresa=company, setor=self.sebrae, colaborador=self.manager,
                                   data_atendimento=self.date, desfecho='Orientado', tipo=Atendimento.SEBRAE)

    def ask(self, question):
        from .views import AssistantQuestionView

        request = APIRequestFactory().post('/api/v1/assistente/perguntar/',
                                           {'pergunta': question, 'inicio': self.date.isoformat(),
                                            'fim': self.date.isoformat()}, format='json')
        force_authenticate(request, user=self.manager)
        return AssistantQuestionView.as_view()(request)

    def test_database_answers_respect_sector_without_provider(self):
        with patch('ai_docs.assistant.urlopen') as provider:
            response = self.ask('Qual foi a evolução dos indicadores do departamento?')
        provider.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertIn('13', response.data['resposta'])
        self.assertNotIn('Orientações', response.data['resposta'])
        self.assertIn('Lançamentos', response.data['fontes'][0]['rotulo'])
        self.assertIn('não tem acesso', self.ask('Quantas empresas foram atendidas pelo SEBRAE-Aqui neste ano?').data['resposta'])
        self.assertIn('permissão', self.ask('Quantas empresas financiadas possuem vagas no PAT?').data['resposta'])

    def test_admin_question_resolves_relative_period(self):
        self.manager.nivel_acesso = 'Administrador'
        result = self.ask('Quantas empresas foram atendidas pelo SEBRAE-Aqui neste ano?').data
        self.assertIn('1 empresa ', result['resposta'])
        self.assertEqual(result['periodo']['inicio'], self.date.replace(month=1, day=1).isoformat())

    def test_invalid_provider_intent_is_discarded(self):
        from io import BytesIO
        import json
        from django.test import override_settings

        external = {'choices': [{'message': {'content': json.dumps({'intencao': 'consulta_desconhecida'})}}]}
        with (override_settings(SIGDEI_AI_PROVIDER='openai', SIGDEI_AI_API_KEY='chave-falsa-teste'),
              patch('ai_docs.assistant.urlopen', return_value=BytesIO(json.dumps(external).encode())) as model):
            response = self.ask('Como foi a movimentação? ZM.123.EBC/0001-09 operacao@exemplo.com')
        self.assertEqual(response.data['fontes'], [])
        self.assertIn('consulta suportada', response.data['resposta'])
        payload = json.loads(model.call_args.args[0].data)
        self.assertNotIn('Empresa A', str(payload))
        self.assertNotIn('ZM.123.EBC/0001-09', str(payload))
        self.assertNotIn('operacao@exemplo.com', str(payload))

    def test_ollama_classification_uses_authorized_query(self):
        from io import BytesIO
        import json
        from django.test import override_settings

        reply = {'message': {'content': json.dumps({'intencao': 'evolucao'})}}
        with (override_settings(SIGDEI_AI_PROVIDER='ollama'),
              patch('ai_docs.assistant.urlopen', return_value=BytesIO(json.dumps(reply).encode()))):
            response = self.ask('Como foi a movimentação?')
        self.assertEqual(response.data['modo'], 'classificador_ollama')
        self.assertIn('Vagas registradas', response.data['resposta'])
        self.assertNotIn('Orientações', response.data['resposta'])
