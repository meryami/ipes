from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST

from bengkel.models import Bengkel, Jemputan, Kehadiran, PenganjurRequest, UserProfile, BengkelContribution, ContributionFile
from problems.models import ProblemStatement


def _pending_count():
    return PenganjurRequest.objects.filter(status="pending").count()


@login_required
def dashboard(request):
    if not request.user.is_superuser:
        return redirect("home")

    now = timezone.now()
    stats = {
        "total_bengkel":    Bengkel.objects.count(),
        "bengkel_aktif":    Bengkel.objects.filter(tarikh__gte=now).count(),
        "total_penganjur":  User.objects.filter(is_staff=True, is_superuser=False).count(),
        "total_peserta":    User.objects.filter(is_staff=False, is_superuser=False).count(),
        "total_jemputan":   Jemputan.objects.count(),
        "total_hadir":      Kehadiran.objects.count(),
        "total_pernyataan": ProblemStatement.objects.count(),
    }
    bengkels_terkini = (
        Bengkel.objects
        .select_related("created_by")
        .prefetch_related("jemputan")
        .order_by("-created_at")[:10]
    )
    return render(request, "superadmin/dashboard.html", {
        "stats": stats,
        "bengkels_terkini": bengkels_terkini,
        "pending_permohonan": _pending_count(),
    })


@login_required
def semua_bengkel(request):
    if not request.user.is_superuser:
        return redirect("home")
    bengkels = (
        Bengkel.objects
        .select_related("created_by")
        .prefetch_related("jemputan")
        .order_by("-created_at")
    )
    return render(request, "superadmin/semua_bengkel.html", {
        "bengkels": bengkels,
        "today": timezone.now(),
        "pending_permohonan": _pending_count(),
    })


@login_required
def semua_pengguna(request):
    if not request.user.is_superuser:
        return redirect("home")
    pengguna = User.objects.filter(is_superuser=False).order_by("date_joined")
    return render(request, "superadmin/semua_pengguna.html", {
        "pengguna": pengguna,
        "pending_permohonan": _pending_count(),
    })


@login_required
@require_POST
def toggle_penganjur(request, uid):
    """Promote peserta → penganjur or demote penganjur → peserta."""
    if not request.user.is_superuser:
        return redirect("home")
    user = get_object_or_404(User, pk=uid, is_superuser=False)
    user.is_staff = not user.is_staff
    user.save()
    role = "Penganjur" if user.is_staff else "Peserta"
    messages.success(request, f"{user.username} kini ditetapkan sebagai {role}.")
    return redirect("superadmin:semua_pengguna")


