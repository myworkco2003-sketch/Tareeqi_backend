import secrets
from urllib.parse import urlsplit
from django.conf import settings
from django.core import signing
from django.core.management.base import BaseCommand, CommandError
from places.submission_api import LINK_SALT


class Command(BaseCommand):
    help = 'Create an expiring, create-only place form link; no Django login is needed by its recipient.'

    def add_arguments(self, parser):
        parser.add_argument('--base-url', required=True, help='Dashboard origin, e.g. https://dashboard.example.com')

    def handle(self, *args, **options):
        base_url = options['base_url'].rstrip('/')
        parsed = urlsplit(base_url)
        if parsed.scheme not in ('https', 'http') or not parsed.netloc or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
            raise CommandError('--base-url must be an HTTP(S) origin without a path, query, or fragment.')
        token = signing.dumps({'scope': 'create-place', 'version': settings.PLACES_FORM_LINK_VERSION, 'nonce': secrets.token_urlsafe(16)}, salt=LINK_SALT)
        self.stdout.write(f'{base_url}/places/new#token={token}')
