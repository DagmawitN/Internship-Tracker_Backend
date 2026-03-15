from django.contrib import admin,messages
from django.apps import apps
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.shortcuts import render,redirect
from django.urls.resolvers import URLPattern
from .models import PreRegisteredStudent,Department
from .forms.upload import UploadCSVForm
import csv
import io


class PreRegisteredStudentAdmin(admin.ModelAdmin):
    list_display = ("name","student_id","department","created_at")
    change_list_template = "admin/core/preregisteredstudent/change_list.html"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-students/",
                self.admin_site.admin_view(self.import_students),
                name="import-students",
            ),
        ]
        return custom_urls + urls

    def import_students(self, request):

        if request.method == "POST":
            form = UploadCSVForm(request.POST, request.FILES)

            if form.is_valid():
                csv_file = form.cleaned_data["file"]

                decoded = csv_file.read().decode("utf-8")
                io_string = io.StringIO(decoded)

                reader = csv.DictReader(io_string)

                students = []
                departments = {d.department_name.strip(): d for d in Department.objects.all()}
                for row in reader:
                    dept_name = row["department"].strip()
                    dept = departments.get(dept_name)
                    if not dept:
                        print(f"Skipping {row['name']}: Department '{dept_name}' not found")
                        continue
                    students.append(
                        PreRegisteredStudent(
                            name=row["name"].strip(),
                            student_id=row["student_id"].strip(),
                            department=dept,
                        )
                    )

                PreRegisteredStudent.objects.bulk_create(
                    students, ignore_conflicts=True
                )

                self.message_user(
                    request,
                    f"{len(students)} students imported successfully!",
                    messages.SUCCESS,
                )

                return redirect("..")

        else:
            form = UploadCSVForm()

        context = {
            "form": form,
            "title": "Preregister Students",
        }

        return render(request, "admin/import_student.html", context)                
            


admin.site.register(PreRegisteredStudent, PreRegisteredStudentAdmin)
app = apps.get_app_config('core')

for model_name,model in app.models.items():
    if not admin.site.is_registered(model):
        admin.site.register(model)

