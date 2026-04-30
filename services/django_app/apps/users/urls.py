from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = "users"

urlpatterns = [
    # ── Auth ────────────────────────────────────────────────────────────
    path("login/",    views.LoginView.as_view(),    name="login"),
    path("register/", views.RegisterView.as_view(), name="register"),

    # JWT refresh — built-in SimpleJWT view, no custom code needed
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),

    # ── Profile ──────────────────────────────────────────────────────────
    path("me/",                          views.MeView.as_view(),            name="me"),
    path("",                             views.UserListView.as_view(),       name="list"),
    path("<int:pk>/",                    views.UserDetailView.as_view(),     name="detail"),
    path("<int:pk>/change-password/",    views.ChangePasswordView.as_view(), name="change-password"),
]
