from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("api/focus-blur/", views.focus_blur_report, name="focus_blur_report"),
    path("exam/<int:pk>/launch/", views.exam_launch, name="exam_launch"),
    path("all/", views.course_catalog, name="course_catalog"),
    path("instructor/<int:pk>/", views.instructor_detail, name="instructor_detail"),
    path("course/<int:pk>/", views.course_detail, name="course_detail"),
    path("course/<int:pk>/complete/", views.course_mark_complete, name="course_mark_complete"),
    path(
        "course/<int:pk>/video-ack/",
        views.video_playthrough_ack,
        name="video_playthrough_ack",
    ),
    path("my/", views.my_learning, name="my_learning"),
    path("my/profile/", views.my_profile_update, name="my_profile_update"),
    path("my/training/", views.my_training, name="my_training"),
    path("my/external/", views.my_external, name="my_external"),
    path("my/projects/", views.my_projects, name="my_projects"),
    path("my/exams/", views.my_exams, name="my_exams"),
    path("my/courses/", views.my_courses, name="my_courses"),
    path("my/courses/add/<int:pk>/", views.add_to_plan, name="add_to_plan"),
    path("my/learning-settings/", views.learning_settings, name="learning_settings"),
    path("my/applications/", views.my_applications_redirect, name="my_applications"),
]
