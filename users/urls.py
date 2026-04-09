from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("login/", views.EmployeeLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="/"), name="logout"),
    path("register/", views.employee_register, name="register"),
    path("register/staff/", views.staff_register, name="register_staff"),
    path(
        "notifications/<int:pk>/open/",
        views.notification_open,
        name="notification_open",
    ),
]
