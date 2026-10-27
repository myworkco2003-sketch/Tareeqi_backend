from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('places', '0008_platform_categories')]
    operations = [
        migrations.AlterField('place', 'latitude', models.FloatField(null=True, blank=True, verbose_name='خط العرض (Lat)')),
        migrations.AlterField('place', 'longitude', models.FloatField(null=True, blank=True, verbose_name='خط الطول (Lon)')),
    ]
