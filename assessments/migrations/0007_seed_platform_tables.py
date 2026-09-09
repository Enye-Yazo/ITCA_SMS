# Seeds the four vendor tables the client asked for by name, with their
# columns, under the Access Credentials / Labs sections. Test Admins can
# rename/delete/add to any of this afterward — this migration just gives
# them a non-empty starting point instead of two blank sections.

from django.db import migrations


TABLES = [
    # (section, vendor_name, [column labels in order], column_type)
    ('Credentials', 'Microsoft', ['Password', 'MCID'], 'Text'),
    ('Credentials', 'CompTIA', ['Password', 'CompTIA ID'], 'Text'),
    ('Labs', 'Microsoft', ['AZ-900', 'AZ-400'], 'Text'),
    ('Labs', 'CompTIA', ['SC-100', 'Security+'], 'Text'),
]

# Password column gets the masked Password type; everything else is plain Text.
PASSWORD_LABELS = {'Password'}


def seed_tables(apps, schema_editor):
    PlatformTable = apps.get_model('assessments', 'PlatformTable')
    PlatformColumn = apps.get_model('assessments', 'PlatformColumn')

    for order, (section, vendor_name, columns, _default_type) in enumerate(TABLES):
        table, _ = PlatformTable.objects.get_or_create(
            section=section, vendor_name=vendor_name, defaults={'order': order}
        )
        for col_order, label in enumerate(columns):
            column_type = 'Password' if label in PASSWORD_LABELS else 'Text'
            PlatformColumn.objects.get_or_create(
                table=table, label=label,
                defaults={'column_type': column_type, 'order': col_order},
            )


def unseed_tables(apps, schema_editor):
    PlatformTable = apps.get_model('assessments', 'PlatformTable')
    for section, vendor_name, _columns, _type in TABLES:
        PlatformTable.objects.filter(section=section, vendor_name=vendor_name).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0006_platformtable_platformrow_platformcolumn_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_tables, unseed_tables),
    ]
