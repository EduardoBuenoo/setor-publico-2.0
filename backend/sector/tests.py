from datetime import timedelta

import bcrypt
from django.core.cache import cache
from django.test import TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils.timezone import localdate
from rest_framework.test import APITestCase

from users.models import Users
from .models import Atividade, HistoricoIndicador, Indicador, Sector


class IndicatorApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pat = Sector.objects.create(nome='PAT', codigo='PAT')
        cls.other = Sector.objects.create(nome='PROCON', codigo='PROCON')
        cls.manager = Users.objects.create(
            matricula='gestor', nome='Gestor de teste', nivel_acesso='Gestor', id_setor=cls.pat,
            senha_hash=bcrypt.hashpw(b'Valid@Test22', bcrypt.gensalt(rounds=4)).decode(),
        )
        cls.operator = Users.objects.create(matricula='colaborador', nome='Operador',
                                            nivel_acesso='Colaborador', id_setor=cls.pat)
        cls.other_indicator = Indicador.objects.create(nome='Catálogo externo', tipo_dado='quantidade',
                                                       id_setor=cls.other)

    def setUp(self):
        cache.clear()
        self.client.force_authenticate(self.manager)

    def definition(self, **changes):
        return {'nome': 'Resoluções', 'descricao': 'Percentual de registros resolvidos',
                'id_setor': self.pat.pk, 'tipo_dado': 'porcentagem', 'unidade': '%',
                'periodicidade': 'mensal', 'meta': '70', 'fonte': 'Relatório mensal', **changes}

    def create_indicator(self, **changes):
        response = self.client.post('/api/v1/indicadores/', self.definition(**changes), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id_indicador']

    def record(self, indicator, amount, when=None):
        return self.client.post('/api/v1/atividades/',
                                {'id_indicador': indicator, 'valor': amount,
                                 'periodo_referencia': (when or localdate()).isoformat()}, format='json')

    def test_jwt_login_and_private_dashboard(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/v1/dashboard/').status_code, 401)
        response = self.client.post('/api/v1/login/', {'matricula': self.manager.matricula, 'senha': 'Valid@Test22'})
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['access'])
        self.assertEqual(self.client.get('/api/v1/dashboard/').status_code, 200)
        self.assertEqual(self.client.get('/health/').json(), {'status': 'ok'})
        for route in ('projetos', 'tarefas', 'oficios'):
            self.assertEqual(self.client.get(f'/api/v1/{route}/').status_code, 404)

    def test_definition_validation_permissions_and_history(self):
        self.assertEqual(self.client.post('/api/v1/indicadores/', {}, format='json').status_code, 400)
        for changes in ({'meta': 110}, {'id_setor': self.other.pk}, {'unidade': 'horas'}):
            response = self.client.post('/api/v1/indicadores/', self.definition(**changes), format='json')
            self.assertEqual(response.status_code, 400, response.data)
        pk = self.create_indicator()
        self.assertEqual(self.client.post('/api/v1/indicadores/', self.definition(nome='resoluções'), format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/v1/indicadores/{pk}/', {'meta': '80'}, format='json').status_code, 200)
        events = self.client.get(f'/api/v1/indicadores/{pk}/historico/').data['results']
        self.assertEqual([event['evento'] for event in events], ['indicador_editado', 'indicador_criado'])
        self.assertEqual(events[0]['anterior']['meta'], '70.00')
        self.assertEqual(events[0]['atual']['meta'], '80.00')
        self.assertEqual(events[0]['autor'], self.manager.pk)
        self.client.force_authenticate(self.operator)
        self.assertEqual(self.client.patch(f'/api/v1/indicadores/{pk}/', {'meta': '90'}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(f'/api/v1/setores/{self.pat.pk}/').status_code, 403)
        self.assertEqual(self.client.get(f'/api/v1/indicadores/{self.other_indicator.pk}/historico/').status_code, 404)

    def test_period_validation_editing_and_scoped_aggregation(self):
        pk = self.create_indicator()
        today = localdate()
        previous_month = today.replace(day=1) - timedelta(days=1)
        self.assertEqual(self.record(self.other_indicator.pk, 1).status_code, 404)
        self.assertEqual(self.record(pk, None).status_code, 400)
        self.assertEqual(self.record(pk, -1).status_code, 400)
        self.assertEqual(self.record(pk, 101).status_code, 400)
        self.assertEqual(self.record(pk, 10, today + timedelta(days=1)).status_code, 400)
        self.client.force_authenticate(self.operator)
        first = self.record(pk, 0)
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data['periodo_referencia'], today.replace(day=1).isoformat())
        self.assertEqual(self.record(pk, 55).status_code, 400)
        self.assertEqual(self.record(pk, 100, previous_month).status_code, 201)
        detail = '/api/v1/atividades/{}/'.format(first.data['id_atividade'])
        self.assertEqual(self.client.patch(detail, {'valor': 60}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(detail, {'id_indicador': self.other_indicator.pk}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(detail).status_code, 403)
        filters = {'inicio': previous_month.replace(day=1).isoformat(), 'fim': today.isoformat(),
                   'setor': self.pat.pk, 'indicador': pk, 'tipo': 'porcentagem'}
        data = self.client.get('/api/v1/dashboard/', filters).data
        self.assertEqual(data['total_indicadores'], 1)
        self.assertEqual(data['indicadores'][0]['valor'], 80)
        self.assertTrue(data['indicadores'][0]['meta_alcancada'])
        self.assertEqual([point['valor'] for point in data['indicadores'][0]['serie']], [100, 60])
        self.assertIsNone(data['vagas_captadas'])
        self.assertEqual(self.client.get('/api/v1/atividades/', {**filters, 'inicio': today.replace(day=1)}).data['count'], 1)
        self.assertEqual(self.client.get('/api/v1/dashboard/', {'setor': self.other.pk}).data['total_indicadores'], 0)
        self.assertEqual(self.client.get('/api/v1/dashboard/', {'inicio': 'invalid'}).status_code, 400)
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.patch(f'/api/v1/indicadores/{pk}/', {'periodicidade': 'anual'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(detail).status_code, 204)
        self.assertTrue(HistoricoIndicador.objects.filter(evento='lancamento_excluido', indicador_id=pk).exists())

    def test_indicators_of_unassigned_managers_are_hidden(self):
        self.manager.id_setor = None
        self.manager.save(update_fields=['id_setor'])
        Indicador.objects.create(nome='Órfão legado', tipo_dado='quantidade')
        self.assertEqual(self.client.get('/api/v1/indicadores/').data, [])


class LegacyMigrationTests(TransactionTestCase):
    def test_migrates_existing_records_and_preserves_archived_modules(self):
        executor = MigrationExecutor(connection)
        final = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(final))
        old_targets = [('sector', '0004_sector_codigo'), ('users', '0003_users_visao_estrategica'),
                       ('projects', '0002_initial'), ('oficios', '0002_oficios_unique_numero_ano')]
        executor.migrate(old_targets)
        old = executor.loader.project_state(old_targets).apps
        sector = old.get_model('sector', 'Sector').objects.create(nome='Setor legado')
        user = old.get_model('users', 'Users').objects.create(matricula='legado', nome='Legado', id_setor=sector)
        indicators = old.get_model('sector', 'Indicador')
        first = indicators.objects.create(nome='Legado', tipo_dado='Número', id_setor=sector)
        indicators.objects.create(nome='legado', tipo_dado='Quantidade', id_setor=sector)
        for value in (2, 5):
            old.get_model('sector', 'Atividade').objects.create(
                id_indicador=first, id_usuario=user, valor=value, data_cadastro=localdate())
        project = old.get_model('projects', 'Project').objects.create(
            nome='Projeto preservado', data_inicio=localdate(), data_fim=localdate(),
            id_setor=sector, id_responsavel=user, status_tag='Em andamento')
        old.get_model('projects', 'Tarefa').objects.create(
            id_projeto=project, nome_tarefa='Tarefa preservada', data_inicio=localdate(), data_final=localdate())
        old.get_model('oficios', 'Oficios').objects.create(
            numero_sequencial=1, ano=localdate().year, data_oficio=localdate(),
            assunto='Ofício preservado', id_usuario=user, id_setor=sector)

        MigrationExecutor(connection).migrate(final)
        self.assertEqual(Indicador.objects.get(pk=first.pk).tipo_dado, 'quantidade')
        self.assertEqual(Indicador.objects.filter(id_setor_id=sector.pk).count(), 2)
        self.assertEqual(list(Atividade.objects.filter(legado=True).order_by('valor').values_list('valor', flat=True)), [2, 5])
        self.assertEqual(Users.objects.get(pk=user.pk).id_setor_id, sector.pk)
        with connection.cursor() as cursor:
            for table, column, expected in (
                ('arquivo_projetos', 'nome', 'Projeto preservado'),
                ('arquivo_tarefas', 'nome_tarefa', 'Tarefa preservada'),
                ('arquivo_oficios', 'assunto', 'Ofício preservado'),
            ):
                # As tabelas e colunas são constantes do teste, administradas por migração.
                cursor.execute(f'SELECT {column} FROM {table} WHERE {column} = %s', [expected])
                self.assertEqual(cursor.fetchone()[0], expected)
            self.assertTrue({'projetos', 'tarefas', 'oficios'}.isdisjoint(connection.introspection.table_names(cursor)))
