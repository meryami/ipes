from django.urls import path, include
from django.contrib import admin
from django.contrib.auth import views as auth_views, logout as auth_logout
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from problems.views import custom_login_view


def logout_view(request):
    auth_logout(request)
    return redirect("login")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/",  custom_login_view, name="login"),
    path("logout/", logout_view, name="logout"),

    # ── Password reset flow ──────────────────────────────────────────────────
    path("lupa-kata-laluan/",
         auth_views.PasswordResetView.as_view(template_name="registration/password_reset.html"),
         name="password_reset"),
    path("lupa-kata-laluan/dihantar/",
         auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"),
         name="password_reset_done"),
    path("reset/<uidb64>/<token>/",
         auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"),
         name="password_reset_confirm"),
    path("reset/berjaya/",
         auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"),
         name="password_reset_complete"),

    path("", include("problems.urls")),
    path("bengkel/", include("bengkel.urls", namespace="bengkel")),
    path("superadmin/", include("superadmin_portal.urls", namespace="superadmin")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
