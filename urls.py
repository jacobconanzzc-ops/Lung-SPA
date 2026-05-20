"""
NII application URL configuration
"""
from django.urls import path
from . import views

app_name = "nii"
urlpatterns = [
    path("upload_file", views.process_file, name="upload_file"),
    path("upload", views.upload_file, name="upload"),
    path("infer", views.infer_file, name="infer"),
    path("download_file", views.download_file, name="download_file"),
]