@login_required
def tambah_penganjur(request):
    """Superadmin creates a new penganjur account."""
    import re as _re
    if not request.user.is_superuser:
        return redirect("home")

    if request.method == "POST":
        username   = request.POST.get("username", "").strip()
        email      = request.POST.get("email", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name  = request.POST.get("last_name", "").strip()
        organisasi = request.POST.get("organisasi", "").strip()
        jabatan    = request.POST.get("jabatan", "").strip()
        telefon    = request.POST.get("telefon", "").strip()
        pw1        = request.POST.get("password1", "")
        pw2        = request.POST.get("password2", "")
        form_data  = {
            "username": username, "email": email,
            "first_name": first_name, "last_name": last_name,
            "organisasi": organisasi, "jabatan": jabatan, "telefon": telefon,
        }

        def _err(msg):
            return render(request, "superadmin/tambah_penganjur.html", {"error": msg, "form_data": form_data, "pending_permohonan": _pending_count()})

        if not username or len(username) < 3:
            return _err("Nama pengguna mesti sekurang-kurangnya 3 aksara.")
        if not _re.match(r'^[\w]+$', username):
            return _err("Nama pengguna hanya boleh mengandungi huruf, nombor, dan garis bawah (_).")
        if User.objects.filter(username=username).exists():
            return _err("Nama pengguna ini sudah digunakan.")
        if not email or not _re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return _err("Sila masukkan alamat e-mel yang sah.")
        if User.objects.filter(email=email).exists():
            return _err("E-mel ini sudah berdaftar.")
        if not organisasi:
            return _err("Nama organisasi wajib diisi.")
        if len(pw1) < 8:
            return _err("Kata laluan mesti sekurang-kurangnya 8 aksara.")
        if pw1 != pw2:
            return _err("Kata laluan tidak sepadan.")

        user = User.objects.create_user(
            username=username, email=email, password=pw1,
            first_name=first_name, last_name=last_name,
            is_staff=True,
        )
        UserProfile.objects.create(
            user=user,
            organisasi=organisasi,
            jabatan=jabatan,
            telefon=telefon,
        )
        messages.success(request, f'Akaun penganjur "{username}" berjaya dicipta.')
        return redirect("superadmin:semua_pengguna")

    return render(request, "superadmin/tambah_penganjur.html", {"pending_permohonan": _pending_count()})


@login_required
def semua_pernyataan(request):
    if not request.user.is_superuser:
        return redirect("home")
    pernyataan = (
        ProblemStatement.objects
        .select_related("jemputan__bengkel", "jemputan__user")
        .order_by("-created_at")
    )
    return render(request, "superadmin/semua_pernyataan.html", {
        "pernyataan": pernyataan,
        "pending_permohonan": _pending_count(),
    })


@login_required
def permohonan_penganjur(request):
    """Superadmin — list all penganjur requests."""
    if not request.user.is_superuser:
        return redirect("home")
    permohonan = PenganjurRequest.objects.select_related("user").order_by("-created_at")
    return render(request, "superadmin/permohonan_penganjur.html", {
        "permohonan": permohonan,
        "pending_permohonan": _pending_count(),
    })


@login_required
@require_POST
def lulus_permohonan(request, pid):
    """Superadmin approves a penganjur request — activates account and sends credentials by email."""
    import random, string
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings as _settings

    if not request.user.is_superuser:
        return redirect("home")
    req = get_object_or_404(PenganjurRequest, pk=pid)

    # Generate a random temporary password
    temp_pw = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

    req.status = "approved"
    req.catatan_admin = request.POST.get("catatan_admin", "").strip()
    req.save()

    req.user.set_password(temp_pw)
    req.user.is_active = True
    req.user.is_staff = True
    req.user.save()

    # Send approval email with credentials
    subject = "Permohonan Penganjur Anda Telah Diluluskan — NDHB"
    login_url = request.build_absolute_uri("/login/")
    text_body = (
        f"Assalamualaikum / Salam Sejahtera,\n\n"
        f"Permohonan anda untuk menjadi Penganjur dalam Sistem Pengurusan Bengkel NDHB telah DILULUSKAN.\n\n"
        f"Maklumat Log Masuk Anda:\n"
        f"  Nama Pengguna : {req.user.username}\n"
        f"  Kata Laluan   : {temp_pw}\n\n"
        f"Sila log masuk di: {login_url}\n\n"
        f"Anda AMAT DISYORKAN untuk menukar kata laluan anda selepas log masuk pertama.\n\n"
        f"Terima kasih.\n"
        f"Pasukan NDHB"
    )
    html_body = f"""
    <div style="font-family:Inter,Arial,sans-serif;max-width:560px;margin:auto;background:#0f172a;
                color:#e2e8f0;padding:36px 40px;border-radius:16px;">
      <h2 style="color:#2dd4bf;margin-top:0;">Permohonan Diluluskan ✅</h2>
      <p>Assalamualaikum / Salam Sejahtera,</p>
      <p>Permohonan anda untuk menjadi <strong>Penganjur</strong> dalam Sistem Pengurusan Bengkel NDHB
         telah <span style="color:#4ade80;font-weight:600;">DILULUSKAN</span>.</p>
      <div style="background:#1e293b;border-radius:10px;padding:20px 24px;margin:24px 0;
                  border-left:4px solid #2dd4bf;">
        <p style="margin:0 0 8px;font-weight:600;color:#94a3b8;font-size:12px;text-transform:uppercase;
                  letter-spacing:.08em;">Maklumat Log Masuk</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <tr><td style="padding:6px 0;color:#94a3b8;width:140px;">Nama Pengguna</td>
              <td style="padding:6px 0;font-family:monospace;font-size:15px;color:#f1f5f9;font-weight:700;">
                {req.user.username}</td></tr>
          <tr><td style="padding:6px 0;color:#94a3b8;">Kata Laluan</td>
              <td style="padding:6px 0;font-family:monospace;font-size:15px;color:#fbbf24;font-weight:700;">
                {temp_pw}</td></tr>
        </table>
      </div>
      <a href="{login_url}"
         style="display:inline-block;background:#2dd4bf;color:#0f172a;text-decoration:none;
                font-weight:700;padding:12px 28px;border-radius:10px;font-size:14px;">
        Log Masuk Sekarang
      </a>
      <p style="margin-top:28px;font-size:13px;color:#64748b;">
        Anda <strong style="color:#f87171;">AMAT DISYORKAN</strong> untuk menukar kata laluan anda
        selepas log masuk pertama.
      </p>
      <hr style="border:none;border-top:1px solid #1e293b;margin:28px 0;">
      <p style="font-size:12px;color:#475569;margin:0;">Sistem Pengurusan Bengkel · NDHB</p>
    </div>
    """
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=getattr(_settings, "DEFAULT_FROM_EMAIL", "noreply@ndhb.my"),
            to=[req.user.email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send()
        messages.success(
            request,
            f"Permohonan {req.user.username} telah diluluskan. E-mel kelayakan dihantar ke {req.user.email}.",
        )
    except Exception:
        messages.warning(
            request,
            f"Permohonan {req.user.username} diluluskan, TETAPI e-mel GAGAL dihantar "
            f"(semak tetapan SMTP). Kata laluan sementara: {temp_pw}",
        )

    return redirect("superadmin:permohonan_penganjur")


@login_required
@require_POST
def tolak_permohonan(request, pid):
    """Superadmin rejects a penganjur request — notifies applicant by email."""
    import random, string
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings as _settings

    if not request.user.is_superuser:
        return redirect("home")
    req = get_object_or_404(PenganjurRequest, pk=pid)
    req.status = "rejected"
    req.catatan_admin = request.POST.get("catatan_admin", "").strip()
    req.save()

    # Send rejection email
    subject = "Permohonan Penganjur Anda Tidak Berjaya — NDHB"
    catatan = req.catatan_admin or "Tiada catatan tambahan."
    text_body = (
        f"Assalamualaikum / Salam Sejahtera,\n\n"
        f"Kami ingin memaklumkan bahawa permohonan anda untuk menjadi Penganjur "
        f"dalam Sistem Pengurusan Bengkel NDHB TIDAK BERJAYA pada masa ini.\n\n"
        f"Catatan daripada pentadbir:\n{catatan}\n\n"
        f"Untuk sebarang pertanyaan, sila hubungi pentadbir sistem.\n\n"
        f"Terima kasih.\nPasukan NDHB"
    )
    html_body = f"""
    <div style="font-family:Inter,Arial,sans-serif;max-width:560px;margin:auto;background:#0f172a;
                color:#e2e8f0;padding:36px 40px;border-radius:16px;">
      <h2 style="color:#f87171;margin-top:0;">Permohonan Tidak Berjaya &#10060;</h2>
      <p>Assalamualaikum / Salam Sejahtera,</p>
      <p>Kami ingin memaklumkan bahawa permohonan anda untuk menjadi <strong>Penganjur</strong>
         dalam Sistem Pengurusan Bengkel NDHB
         <span style="color:#f87171;font-weight:600;">TIDAK BERJAYA</span> pada masa ini.</p>
      <div style="background:#1e293b;border-radius:10px;padding:16px 20px;margin:20px 0;
                  border-left:4px solid #ef4444;">
        <p style="margin:0 0 6px;font-size:11px;font-weight:700;color:#94a3b8;
                  text-transform:uppercase;letter-spacing:.06em;">Catatan Pentadbir</p>
        <p style="margin:0;font-size:14px;color:#fca5a5;">{catatan}</p>
      </div>
      <p style="font-size:13px;color:#94a3b8;">
        Untuk sebarang pertanyaan lanjut, sila hubungi pentadbir sistem.
      </p>
      <hr style="border:none;border-top:1px solid #1e293b;margin:28px 0;">
      <p style="font-size:12px;color:#475569;margin:0;">Sistem Pengurusan Bengkel &middot; NDHB</p>
    </div>
    """
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=getattr(_settings, "DEFAULT_FROM_EMAIL", "noreply@ndhb.my"),
            to=[req.user.email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send()
        messages.success(request, f"Permohonan {req.user.username} telah ditolak. E-mel notifikasi dihantar ke {req.user.email}.")
    except Exception:
        messages.warning(request, f"Permohonan {req.user.username} ditolak, TETAPI e-mel GAGAL dihantar (semak tetapan SMTP).")

    return redirect("superadmin:permohonan_penganjur")


# ── Edit & Delete Pengguna ────────────────────────────────────────────────────

@login_required
def edit_pengguna(request, uid):
    if not request.user.is_superuser:
        return redirect("home")
    import re as _re
    u = get_object_or_404(User, pk=uid, is_superuser=False)
    profile, _ = UserProfile.objects.get_or_create(user=u)

    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name  = request.POST.get("last_name", "").strip()
        email      = request.POST.get("email", "").strip()
        is_active  = request.POST.get("is_active") == "1"
        is_staff   = request.POST.get("is_staff") == "1"
        organisasi = request.POST.get("organisasi", "").strip()
        jabatan    = request.POST.get("jabatan", "").strip()
        telefon    = request.POST.get("telefon", "").strip()
        new_pw     = request.POST.get("new_password", "").strip()

        def _err(msg):
            return render(request, "superadmin/edit_pengguna.html", {
                "u": u, "profile": profile, "error": msg,
                "pending_permohonan": _pending_count(),
            })

        if not email or not _re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return _err("Sila masukkan alamat e-mel yang sah.")
        if User.objects.filter(email=email).exclude(pk=uid).exists():
            return _err("E-mel ini sudah digunakan oleh pengguna lain.")
        if new_pw and len(new_pw) < 8:
            return _err("Kata laluan baharu mesti sekurang-kurangnya 8 aksara.")

        u.first_name = first_name
        u.last_name  = last_name
        u.email      = email
        u.is_active  = is_active
        u.is_staff   = is_staff
        if new_pw:
            u.set_password(new_pw)
        u.save()

        profile.organisasi = organisasi
        profile.jabatan    = jabatan
        profile.telefon    = telefon
        profile.save()

        messages.success(request, f'Akaun "{u.username}" berjaya dikemaskini.')
        return redirect("superadmin:semua_pengguna")

    return render(request, "superadmin/edit_pengguna.html", {
        "u": u, "profile": profile,
        "pending_permohonan": _pending_count(),
    })


@login_required
@require_POST
def delete_pengguna(request, uid):
    if not request.user.is_superuser:
        return redirect("home")
    u = get_object_or_404(User, pk=uid, is_superuser=False)
    username = u.username
    u.delete()
    messages.success(request, f'Akaun "{username}" telah dipadam.')
    return redirect("superadmin:semua_pengguna")


# ── Edit & Delete Bengkel ─────────────────────────────────────────────────────

@login_required
def edit_bengkel(request, bid):
    if not request.user.is_superuser:
        return redirect("home")
    import datetime as _dt
    from django.utils import timezone as _tz
    b = get_object_or_404(Bengkel, pk=bid)

    if request.method == "POST":
        title             = request.POST.get("title", "").strip()
        description       = request.POST.get("description", "").strip()
        tarikh_str        = request.POST.get("tarikh", "").strip()
        tarikh_tamat_str  = request.POST.get("tarikh_tamat", "").strip()
        lokasi_nama       = request.POST.get("lokasi_nama", "").strip()
        lokasi_alamat     = request.POST.get("lokasi_alamat", "").strip()
        organizer_nama    = request.POST.get("organizer_nama", "").strip()
        organizer_email   = request.POST.get("organizer_email", "").strip()
        organizer_telefon = request.POST.get("organizer_telefon", "").strip()
        had_peserta       = request.POST.get("had_peserta", "0").strip()

        def _err(msg):
            return render(request, "superadmin/edit_bengkel.html", {
                "b": b, "error": msg,
                "pending_permohonan": _pending_count(),
            })

        if not title:
            return _err("Tajuk bengkel wajib diisi.")
        if not tarikh_str:
            return _err("Tarikh bengkel wajib diisi.")
        if not lokasi_nama:
            return _err("Nama lokasi wajib diisi.")

        try:
            tarikh = _tz.make_aware(_dt.datetime.fromisoformat(tarikh_str))
        except ValueError:
            return _err("Format tarikh tidak sah.")

        tarikh_tamat = None
        if tarikh_tamat_str:
            try:
                tarikh_tamat = _tz.make_aware(_dt.datetime.fromisoformat(tarikh_tamat_str))
            except ValueError:
                return _err("Format tarikh tamat tidak sah.")

        b.title             = title
        b.description       = description
        b.tarikh            = tarikh
        b.tarikh_tamat      = tarikh_tamat
        b.lokasi_nama       = lokasi_nama
        b.lokasi_alamat     = lokasi_alamat
        b.organizer_nama    = organizer_nama
        b.organizer_email   = organizer_email
        b.organizer_telefon = organizer_telefon
        b.had_peserta       = int(had_peserta) if had_peserta.isdigit() else 0
        b.save()

        messages.success(request, f'Bengkel "{b.title}" berjaya dikemaskini.')
        return redirect("superadmin:semua_bengkel")

    return render(request, "superadmin/edit_bengkel.html", {
        "b": b,
        "pending_permohonan": _pending_count(),
    })


@login_required
@require_POST
def delete_bengkel(request, bid):
    if not request.user.is_superuser:
        return redirect("home")
    b = get_object_or_404(Bengkel, pk=bid)
    title = b.title
    b.delete()
    messages.success(request, f'Bengkel "{title}" telah dipadam.')
    return redirect("superadmin:semua_bengkel")


@login_required
@require_POST
def delete_contribution_comment(request, cid):
    if not request.user.is_superuser:
        return redirect("home")
    from bengkel.models import BengkelContribution
    c = get_object_or_404(BengkelContribution, pk=cid)
    bid = c.bengkel_id
    line_idx = request.POST.get("line_idx")
    if line_idx is not None:
        lines = c.comment.splitlines()
        try:
            idx = int(line_idx)
            if 0 <= idx < len(lines):
                lines.pop(idx)
            c.comment = "\n".join(l for l in lines if l.strip())
        except (ValueError, IndexError):
            pass
    else:
        c.comment = ""
    c.save(update_fields=["comment"])
    messages.success(request, "Komen telah dipadam.")
    return redirect("superadmin:detail_bengkel", bid=bid)


def delete_contribution_file(request, fid):
    if not request.user.is_superuser:
        return redirect("home")
    import os
    cf = get_object_or_404(ContributionFile, pk=fid)
    bid = cf.contribution.bengkel_id
    try:
        if cf.file and os.path.isfile(cf.file.path):
            os.remove(cf.file.path)
    except Exception:
        pass
    cf.delete()
    messages.success(request, f'Fail "{cf.original_name}" telah dipadam.')
    return redirect("superadmin:detail_bengkel", bid=bid)


@login_required
def detail_bengkel(request, bid):
    if not request.user.is_superuser:
        return redirect("home")
    b = get_object_or_404(
        Bengkel.objects
        .select_related("created_by", "created_by__profile")
        .prefetch_related(
            "jemputan__kehadiran",
            "jemputan__contribution__files",
            "tentative",
        ),
        pk=bid,
    )
    jemputan_list = b.jemputan.select_related("user").prefetch_related("contribution__files").order_by("nama")
    return render(request, "superadmin/detail_bengkel.html", {
        "b": b,
        "jemputan_list": jemputan_list,
        "pending_permohonan": _pending_count(),
    })
