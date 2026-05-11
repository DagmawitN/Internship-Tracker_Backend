from django.contrib import admin,messages
from django.apps import apps
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.shortcuts import render,redirect
from django.urls.resolvers import URLPattern
from .models import PreRegisteredStudent,Department,PreRegisteredStaff
from .admin_classes import PreRegisteredStudentAdmin,PreRegisteredStaffAdmin




admin.site.register(PreRegisteredStudent, PreRegisteredStudentAdmin)
admin.site.register(PreRegisteredStaff, PreRegisteredStaffAdmin)



app = apps.get_app_config('core')

for model_name,model in app.models.items():
    if not admin.site.is_registered(model):
        admin.site.register(model)

