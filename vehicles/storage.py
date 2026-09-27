from urllib.parse import urljoin
from django.conf import settings
from django.core.files.storage import FileSystemStorage


class CDNFileSystemStorage(FileSystemStorage):
    """
    FileSystemStorage that rewrites public media URLs through MEDIA_CDN_URL
    (e.g. a Cloudflare CDN / R2 / custom CDN hostname) when configured, while
    still reading/writing files on the local shared `/app/media` volume.
    """

    def url(self, name):
        rel_url = super().url(name)
        cdn_base = (getattr(settings, 'MEDIA_CDN_URL', '') or '').strip().rstrip('/')
        if cdn_base and not rel_url.startswith(('http://', 'https://')):
            if not rel_url.startswith('/'):
                rel_url = '/' + rel_url
            return f"{cdn_base}{rel_url}"
        return rel_url
