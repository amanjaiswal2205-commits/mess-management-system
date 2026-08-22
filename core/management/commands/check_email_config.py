import os
from django.core.management.base import BaseCommand
from django.conf import settings


PLACEHOLDER_VALUES = {
    'EMAIL_HOST_USER': {'yourgmail@gmail.com', 'your_real_address@gmail.com'},
    'EMAIL_HOST_PASSWORD': {'your_16_character_gmail_app_password'},
    'DEFAULT_FROM_EMAIL': {'yourgmail@gmail.com', 'your_real_address@gmail.com'},
}


class Command(BaseCommand):
    help = 'Check email configuration status without exposing secrets.'

    def handle(self, *args, **options):
        fields = ['EMAIL_HOST', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD', 'DEFAULT_FROM_EMAIL']
        for field in fields:
            value = getattr(settings, field, '') or os.environ.get(field, '')
            if not value:
                self.stdout.write(f'{field}: not configured')
            else:
                if field in PLACEHOLDER_VALUES and value in PLACEHOLDER_VALUES[field]:
                    self.stdout.write(f'{field}: configured (placeholder — real value required)')
                else:
                    self.stdout.write(f'{field}: configured')
