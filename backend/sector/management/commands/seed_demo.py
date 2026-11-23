"""Dados sintéticos de setembro e outubro para testar o SIGDEI local."""

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sector.models import Atividade, Indicador, Sector
from users.models import Users


INDICATORS = {
    "SEBRAE Aqui": [
        ("Atendimentos empresariais", 24, 30),
        ("Oficinas realizadas", 4, 5),
    ],
    "PAT": [
        ("Vagas captadas", 21, 23),
        ("Encaminhamentos realizados", 18, 20),
    ],
    "Banco do Povo": [
        ("Operações de crédito liberadas", 7, 9),
        ("Crédito liberado em reais", 42000, 51000),
    ],
    "PROCON": [
        ("Reclamações registradas", 10, 9),
        ("Casos resolvidos", 8, 8),
    ],
}


class Command(BaseCommand):
    help = "Insere dados fictícios identificados por [DEMO], sem alterar registros existentes."

    def handle(self, *args, **options):
        if not settings.SIGDEI_SHOW_DEMO_DATA:
            raise CommandError('Habilite SIGDEI_SHOW_DEMO_DATA=1 somente no ambiente de demonstração.')
        if Indicador.objects.filter(nome__startswith="[DEMO]").exists():
            self.stdout.write("Dados [DEMO] já existem; nenhuma duplicação foi feita.")
            return
        admin = Users.objects.filter(nivel_acesso="Administrador").order_by("id_usuario").first()
        if admin is None:
            raise CommandError("Crie o Administrador inicial antes de inserir dados de demonstração.")

        with transaction.atomic():
            indicator_count = 0
            activity_count = 0
            for sector_name, specs in INDICATORS.items():
                code = {'SEBRAE Aqui': 'SEBRAE', 'Banco do Povo': 'BP',
                        'PAT': 'PAT', 'PROCON': 'PROCON'}[sector_name]
                sector = Sector.objects.filter(codigo=code).first()
                if sector is None:
                    raise CommandError('Execute bootstrap_setores antes de carregar a demonstração.')
                for label, september, october in specs:
                    indicator = Indicador.objects.create(
                        id_setor=sector, nome=f"[DEMO] {label}", tipo_dado=Indicador.QUANTIDADE, unidade="registros"
                    )
                    indicator_count += 1
                    for month, total in ((9, september), (10, october)):
                        first = total // 2
                        for day, value in ((15, first), (24, total - first)):
                            Atividade.objects.create(
                                id_indicador=indicator,
                                id_usuario=admin,
                                valor=Decimal(value),
                                data_cadastro=date(2026, month, day),
                            )
                            activity_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Criados {indicator_count} indicadores e {activity_count} lançamentos [DEMO]."
        ))
