# Generated manually — ensure one ShopMallSettings row exists for admin editing.

from django.db import migrations


def seed_settings(apps, schema_editor):
    ShopMallSettings = apps.get_model("shop", "ShopMallSettings")
    if not ShopMallSettings.objects.exists():
        ShopMallSettings.objects.create(
            default_pickup_instruction="总部行政部前台领取 · 工作日 9:00–18:00 · 请携带订单号与工牌"
        )


def unseed(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0005_shop_mall_settings_and_pickup_text"),
    ]

    operations = [
        migrations.RunPython(seed_settings, unseed),
    ]
