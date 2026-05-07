from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fazendaria', '0005_processofazendaria_data_distribuicao'),
    ]

    operations = [
        migrations.AddField(
            model_name='processofazendaria',
            name='apensos',
            field=models.CharField(blank=True, max_length=240, verbose_name='apensos'),
        ),
    ]
