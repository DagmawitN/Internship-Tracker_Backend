from django.contrib import admin
from django.apps import apps

app = apps.get_app_config('core')

for model_name,model in app.models.items():
    if not admin.site.is_registered(model):
        admin.site.register(model)
