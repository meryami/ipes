from django.urls import path
from . import views

app_name = "bengkel"

urlpatterns = [
    # ── Penganjur home ───────────────────────────────────────────────────────
    path("home/",                     views.penganjur_home,     name="penganjur_home"),

    # ── Workshop CRUD ────────────────────────────────────────────────────────
    path("",                          views.bengkel_list,       name="list"),
    path("baru/",                     views.bengkel_create,     name="create"),
    path("<int:pk>/",                 views.bengkel_detail,     name="detail"),
    path("<int:pk>/edit/",            views.bengkel_edit,       name="edit"),
    path("<int:pk>/delete/",          views.bengkel_delete,     name="delete"),

    # ── Invitation management (admin) ────────────────────────────────────────
    path("<int:pk>/jemputan/",        views.jemputan_list,       name="jemputan_list"),
    path("<int:pk>/jemput/",           views.jemput,              name="jemput"),
    path("jemputan/csv-template/",     views.jemputan_csv_template, name="jemputan_csv_template"),
    path("jemputan/<int:jid>/",        views.jemputan_info,       name="jemputan_info"),
    path("jemputan/<int:jid>/delete/", views.jemputan_delete,     name="jemputan_delete"),
    path("jemputan/<int:jid>/qr/",     views.jemputan_qr_image,   name="jemputan_qr"),
    path("jemputan/<int:jid>/email/",  views.jemputan_send_email, name="jemputan_send_email"),
    # Open registration link management
    path("<int:pk>/reg/toggle/",       views.reg_toggle,          name="reg_toggle"),
    path("<int:pk>/reg/reset/",        views.reg_reset,           name="reg_reset"),
    path("<int:pk>/reg/",              views.open_reg_info,       name="open_reg_info"),
    path("<int:pk>/reg/qr/",           views.open_reg_qr_image,   name="open_reg_qr"),

    # ── QR scanner & check-in (staff) ───────────────────────────────────────
    path("<int:pk>/imbas/",           views.qr_scan,            name="qr_scan"),
    path("api/check-in/<uuid:qr_token>/", views.check_in_api,  name="check_in_api"),
    path("hadir/<uuid:qr_token>/",    views.check_in_staff,     name="check_in_staff"),

    # ── User dashboard (login required) ─────────────────────────────────────
    path("dashboard/",            views.user_dashboard,  name="dashboard"),
    path("profil/edit/",          views.edit_profile,    name="edit_profile"),
    path("profil/kata-laluan/",   views.change_password, name="change_password"),
    path("mohon-penganjur/",      views.mohon_penganjur, name="mohon_penganjur"),
    path("peserta/",              views.peserta_saya,    name="peserta_saya"),

    # ── Attendee problem statement submission (token-based, no login needed) ─
    path("i/<uuid:token>/hantar/", views.submit_pernyataan, name="submit_pernyataan"),

    # ── Public Portal — peserta daftar sendiri (no login) ────────────────────
    path("portal/",               views.portal_list,   name="portal_list"),
    path("portal/<int:pk>/",      views.portal_detail, name="portal_detail"),
    path("portal/tiket/<uuid:token>/", views.portal_tiket, name="portal_tiket"),

    # ── Public invitation pages (no login required) ──────────────────────────
    path("i/<uuid:token>/",           views.invitation_response, name="response"),
    path("i/<uuid:token>/terima/",    views.invitation_accept,   name="accept"),
    path("i/<uuid:token>/tolak/",     views.invitation_reject,   name="reject"),
    path("i/<uuid:token>/tiket/",     views.invitation_ticket,   name="tiket"),
    # Open registration (no login — anyone with the link)
    path("r/<uuid:reg_token>/",       views.open_reg,            name="open_reg"),

    # ── Contribution (file upload + comment) ─────────────────────────────────
    path("i/<uuid:token>/sumbangan/", views.contribute,          name="contribute"),

    # ── LLM Laporan ──────────────────────────────────────────────────────────
    path("<int:pk>/laporan/",         views.laporan_list,        name="laporan_list"),

    # ── Tentative (jadual program) ────────────────────────────────────────────
    path("<int:pk>/tentative/",                  views.tentative_manage, name="tentative"),
    path("<int:pk>/tentative/<int:tid>/edit/",   views.tentative_edit,   name="tentative_edit"),
    path("<int:pk>/tentative/<int:tid>/delete/", views.tentative_delete, name="tentative_delete"),

    # ── Situational Analysis Tools ────────────────────────────────────────────
    path("analisis/swot/",              views.analisis_swot,         name="analisis_swot"),
    path("analisis/swot/<int:pk>/del/", views.analisis_swot_delete,  name="analisis_swot_delete"),
    path("analisis/pestel/",              views.analisis_pestel,        name="analisis_pestel"),
    path("analisis/pestel/<int:pk>/del/", views.analisis_pestel_delete, name="analisis_pestel_delete"),
    path("analisis/vmost/",              views.analisis_vmost,         name="analisis_vmost"),
    path("analisis/vmost/<int:pk>/del/", views.analisis_vmost_delete,  name="analisis_vmost_delete"),
    path("analisis/5c/",              views.analisis_5c,            name="analisis_5c"),
    path("analisis/5c/<int:pk>/del/", views.analisis_5c_delete,     name="analisis_5c_delete"),
    path("analisis/soar/",              views.analisis_soar,          name="analisis_soar"),
    path("analisis/soar/<int:pk>/del/", views.analisis_soar_delete,   name="analisis_soar_delete"),
]
