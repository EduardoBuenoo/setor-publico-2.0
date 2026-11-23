"""Separa a atualização de registros legados das alterações de esquema."""

from django.db import migrations


def preserve_existing_records(apps, schema_editor):
    alias = schema_editor.connection.alias
    indicators = apps.get_model('sector', 'Indicador').objects.using(alias)
    activities = apps.get_model('sector', 'Atividade').objects.using(alias)
    indicators.update(legado=True)
    activities.update(legado=True)
    for old, new in [
        ('Número', 'quantidade'), ('Quantidade', 'quantidade'),
        ('Horários', 'tempo'), ('Tempo', 'tempo'), ('Porcentagem', 'porcentagem'),
    ]:
        indicators.filter(tipo_dado__iexact=old).update(tipo_dado=new)


class Migration(migrations.Migration):
    dependencies = [('sector', '0005_catalogo_historico')]
    operations = [migrations.RunPython(preserve_existing_records, migrations.RunPython.noop)]
