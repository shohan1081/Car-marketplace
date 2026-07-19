"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.py.urls if hasattr(admin, 'py') else admin.site.urls), # standard is admin.site.urls
    path('api/users/', include('users.urls')),
    path('api/vehicles/', include('vehicles.urls')),
    path('api/messaging/', include('messaging.urls')),
    path('api/subscriptions/', include('subscriptions.urls')),
]

if settings.DEBUG:
    import os
    import mimetypes
    from ranged_response import RangedFileResponse
    from django.http import Http404
    from django.urls import re_path

    def ranged_serve(request, path, document_root=None, show_indexes=False):
        filepath = os.path.join(document_root, path)
        if not os.path.exists(filepath):
            raise Http404()
        
        content_type, encoding = mimetypes.guess_type(filepath)
        content_type = content_type or 'application/octet-stream'
        
        file = open(filepath, 'rb')
        response = RangedFileResponse(request, file, content_type=content_type)
        return response

    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', ranged_serve, {'document_root': settings.MEDIA_ROOT}),
    ]
