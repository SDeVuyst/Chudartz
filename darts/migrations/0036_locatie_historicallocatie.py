# Generated by Django 5.1.4 on 2025-02-19 12:41

import ckeditor.fields
import django.db.models.deletion
import simple_history.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('darts', '0035_historicaltrainer_volgorde_trainer_volgorde'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Locatie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titel', models.CharField(max_length=100, verbose_name='Titel')),
                ('afbeelding', models.ImageField(upload_to='locaties', verbose_name='Hoofdafbeelding')),
                ('locatie', models.CharField(max_length=100, verbose_name='Locatie')),
                ('adres', models.CharField(max_length=100, verbose_name='Adres')),
                ('lesuren', ckeditor.fields.RichTextField(verbose_name='Lesuren')),
                ('extra_info', ckeditor.fields.RichTextField(verbose_name='Extra Info')),
                ('slug', models.SlugField(unique=True)),
                ('volgorde', models.SmallIntegerField(default=0, verbose_name='Volgorde')),
                ('active', models.BooleanField(default=True, verbose_name='Actief')),
            ],
            options={
                'verbose_name': 'Locatie',
                'verbose_name_plural': 'Locaties',
            },
        ),
        migrations.CreateModel(
            name='HistoricalLocatie',
            fields=[
                ('id', models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('titel', models.CharField(max_length=100, verbose_name='Titel')),
                ('afbeelding', models.TextField(max_length=100, verbose_name='Hoofdafbeelding')),
                ('locatie', models.CharField(max_length=100, verbose_name='Locatie')),
                ('adres', models.CharField(max_length=100, verbose_name='Adres')),
                ('lesuren', ckeditor.fields.RichTextField(verbose_name='Lesuren')),
                ('extra_info', ckeditor.fields.RichTextField(verbose_name='Extra Info')),
                ('slug', models.SlugField()),
                ('volgorde', models.SmallIntegerField(default=0, verbose_name='Volgorde')),
                ('active', models.BooleanField(default=True, verbose_name='Actief')),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField(db_index=True)),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Geschiedenis',
                'verbose_name_plural': 'historical Locaties',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': ('history_date', 'history_id'),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
    ]
