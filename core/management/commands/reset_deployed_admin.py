import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Reset the existing superuser password from environment variables.'

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if not username or not email or not password:
            self.stdout.write(
                self.style.WARNING('DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, and DJANGO_SUPERUSER_PASSWORD must all be set.')
            )
            return

        User = get_user_model()

        user = User.objects.filter(username=username).first()
        if user is None:
            user = User.objects.filter(email=email).first()

        if user is None:
            self.stdout.write(
                self.style.ERROR(f'No existing superuser found with username "{username}" or email "{email}".')
            )
            return

        user.set_password(password)
        user.save(update_fields=['password'])

        self.stdout.write(
            self.style.SUCCESS(f'Password reset successfully for user "{user.username}".')
        )
