# Generated manually — score is now a required field, scored out of 1000
# with 700 as the pass mark. Safe to run with no default: the table was
# confirmed empty (the one prior row was stale test data on the old 0-100
# scale, deleted before this migration) at the time this was written.

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0002_alter_localassessment_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='internationalexamattempt',
            name='score',
            field=models.IntegerField(
                help_text='Score out of 1000 — 700 is the pass mark. Required.',
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(1000),
                ],
            ),
        ),
    ]
