from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("all/", views.course_catalog, name="course_catalog"),
    path("course/<int:pk>/", views.course_detail, name="course_detail"),
    path("course/<int:pk>/complete/", views.course_mark_complete, name="course_mark_complete"),
    path("my/", views.my_learning, name="my_learning"),
    path("my/profile/", views.my_profile_update, name="my_profile_update"),
    path("my/training/", views.my_training, name="my_training"),
    path("my/external/", views.my_external, name="my_external"),
    path("my/projects/", views.my_projects, name="my_projects"),
    path("my/exams/", views.my_exams, name="my_exams"),
    path("my/courses/", views.my_courses, name="my_courses"),
    path("my/applications/", views.my_applications_redirect, name="my_applications"),
]
