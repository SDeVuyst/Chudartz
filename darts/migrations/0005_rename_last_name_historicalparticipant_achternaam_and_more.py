# Generated by Django 5.0.6 on 2024-08-18 13:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('darts', '0004_historicalparticipant_nummer_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='historicalparticipant',
            old_name='last_name',
            new_name='achternaam',
        ),
        migrations.RenameField(
            model_name='historicalparticipant',
            old_name='mail',
            new_name='email',
        ),
        migrations.RenameField(
            model_name='historicalparticipant',
            old_name='level',
            new_name='niveau',
        ),
        migrations.RenameField(
            model_name='historicalparticipant',
            old_name='first_name',
            new_name='voornaam',
        ),
        migrations.RenameField(
            model_name='participant',
            old_name='last_name',
            new_name='achternaam',
        ),
        migrations.RenameField(
            model_name='participant',
            old_name='mail',
            new_name='email',
        ),
        migrations.RenameField(
            model_name='participant',
            old_name='level',
            new_name='niveau',
        ),
        migrations.RenameField(
            model_name='participant',
            old_name='first_name',
            new_name='voornaam',
        ),
        migrations.AddField(
            model_name='historicalparticipant',
            name='postcode',
            field=models.IntegerField(default=8000, verbose_name='Postcode'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='participant',
            name='postcode',
            field=models.IntegerField(default=8000, verbose_name='Postcode'),
            preserve_default=False,
        ),
    ]