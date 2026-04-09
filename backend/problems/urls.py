from django.urls import path
from . import views

urlpatterns = [
    # ── HTML page URLs ──────────────────────────────────────
    path("",                   views.home,               name="home"),
    path("submit/",            views.submit_view,        name="submit"),
    path("list/",              views.list_view,          name="list"),
    path("profile/",           views.profile_view,       name="profile"),
    path("delete/<int:pk>/",   views.delete_view,        name="delete"),
    path("register/",                  views.register_view,          name="register"),
    path("permohonan/dihantar/",       views.permohonan_pending_view,  name="permohonan_pending"),
    path("check-email/",       views.check_email,        name="check_email"),
    path("users/",             views.users_view,         name="users"),
    path("users/<int:pk>/toggle/", views.toggle_user_active, name="toggle_user_active"),

    # ── REST API URLs (kept for reference) ─────────────────
    path("api/problem-statements/",          views.problem_list_create, name="problem-list-create"),
    path("api/problem-statements/<int:pk>/", views.problem_detail,      name="problem-detail"),
    path("api/profile/",                     views.data_profile,        name="data-profile"),
    path("api/meta/",                        views.meta,                name="meta"),
]

