from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='GuestCart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.CharField(max_length=255, unique=True)),
                ('items', models.JSONField(default=list)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]