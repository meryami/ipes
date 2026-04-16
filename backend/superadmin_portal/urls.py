from django.urls import path
from . import views

app_name = "superadmin"

urlpatterns = [
    path("",                                 views.dashboard,              name="dashboard"),
    path("bengkel/",                         views.semua_bengkel,          name="semua_bengkel"),
    path("bengkel/<int:bid>/edit/",          views.edit_bengkel,           name="edit_bengkel"),
    path("bengkel/<int:bid>/delete/",        views.delete_bengkel,         name="delete_bengkel"),
    path("bengkel/<int:bid>/detail/",        views.detail_bengkel,         name="detail_bengkel"),
    path("fail/<int:fid>/padam/",             views.delete_contribution_file,    name="delete_contribution_file"),
    path("komen/<int:cid>/padam/",            views.delete_contribution_comment, name="delete_contribution_comment"),
    path("bengkel/<int:bid>/tema/<int:tid>/padam/", views.delete_blueprint_theme, name="delete_blueprint_theme"),
    path("pengguna/",                        views.semua_pengguna,         name="semua_pengguna"),
    path("pengguna/tambah/",                 views.tambah_penganjur,       name="tambah_penganjur"),
    path("pengguna/<int:uid>/edit/",         views.edit_pengguna,          name="edit_pengguna"),
    path("pengguna/<int:uid>/delete/",       views.delete_pengguna,        name="delete_pengguna"),
    path("pengguna/<int:uid>/toggle/",       views.toggle_penganjur,       name="toggle_penganjur"),
    path("pernyataan/",                      views.semua_pernyataan,       name="semua_pernyataan"),
    path("permohonan/",                      views.permohonan_penganjur,   name="permohonan_penganjur"),
    path("permohonan/<int:pid>/lulus/",      views.lulus_permohonan,       name="lulus_permohonan"),
    path("permohonan/<int:pid>/tolak/",      views.tolak_permohonan,       name="tolak_permohonan"),
]
