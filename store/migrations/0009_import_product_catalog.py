from django.db import migrations


PRODUCTS = [{'name': 'PRemium T shirt',
  'category': 'other',
  'description': '',
  'price': '700.00',
  'image': 'products/pngtree-red-t-shirt-png-image_12322366_eyzul0G.png',
  'sizes': 'S,M',
  'colors': 'Red',
  'stock': 4,
  'available': True}]


def import_catalog(apps, schema_editor):
    Product = apps.get_model("store", "Product")
    catalog = Product.objects.using(schema_editor.connection.alias)
    if catalog.exists():
        return

    for fields in PRODUCTS:
        catalog.create(**fields)


class Migration(migrations.Migration):
    dependencies = [('store', '0008_order_payment_method_order_payment_status_and_more')]

    operations = [
        migrations.RunPython(import_catalog, migrations.RunPython.noop),
    ]
