from django.contrib import admin
from .models import News

# Haber modelini yönetim paneline kaydet
admin.site.register(News)