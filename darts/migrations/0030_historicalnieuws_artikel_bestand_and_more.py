# Generated by Django 5.1.1 on 2024-10-29 20:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('darts', '0029_nieuws_historicalnieuws'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalnieuws',
            name='artikel_bestand',
            field=models.TextField(blank=True, max_length=100, null=True, verbose_name='Artikel Bestand'),
        ),
        migrations.AddField(
            model_name='nieuws',
            name='artikel_bestand',
            field=models.FileField(blank=True, null=True, upload_to='artikels', verbose_name='Artikel Bestand'),
        ),
        migrations.AlterField(
            model_name='historicalnieuws',
            name='link',
            field=models.URLField(blank=True, null=True, verbose_name='Artikel URL'),
        ),
        migrations.AlterField(
            model_name='nieuws',
            name='link',
            field=models.URLField(blank=True, null=True, verbose_name='Artikel URL'),
        ),
    ]