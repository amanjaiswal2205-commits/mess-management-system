from django.db import migrations
from django.db.models import Sum


def backfill_student_period_accounts(apps, schema_editor):
    Payment = apps.get_model('core', 'Payment')
    StudentPeriodAccount = apps.get_model('core', 'StudentPeriodAccount')
    PeriodDefaultFee = apps.get_model('core', 'PeriodDefaultFee')

    pairs = (
        Payment.objects
        .filter(period__isnull=False)
        .values_list('student', 'period')
        .distinct()
    )

    for student_id, period_id in pairs:
        try:
            default_fee = PeriodDefaultFee.objects.get(period_id=period_id).default_fee_per_student
        except PeriodDefaultFee.DoesNotExist:
            default_fee = None

        defaults = {}
        if default_fee is not None:
            defaults['total_to_collect'] = default_fee
        else:
            defaults['total_to_collect'] = 0

        StudentPeriodAccount.objects.get_or_create(
            student_id=student_id,
            period_id=period_id,
            defaults=defaults
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_purchase_unit'),
    ]

    operations = [
        migrations.RunPython(backfill_student_period_accounts, noop_reverse),
    ]
