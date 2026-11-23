import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('sector', '0006_preservar_legado')]
    operations = [
        migrations.AddConstraint(
            model_name='atividade',
            constraint=models.UniqueConstraint(condition=models.Q(('legado', False)), fields=('id_indicador', 'data_cadastro'), name='atividade_referencia_unica'),
        ),
        migrations.AddConstraint(
            model_name='atividade',
            constraint=models.CheckConstraint(condition=models.Q(('legado', True), ('valor__gte', 0), _connector='OR'), name='atividade_valor_positivo'),
        ),
        migrations.AddConstraint(
            model_name='indicador',
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower('nome'), models.F('id_setor'), condition=models.Q(('legado', False)), name='indicador_nome_setor_unico'),
        ),
    ]
