import re

from django.core.management.base import BaseCommand
from django.db import transaction

from sector.cross_indicators import SECTORS
from sector.models import Sector


class Command(BaseCommand):
    help = 'Garante os códigos oficiais dos quatro setores, preservando os IDs existentes.'

    @transaction.atomic
    def handle(self, *args, **options):
        existing = list(Sector.objects.select_for_update().order_by('pk'))

        def normalize(label):
            return re.sub(r'[\s-]+', '', label.casefold())

        for code, name in SECTORS.items():
            if any(sector.codigo == code for sector in existing):
                continue
            matches = [sector for sector in existing
                       if not sector.codigo and normalize(sector.nome) == normalize(name)]
            if len(matches) > 1:
                self.stderr.write(self.style.WARNING(
                    f'{name} tem cadastros legados ambíguos. Verifique os vínculos e atribua o código {code} no setor correto.',
                ))
            elif matches:
                sector = matches[0]
                sector.codigo = code
                sector.save(update_fields=['codigo'])
            else:
                Sector.objects.get_or_create(codigo=code, defaults={'nome': name})
        self.stdout.write(self.style.SUCCESS('Verificação dos setores concluída.'))
