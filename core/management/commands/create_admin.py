import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import UserProfile


class Command(BaseCommand):
    help = 'Create a superuser from environment variables if ADMIN_USERNAME, ADMIN_EMAIL, and ADMIN_PASSWORD are set.'

    def handle(self, *args, **options):
        username = os.environ.get('ADMIN_USERNAME')
        email = os.environ.get('ADMIN_EMAIL')
        password = os.environ.get('ADMIN_PASSWORD')

        if not username or not email or not password:
            self.stdout.write(
                self.style.WARNING('ADMIN variables missing. Skipped admin creation.')
            )
            return

        User = get_user_model()

        user = User.objects.filter(username=username).first()
        if user is None:
            user = User.objects.filter(email=email).first()

        if user is not None:
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.role = 'admin'
            profile.is_active_user = True
            profile.save()
            if not user.is_superuser:
                user.is_superuser = True
                user.is_staff = True
                user.save(update_fields=['is_superuser', 'is_staff'])
            self.stdout.write(
                self.style.SUCCESS(f'Admin user "{username}" already exists. Profile role set to admin.')
            )
            return

        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={'role': 'admin', 'is_active_user': True},
        )
        profile.role = 'admin'
        profile.is_active_user = True
        profile.save()
        self.stdout.write(
            self.style.SUCCESS(f'Admin user "{username}" created successfully.')
        )
