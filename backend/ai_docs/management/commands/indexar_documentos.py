from django.core.management.base import BaseCommand, CommandError

from ai_docs.documents import build_index


class Command(BaseCommand):
    help = 'Reconstrói o índice documental local. Requer as dependências opcionais e Ollama.'

    def handle(self, *args, **options):
        try:
            count = build_index()
        except ImportError as exc:
            raise CommandError('Instale backend/requirements-documentos.txt para indexar.') from exc
        except (RuntimeError, OSError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f'Indexados {count} arquivo(s).'))
