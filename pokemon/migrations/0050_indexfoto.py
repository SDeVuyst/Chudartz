from django.db import migrations, models
import darts.validators.image_validator


class Migration(migrations.Migration):

    dependencies = [
        ('pokemon', '0049_team'),
    ]

    operations = [
        migrations.CreateModel(
            name='IndexFoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titel', models.CharField(max_length=100, verbose_name='Titel')),
                ('afbeelding', models.ImageField(upload_to='index_fotos', validators=[darts.validators.image_validator.validate_image_max_size], verbose_name='Afbeelding')),
                ('category', models.CharField(choices=[('beurzen', 'Beurzen'), ('community', 'Community'), ('collectibles', 'Collectibles')], default='beurzen', max_length=20, verbose_name='Categorie')),
                ('active', models.BooleanField(default=True, verbose_name='Actief')),
            ],
            options={
                'verbose_name': 'Index Foto',
                'verbose_name_plural': "Index Foto's",
            },
        ),
    ]
