from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_messsetting_studentperiodaccount_is_manual_due_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='studentperiodaccount',
            old_name='total_due',
            new_name='total_to_collect',
        ),
        migrations.RenameField(
            model_name='studentperiodaccount',
            old_name='manual_due',
            new_name='manual_remaining',
        ),
        migrations.RenameField(
            model_name='studentperiodaccount',
            old_name='is_manual_due',
            new_name='is_manual_remaining',
        ),
        migrations.AlterField(
            model_name='studentperiodaccount',
            name='total_to_collect',
            field=models.DecimalField(decimal_places=2, default=0, help_text='Total amount to collect from this student for this period', max_digits=12),
        ),
        migrations.AlterField(
            model_name='studentperiodaccount',
            name='manual_remaining',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='If set, overrides the auto-calculated remaining amount', max_digits=12, null=True),
        ),
        migrations.AlterField(
            model_name='studentperiodaccount',
            name='is_manual_remaining',
            field=models.BooleanField(default=False, help_text='Whether remaining amount is manually set'),
        ),
    ]