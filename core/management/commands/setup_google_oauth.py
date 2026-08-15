import os
from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp


class Command(BaseCommand):
    help = 'Setup Google OAuth SocialApp from environment variables'

    def handle(self, *args, **options):
        client_id = os.environ.get('GOOGLE_CLIENT_ID')
        client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

        if not client_id or not client_secret:
            self.stdout.write(self.style.ERROR(
                'GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables must be set.'
            ))
            return

        site = Site.objects.get_current()

        app, created = SocialApp.objects.get_or_create(
            provider='google',
            defaults={
                'name': 'Google',
                'client_id': client_id,
                'secret': client_secret,
            }
        )

        if not created:
            app.client_id = client_id
            app.secret = client_secret
            app.save()

        app.sites.add(site)

        status = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'{status} Google SocialApp (client_id={client_id}) for site {site.domain}.'
        ))
