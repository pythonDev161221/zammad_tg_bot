# Generated migration for Customer model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0005_rename_group_telegrambot_zammad_group_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('telegram_bot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='chatbot.telegrambot')),
            ],
        ),
    ]