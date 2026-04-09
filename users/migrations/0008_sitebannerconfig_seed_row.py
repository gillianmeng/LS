from django.db import migrations


def seed_site_banner_row(apps, schema_editor):
    SiteBannerConfig = apps.get_model("users", "SiteBannerConfig")
    if not SiteBannerConfig.objects.filter(pk=1).exists():
        SiteBannerConfig.objects.create(pk=1)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0007_sitebannerconfig"),
    ]

    operations = [
        migrations.RunPython(seed_site_banner_row, migrations.RunPython.noop),
    ]
