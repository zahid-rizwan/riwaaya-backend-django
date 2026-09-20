from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('catalog', '0001_initial')]

    operations = [
        migrations.AddField(
            model_name='variant', name='size',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
        migrations.AddField(
            model_name='variant', name='color',
            field=models.CharField(blank=True, default='', max_length=80),
        ),
    ]