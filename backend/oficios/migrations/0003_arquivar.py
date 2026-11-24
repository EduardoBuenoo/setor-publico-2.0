"""Retira os modelos da aplicação e preserva as tabelas para recuperação."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('oficios', '0002_oficios_unique_numero_ano')]
    operations = [
        migrations.AlterField('oficios', 'id_usuario', models.ForeignKey(to='users.users', on_delete=django.db.models.deletion.CASCADE, db_column='id_usuario', null=True, blank=True, db_constraint=False)),
        migrations.AlterField('oficios', 'id_setor', models.ForeignKey(to='sector.sector', on_delete=django.db.models.deletion.CASCADE, db_column='id_setor', null=True, blank=True, db_constraint=False)),
        migrations.AlterModelTable('oficios', 'arquivo_oficios'),
        migrations.SeparateDatabaseAndState(state_operations=[migrations.DeleteModel('oficios')]),
    ]
