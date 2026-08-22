from django.db import migrations, models


def backfill_student_name(apps, schema_editor):
    Student = apps.get_model('core', 'Student')
    for student in Student.objects.all():
        if not student.student_name:
            full_name = student.user.get_full_name().strip()
            if full_name:
                student.student_name = full_name
            else:
                student.student_name = student.user.username or ''
            student.save(update_fields=['student_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_payment_payment_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='student_name',
            field=models.CharField(blank=True, default='', help_text='Proper display name with spaces (e.g. Aman Jaiswal). Used in payment receipt emails. Duplicate names allowed.', max_length=150),
        ),
        migrations.RunPython(backfill_student_name, migrations.RunPython.noop),
    ]
