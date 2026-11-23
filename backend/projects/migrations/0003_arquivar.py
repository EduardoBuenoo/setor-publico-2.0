"""Retira os modelos da aplicação e preserva as tabelas para recuperação."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('projects', '0002_initial')]
    operations = [
        migrations.AlterField('project', 'id_responsavel', models.ForeignKey(to='users.users', on_delete=django.db.models.deletion.CASCADE, db_column='id_responsavel', null=True, blank=True, db_constraint=False)),
        migrations.AlterField('project', 'id_setor', models.ForeignKey(to='sector.sector', on_delete=django.db.models.deletion.CASCADE, db_column='id_setor', null=True, blank=True, db_constraint=False)),
        migrations.AlterModelTable('project', 'arquivo_projetos'),
        migrations.AlterModelTable('tarefa', 'arquivo_tarefas'),
        migrations.SeparateDatabaseAndState(state_operations=[migrations.DeleteModel('tarefa'), migrations.DeleteModel('project')]),
    ]
