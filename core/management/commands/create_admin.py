from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Create a superuser from environment variables if ADMIN_USERNAME, ADMIN_EMAIL, and ADMIN_PASSWORD are set.'

    def handle(self, *args, **options):
        username = __import__('os').environ.get('ADMIN_USERNAME')
        email = __import__('os').environ.get('ADMIN_EMAIL')
        password = __import__('os').environ.get('ADMIN_PASSWORD')

        if not username or not email or not password:
            self.stdout.write(
                self.style.WARNING('Skipped admin creation: ADMIN_USERNAME, ADMIN_EMAIL, or ADMIN_PASSWORD not set.')
            )
            return

        User = get_user_model()

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User "{username}" already exists. Skipped creation.')
            )
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.WARNING(f'User with email "{email}" already exists. Skipped creation.')
            )
            return

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(
            self.style.SUCCESS(f'Superuser "{username}" created successfully.')
        )
