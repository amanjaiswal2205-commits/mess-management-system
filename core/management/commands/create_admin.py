import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import UserProfile


class Command(BaseCommand):
    help = 'Create a superuser from environment variables and optionally reset the configured superuser password.'

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        reset_password = os.environ.get('DJANGO_RESET_SUPERUSER_PASSWORD')

        User = get_user_model()

        if username and reset_password:
            user = User.objects.filter(username=username).first()
            if user is None:
                self.stdout.write(
                    self.style.WARNING(
                        'Configured superuser not found; password reset was not performed.'
                    )
                )
            elif user.is_superuser and user.is_staff:
                user.set_password(reset_password)
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        'Admin password reset completed for configured superuser.'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        'Configured superuser is not a superuser/staff account; password reset was not performed.'
                    )
                )

        if not username or not email or not password:
            self.stdout.write(
                self.style.WARNING('DJANGO_SUPERUSER variables missing. Skipped admin creation.')
            )
            return

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
