from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse  # <-- needed for home and healthz
from django.conf import settings
from django.conf.urls.static import static

# Simple view for root '/'
def home(request):
    return HttpResponse("DAVE_BANK Backend is running!")

# Health check for Render
def healthz(request):
    return HttpResponse("OK")

urlpatterns = [
    path('', home),  # Root URL
    path('healthz', healthz),  # Health check endpoint
    path('admin/', admin.site.urls),
    path('api/', include('backdave_app.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
