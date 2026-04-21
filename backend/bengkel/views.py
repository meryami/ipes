from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
import csv
import io as _io
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from email.mime.image import MIMEImage
import qrcode
import io
import uuid
from django.db.models import Count, Sum
from django.urls import reverse

from .models import Bengkel, Jemputan, Kehadiran, PenganjurRequest, UserProfile


def _home_url(user):
    """Return the correct home URL for a given user based on role."""
    if user.is_superuser:
        return reverse("superadmin:dashboard")
    if user.is_staff:
        return reverse("bengkel:penganjur_home")
    return reverse("bengkel:dashboard")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _bengkel_form_save(request, bengkel=None):
    """Extract POST data and save Bengkel. Returns (instance, errors)."""
    errors = {}
    title         = request.POST.get("title", "").strip()
    description   = request.POST.get("description", "").strip()
    tarikh_raw    = request.POST.get("tarikh", "").strip()
    tarikh_tamat_raw = request.POST.get("tarikh_tamat", "").strip()
    lokasi_nama   = request.POST.get("lokasi_nama", "").strip()
    lokasi_alamat = request.POST.get("lokasi_alamat", "").strip()
    org_nama      = request.POST.get("organizer_nama", "").strip()
    org_email     = request.POST.get("organizer_email", "").strip()
    org_tel       = request.POST.get("organizer_telefon", "").strip()
    vid_ucapan    = request.POST.get("video_ucapan_url", "").strip()
    vid_arah      = request.POST.get("video_arah_url", "").strip()
    had           = request.POST.get("had_peserta", "0").strip() or "0"

    if not title:        errors["title"]          = "Tajuk wajib diisi."
    if not tarikh_raw:   errors["tarikh"]         = "Tarikh & masa mula wajib diisi."
    if not lokasi_nama:  errors["lokasi_nama"]    = "Nama lokasi wajib diisi."
    if not org_nama:     errors["organizer_nama"] = "Nama penganjur wajib diisi."

    # Parse datetime-local strings (format: "YYYY-MM-DDTHH:MM") into aware datetimes
    tarikh_dt = None
    if tarikh_raw and "tarikh" not in errors:
        dt = parse_datetime(tarikh_raw)
        if dt is None:
            errors["tarikh"] = "Format tarikh tidak sah."
        else:
            tarikh_dt = timezone.make_aware(dt) if timezone.is_naive(dt) else dt

    tarikh_tamat_dt = None
    if tarikh_tamat_raw:
        dt2 = parse_datetime(tarikh_tamat_raw)
        if dt2 is not None:
            tarikh_tamat_dt = timezone.make_aware(dt2) if timezone.is_naive(dt2) else dt2

    if errors:
        return None, errors, {
            "title": title, "description": description,
            "tarikh": tarikh_raw, "tarikh_tamat": tarikh_tamat_raw,
            "lokasi_nama": lokasi_nama, "lokasi_alamat": lokasi_alamat,
            "organizer_nama": org_nama, "organizer_email": org_email,
            "organizer_telefon": org_tel, "video_ucapan_url": vid_ucapan,
            "video_arah_url": vid_arah, "had_peserta": had,
        }

    try:
        had_int = int(had)
    except ValueError:
        had_int = 0

    if bengkel is None:
        bengkel = Bengkel(created_by=request.user)

    bengkel.title             = title
    bengkel.description       = description
    bengkel.tarikh            = tarikh_dt
    bengkel.tarikh_tamat      = tarikh_tamat_dt
    bengkel.lokasi_nama       = lokasi_nama
    bengkel.lokasi_alamat     = lokasi_alamat
    bengkel.organizer_nama    = org_nama
    bengkel.organizer_email   = org_email
    bengkel.organizer_telefon = org_tel
    bengkel.video_ucapan_url  = vid_ucapan
    bengkel.video_arah_url    = vid_arah
    bengkel.had_peserta       = had_int
    bengkel.save()

    # ── Save tentative items ──────────────────────────────────────────────
    from .models import TentativeBengkel
    masa_list       = request.POST.getlist("tentative_masa")
    aktiviti_list   = request.POST.getlist("tentative_aktiviti")
    penerangan_list = request.POST.getlist("tentative_penerangan")

    # Replace all existing items with submitted ones
    bengkel.tentative.all().delete()
    for i, (masa_val, aktiviti_val) in enumerate(zip(masa_list, aktiviti_list)):
        masa_val     = masa_val.strip()
        aktiviti_val = aktiviti_val.strip()
        if masa_val and aktiviti_val:
            penerangan_val = penerangan_list[i].strip() if i < len(penerangan_list) else ""
            TentativeBengkel.objects.create(
                bengkel=bengkel, masa=masa_val, aktiviti=aktiviti_val,
                penerangan=penerangan_val, urutan=i
            )

    return bengkel, {}, {}


# ── Workshop CRUD ─────────────────────────────────────────────────────────────

@login_required
def penganjur_home(request):
    """Laman utama khas untuk penganjur."""
    if not request.user.is_staff or request.user.is_superuser:
        return redirect("home")

    now = timezone.now()
    bengkel_qs = Bengkel.objects.filter(created_by=request.user)

    total_bengkel   = bengkel_qs.count()
    akan_datang     = bengkel_qs.filter(tarikh__gte=now).order_by("tarikh")
    sudah_lepas     = bengkel_qs.filter(tarikh__lt=now).order_by("-tarikh")
    total_peserta   = Jemputan.objects.filter(bengkel__in=bengkel_qs).count()
    total_hadir     = Kehadiran.objects.filter(jemputan__bengkel__in=bengkel_qs).count()
    total_diterima  = Jemputan.objects.filter(bengkel__in=bengkel_qs, status="accepted").count()

    return render(request, "bengkel/penganjur_home.html", {
        "akan_datang":    akan_datang[:5],
        "sudah_lepas":    sudah_lepas[:3],
        "total_bengkel":  total_bengkel,
        "total_peserta":  total_peserta,
        "total_hadir":    total_hadir,
        "total_diterima": total_diterima,
        "active":         "home",
    })


@login_required
def bengkel_list(request):
    if not request.user.is_staff:
        return redirect("bengkel:dashboard")
    if request.user.is_superuser:
        qs = Bengkel.objects.all()
    else:
        qs = Bengkel.objects.filter(created_by=request.user)
    return render(request, "bengkel/list.html", {"bengkel_list": qs, "active": "bengkel"})


@login_required
def bengkel_create(request):
    if not request.user.is_staff:
        return redirect("bengkel:dashboard")
    if request.method == "POST":
        instance, errors, form_data = _bengkel_form_save(request)
        if instance:
            messages.success(request, f'Bengkel "{instance.title}" berjaya dicipta.')
            return redirect("bengkel:detail", pk=instance.pk)
        return render(request, "bengkel/form.html", {
            "errors": errors, "form_data": form_data,
            "mode": "create", "active": "bengkel", "bengkel": None,
        })
    return render(request, "bengkel/form.html", {"mode": "create", "active": "bengkel", "bengkel": None})


@login_required
def bengkel_detail(request, pk):
    if not request.user.is_staff:
        return redirect("bengkel:dashboard")
    bengkel = get_object_or_404(Bengkel, pk=pk)
    if not request.user.is_superuser and bengkel.created_by != request.user:
        messages.error(request, "Anda tidak mempunyai akses ke bengkel ini.")
        return redirect("bengkel:list")
    jemputan = bengkel.jemputan.prefetch_related("kehadiran").all()
    return render(request, "bengkel/detail.html", {
        "bengkel": bengkel, "jemputan": jemputan, "active": "bengkel",
    })


@login_required
def bengkel_edit(request, pk):
    if not request.user.is_staff:
        return redirect("bengkel:dashboard")
    bengkel = get_object_or_404(Bengkel, pk=pk)
    if not request.user.is_superuser and bengkel.created_by != request.user:
        messages.error(request, "Anda tidak mempunyai akses untuk mengedit bengkel ini.")
        return redirect("bengkel:list")
    if request.method == "POST":
        instance, errors, form_data = _bengkel_form_save(request, bengkel=bengkel)
        if instance:
            messages.success(request, "Maklumat bengkel berjaya dikemaskini.")
            return redirect("bengkel:detail", pk=instance.pk)
        return render(request, "bengkel/form.html", {
            "bengkel": bengkel, "errors": errors, "form_data": form_data,
            "mode": "edit", "active": "bengkel",
        })
    form_data = {
        "title": bengkel.title,
        "description": bengkel.description,
        "tarikh": bengkel.tarikh.strftime("%Y-%m-%dT%H:%M") if bengkel.tarikh else "",
        "tarikh_tamat": bengkel.tarikh_tamat.strftime("%Y-%m-%dT%H:%M") if bengkel.tarikh_tamat else "",
        "lokasi_nama": bengkel.lokasi_nama,
        "lokasi_alamat": bengkel.lokasi_alamat,
        "organizer_nama": bengkel.organizer_nama,
        "organizer_email": bengkel.organizer_email,
        "organizer_telefon": bengkel.organizer_telefon,
        "video_ucapan_url": bengkel.video_ucapan_url,
        "video_arah_url": bengkel.video_arah_url,
        "had_peserta": bengkel.had_peserta,
    }
    return render(request, "bengkel/form.html", {
        "bengkel": bengkel, "mode": "edit", "active": "bengkel", "form_data": form_data,
        "tentative_items": bengkel.tentative.all(),
    })


@login_required
@require_POST
def bengkel_delete(request, pk):
    if not request.user.is_staff:
        return redirect("bengkel:dashboard")
    bengkel = get_object_or_404(Bengkel, pk=pk)
    if not request.user.is_superuser and bengkel.created_by != request.user:
        messages.error(request, "Anda tidak mempunyai akses untuk memadam bengkel ini.")
        return redirect("bengkel:list")
    title = bengkel.title
    bengkel.delete()
    messages.success(request, f'Bengkel "{title}" telah dipadam.')
    return redirect("bengkel:list")


# ── Invitations ───────────────────────────────────────────────────────────────

def _send_jemputan_email(request, j):
    """Send invitation email with accept/reject link. Silently skips if no email."""
    if not j.email:
        return
    try:
        inv_url      = request.build_absolute_uri(f"/bengkel/i/{j.token}/")
        check_in_url = request.build_absolute_uri(f"/bengkel/hadir/{j.qr_token}/")

        buf = io.BytesIO()
        qr_obj = qrcode.QRCode(
            version=None, error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=8, border=2,
        )
        qr_obj.add_data(check_in_url)
        qr_obj.make(fit=True)
        qr_obj.make_image(fill_color="#0f172a", back_color="white").save(buf, format="PNG")
        qr_bytes = buf.getvalue()

        subject   = f"Jemputan Bengkel: {j.bengkel.title}"
        html_body = render_to_string("bengkel/email_jemputan.html", {
            "jemputan": j, "bengkel": j.bengkel,
            "inv_url": inv_url, "check_in_url": check_in_url,
        })
        plain_body = (
            f"Anda dijemput ke {j.bengkel.title}.\n"
            f"Sahkan kehadiran: {inv_url}"
        )
        msg = EmailMultiAlternatives(
            subject=subject, body=plain_body, from_email=None, to=[j.email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.mixed_subtype = "related"
        qr_mime = MIMEImage(qr_bytes)
        qr_mime.add_header("Content-ID", "<jemputan_qr>")
        qr_mime.add_header("Content-Disposition", "inline", filename="jemputan_qr.png")
        msg.attach(qr_mime)
        msg.send(fail_silently=True)
    except Exception:
        pass

@login_required
def jemputan_list(request, pk):
    if not request.user.is_staff:
        return redirect("bengkel:dashboard")
    bengkel = get_object_or_404(Bengkel, pk=pk)
    if not request.user.is_superuser and bengkel.created_by != request.user:
        messages.error(request, "Anda tidak mempunyai akses ke senarai jemputan ini.")
        return redirect("bengkel:list")
    jemputan = bengkel.jemputan.prefetch_related("kehadiran").all()
    base_url = request.build_absolute_uri("/").rstrip("/")
    return render(request, "bengkel/jemputan_list.html", {
        "bengkel": bengkel, "jemputan": jemputan,
        "base_url": base_url, "active": "bengkel",
    })


@login_required
def jemput(request, pk):
    if not request.user.is_staff:
        return redirect("bengkel:dashboard")
    bengkel = get_object_or_404(Bengkel, pk=pk)

    if request.method == "POST":
        action = request.POST.get("action", "individu")

        if action == "individu":
            email = request.POST.get("email", "").strip().lower()

            def _form_err(msg):
                return render(request, "bengkel/jemput_form.html", {
                    "bengkel": bengkel, "active": "bengkel",
                    "individu_error": msg, "individu_email": email,
                })

            if not email:
                return _form_err("Sila masukkan alamat e-mel.")

            # Check user exists
            try:
                target_user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                return _form_err(f"Tiada akaun berdaftar dengan e-mel \"{email}\". Pastikan pengguna sudah mendaftar akaun terlebih dahulu.")

            # Check already invited to this bengkel
            existing = Jemputan.objects.filter(bengkel=bengkel, email__iexact=email).first()
            if existing:
                status_label = {"accepted": "diterima ✓", "rejected": "ditolak ✗", "pending": "belum dijawab"}.get(existing.status, existing.status)
                return _form_err(f"Pengguna ini sudah mempunyai jemputan untuk bengkel ini (status: {status_label}).")

            # Create jemputan pre-filled with user's info
            profile = UserProfile.objects.filter(user=target_user).first()
            j = Jemputan.objects.create(
                bengkel=bengkel,
                dijemput_oleh=request.user,
                user=target_user,
                email=target_user.email,
                nama=target_user.get_full_name() or target_user.username,
                organisasi=profile.organisasi if profile else "",
                jawatan=profile.jabatan if profile else "",
            )
            _send_jemputan_email(request, j)
            messages.success(request, f"Jemputan berjaya dihantar kepada {j.nama} ({j.email}).")
            return redirect("bengkel:jemputan_info", jid=j.pk)

        else:
            # QR untuk semua / fallback count-based
            try:
                count = max(1, min(int(request.POST.get("count", 1)), 1000))
            except (ValueError, TypeError):
                count = 1
            created = [Jemputan.objects.create(bengkel=bengkel, dijemput_oleh=request.user) for _ in range(count)]
            if count == 1:
                return redirect("bengkel:jemputan_info", jid=created[0].pk)
            messages.success(request, f"{count} jemputan berjaya dijana.")
            return redirect("bengkel:jemputan_list", pk=bengkel.pk)

    return render(request, "bengkel/jemput_form.html", {
        "bengkel": bengkel, "active": "bengkel",
    })


@login_required
def jemputan_csv_template(request):
    """Download a blank CSV template for bulk invitations."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="template_jemputan.csv"'
    response.write("\ufeff")  # UTF-8 BOM so Excel opens correctly
    writer = csv.writer(response)
    writer.writerow(["email", "nama", "organisasi", "jawatan"])
    writer.writerow(["ahmad@example.com", "Ahmad bin Abu", "KKM", "Pengurus Projek"])
    writer.writerow(["siti@example.com", "Siti Aminah", "Hospital Putrajaya", "Doktor"])
    return response


@login_required
def jemputan_info(request, jid):
    """Show generated link + QR for a jemputan so staff can copy/share manually."""
    if not request.user.is_staff:
        return redirect("bengkel:dashboard")
    j = get_object_or_404(Jemputan, pk=jid)
    inv_url = request.build_absolute_uri(f"/bengkel/i/{j.token}/")
    return render(request, "bengkel/jemputan_info.html", {
        "jemputan": j, "bengkel": j.bengkel,
        "inv_url": inv_url, "active": "bengkel",
    })


@login_required
@require_POST
def jemputan_delete(request, jid):
    if not request.user.is_staff:
        return redirect("bengkel:dashboard")
    j = get_object_or_404(Jemputan, pk=jid)
    bengkel_pk = j.bengkel_id
    j.delete()
    messages.success(request, "Jemputan telah dibuang.")
    return redirect("bengkel:jemputan_list", pk=bengkel_pk)


@login_required
def jemputan_qr_image(request, jid):
    """Return QR code PNG for a jemputan's check-in URL."""
    if not request.user.is_staff:
        return redirect("bengkel:dashboard")
    j = get_object_or_404(Jemputan, pk=jid)
    check_in_url = request.build_absolute_uri(f"/bengkel/hadir/{j.qr_token}/")

    buf = io.BytesIO()
    qr  = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=3,
    )
    qr.add_data(check_in_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="white")
    img.save(buf, format="PNG")

    return HttpResponse(buf.getvalue(), content_type="image/png")


@login_required
@require_POST
def jemputan_send_email(request, jid):
    """Manually trigger invitation email for a single jemputan."""
    if not request.user.is_staff:
        return redirect("bengkel:dashboard")
    j = get_object_or_404(Jemputan, pk=jid)
    bengkel = j.bengkel

    inv_url      = request.build_absolute_uri(f"/bengkel/i/{j.token}/")
    check_in_url = request.build_absolute_uri(f"/bengkel/hadir/{j.qr_token}/")

    try:
        qr_buf = io.BytesIO()
        qr_obj = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=8,
            border=2,
        )
        qr_obj.add_data(check_in_url)
        qr_obj.make(fit=True)
        qr_pil = qr_obj.make_image(fill_color="#0f172a", back_color="white")
        qr_pil.save(qr_buf, format="PNG")
        qr_bytes = qr_buf.getvalue()

        subject   = f"Jemputan Bengkel: {bengkel.title}"
        html_body = render_to_string("bengkel/email_jemputan.html", {
            "jemputan": j, "bengkel": bengkel,
            "inv_url": inv_url, "check_in_url": check_in_url,
        })
        plain_body = (
            f"Anda dijemput ke {bengkel.title}.\n"
            f"Sahkan kehadiran: {inv_url}"
        )

        msg = EmailMultiAlternatives(
            subject=subject, body=plain_body, from_email=None, to=[j.email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.mixed_subtype = "related"
        qr_mime = MIMEImage(qr_bytes)
        qr_mime.add_header("Content-ID", "<jemputan_qr>")
        qr_mime.add_header("Content-Disposition", "inline", filename="tiket_qr.png")
        msg.attach(qr_mime)
        msg.send(fail_silently=False)
        messages.success(request, f"E-mel jemputan berjaya dihantar kepada {j.nama} ({j.email}).")
    except Exception as exc:
        messages.error(request, f"Gagal hantar e-mel kepada {j.nama}: {exc}")

    return redirect("bengkel:jemputan_list", pk=bengkel.pk)


# ── Open Registration Link ────────────────────────────────────────────────────

def _send_ticket_email(request, j):
    """Send a tiket QR email to the invitee. Silently skips if no email."""
    if not j.email:
        return
    try:
        tiket_url    = request.build_absolute_uri(f"/bengkel/i/{j.token}/tiket/")
        check_in_url = request.build_absolute_uri(f"/bengkel/hadir/{j.qr_token}/")

        # Build QR PNG of the check-in URL
        buf = _io.BytesIO()
        qr_obj = qrcode.QRCode(
            version=None, error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=8, border=2,
        )
        qr_obj.add_data(check_in_url)
        qr_obj.make(fit=True)
        qr_obj.make_image(fill_color="#0f172a", back_color="white").save(buf, format="PNG")
        qr_bytes = buf.getvalue()

        subject    = f"Tiket Anda — {j.bengkel.title}"
        html_body  = render_to_string("bengkel/email_tiket.html", {
            "jemputan": j, "bengkel": j.bengkel,
            "tiket_url": tiket_url, "check_in_url": check_in_url,
        })
        plain_body = (
            f"Terima kasih, {j.nama}!\n\n"
            f"Pendaftaran anda untuk {j.bengkel.title} telah berjaya.\n"
            f"Lihat tiket QR anda: {tiket_url}"
        )
        msg = EmailMultiAlternatives(
            subject=subject, body=plain_body, from_email=None, to=[j.email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.mixed_subtype = "related"
        qr_mime = MIMEImage(qr_bytes)
        qr_mime.add_header("Content-ID", "<tiket_qr>")
        qr_mime.add_header("Content-Disposition", "inline", filename="tiket_qr.png")
        msg.attach(qr_mime)
        msg.send(fail_silently=True)
    except Exception:
        pass  # Never block registration because of email failure

@login_required
def reg_toggle(request, pk):
    """Enable/disable the open registration link for a bengkel."""
    if not request.user.is_staff:
        return redirect("bengkel:dashboard")
    bengkel = get_object_or_404(Bengkel, pk=pk)
    if request.method == "POST":
        bengkel.reg_enabled = not bengkel.reg_enabled
        had = request.POST.get("reg_had", "0")
        try:
            bengkel.reg_had = max(0, int(had))
        except (ValueError, TypeError):
            bengkel.reg_had = 0
        bengkel.save(update_fields=["reg_enabled", "reg_had"])
    return redirect("bengkel:jemputan_list", pk=pk)


@login_required
def reg_reset(request, pk):
    """Generate a fresh registration token, invalidating the old link."""
    if not request.user.is_staff:
        return redirect("bengkel:dashboard")
    bengkel = get_object_or_404(Bengkel, pk=pk)
    if request.method == "POST":
        bengkel.reg_token = uuid.uuid4()
        bengkel.save(update_fields=["reg_token"])
        messages.success(request, "Link pendaftaran awam telah diset semula. Link lama tidak lagi sah.")
    return redirect("bengkel:jemputan_list", pk=pk)


@login_required
def open_reg_info(request, pk):
    """Show the shared open-registration QR + link for a bengkel (staff)."""
    if not request.user.is_staff:
        return redirect("bengkel:dashboard")
    bengkel = get_object_or_404(Bengkel, pk=pk)
    # Auto-enable when staff visits this page
    if not bengkel.reg_enabled:
        bengkel.reg_enabled = True
        bengkel.save(update_fields=["reg_enabled"])
    reg_url = request.build_absolute_uri(f"/bengkel/r/{bengkel.reg_token}/")
    return render(request, "bengkel/open_reg_info.html", {
        "bengkel": bengkel, "reg_url": reg_url, "active": "bengkel",
    })


@login_required
def open_reg_qr_image(request, pk):
    """Return a PNG QR code for the open registration URL."""
    if not request.user.is_staff:
        return redirect("bengkel:dashboard")
    bengkel = get_object_or_404(Bengkel, pk=pk)
    reg_url = request.build_absolute_uri(f"/bengkel/r/{bengkel.reg_token}/")
    buf = _io.BytesIO()
    qr_obj = qrcode.QRCode(
        version=None, error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10, border=3,
    )
    qr_obj.add_data(reg_url)
    qr_obj.make(fit=True)
    qr_pil = qr_obj.make_image(fill_color="#0f172a", back_color="white")
    qr_pil.save(buf, format="PNG")
    return HttpResponse(buf.getvalue(), content_type="image/png")


def open_reg(request, reg_token):
    """Public open-registration page — anyone with the link can self-register."""
    bengkel = get_object_or_404(Bengkel, reg_token=reg_token, reg_enabled=True)

    # Check seat cap
    if bengkel.reg_had > 0:
        registered = Jemputan.objects.filter(bengkel=bengkel).count()
        if registered >= bengkel.reg_had:
            return render(request, "bengkel/open_reg.html", {
                "bengkel": bengkel, "penuh": True,
            })

    if request.method == "POST":
        nama     = request.POST.get("nama", "").strip()
        email    = request.POST.get("email", "").strip()
        username = request.POST.get("username", "").strip()
        org      = request.POST.get("organisasi", "").strip()
        jawatan  = request.POST.get("jawatan", "").strip()
        unit     = request.POST.get("unit", "").strip()
        alamat   = request.POST.get("alamat", "").strip()

        errors = {}
        if not nama:
            errors["nama"] = "Nama penuh wajib diisi."
        if not email:
            errors["email"] = "E-mel wajib diisi."
        if not username:
            errors["username"] = "Nama pengguna wajib diisi."
        elif len(username) < 3:
            errors["username"] = "Nama pengguna mesti sekurang-kurangnya 3 aksara."
        elif User.objects.filter(username=username).exists():
            errors["username"] = "Nama pengguna ini telah digunakan."

        if not errors:
            import random, string, re as _re
            from django.core.mail import EmailMultiAlternatives as _EMA
            from django.conf import settings as _cfg

            # Check for existing active user with same email
            linked_user = User.objects.filter(email__iexact=email, is_active=True).first() if email else None
            new_account_pw = None

            if not linked_user and email:
                # Auto-create a Peserta account using the entered username
                requested_username = username or _re.sub(r'[^\w]', '_', email.split('@')[0])[:24] or "peserta"
                candidate = requested_username
                suffix = 1
                while User.objects.filter(username=candidate).exists():
                    candidate = f"{requested_username}_{suffix}"
                    suffix += 1
                new_account_pw = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
                name_parts = nama.strip().split()
                linked_user = User.objects.create_user(
                    username=candidate,
                    email=email,
                    password=new_account_pw,
                    first_name=name_parts[0] if name_parts else nama,
                    last_name=' '.join(name_parts[1:]) if len(name_parts) > 1 else '',
                    is_active=True,
                )
                from bengkel.models import UserProfile
                profile, _ = UserProfile.objects.get_or_create(user=linked_user)
                profile.organisasi = org
                profile.jabatan    = jawatan
                profile.save()

            j = Jemputan.objects.create(
                bengkel=bengkel,
                nama=nama, email=email, username=username,
                organisasi=org, jawatan=jawatan, unit=unit, alamat=alamat,
                user=linked_user,
                status="accepted",
                responded_at=timezone.now(),
            )
            _send_ticket_email(request, j)

            # Send account credentials email if new account was created
            if new_account_pw and email:
                login_url = request.build_absolute_uri("/login/")
                tiket_url = request.build_absolute_uri(f"/bengkel/i/{j.token}/tiket/")
                try:
                    _html = f"""
                    <div style="font-family:Inter,Arial,sans-serif;max-width:560px;margin:auto;background:#0f172a;
                                color:#e2e8f0;padding:36px 40px;border-radius:16px;">
                      <h2 style="color:#2dd4bf;margin-top:0;">Akaun Peserta Telah Didaftarkan &#127881;</h2>
                      <p>Terima kasih kerana mendaftar untuk <strong>{bengkel.title}</strong>.</p>
                      <p>Akaun sistem telah dicipta secara automatik untuk anda:</p>
                      <div style="background:#1e293b;border-radius:10px;padding:20px 24px;margin:20px 0;
                                  border-left:4px solid #2dd4bf;">
                        <table style="width:100%;border-collapse:collapse;font-size:14px;">
                          <tr><td style="padding:6px 0;color:#94a3b8;width:140px;">Nama Pengguna</td>
                              <td style="padding:6px 0;font-family:monospace;font-size:15px;
                                         color:#f1f5f9;font-weight:700;">{linked_user.username}</td></tr>
                          <tr><td style="padding:6px 0;color:#94a3b8;">Kata Laluan</td>
                              <td style="padding:6px 0;font-family:monospace;font-size:15px;
                                         color:#fbbf24;font-weight:700;">{new_account_pw}</td></tr>
                        </table>
                      </div>
                      <p style="font-size:13px;color:#94a3b8;">
                        Anda <strong style="color:#f87171;">AMAT DISYORKAN</strong> untuk menukar kata laluan
                        selepas log masuk pertama.
                      </p>
                      <div style="display:flex;gap:12px;margin-top:20px;flex-wrap:wrap;">
                        <a href="{login_url}" style="background:#2dd4bf;color:#0f172a;text-decoration:none;
                           font-weight:700;padding:11px 22px;border-radius:9px;font-size:13px;">Log Masuk</a>
                        <a href="{tiket_url}" style="background:#1e293b;color:#94a3b8;text-decoration:none;
                           font-weight:600;padding:11px 22px;border-radius:9px;font-size:13px;
                           border:1px solid #334155;">Lihat Tiket</a>
                      </div>
                      <hr style="border:none;border-top:1px solid #1e293b;margin:28px 0;">
                      <p style="font-size:12px;color:#475569;margin:0;">Sistem Pengurusan Bengkel &middot; NDHB</p>
                    </div>
                    """
                    _txt = (
                        f"Akaun peserta telah dicipta.\n\n"
                        f"Nama Pengguna : {linked_user.username}\n"
                        f"Kata Laluan   : {new_account_pw}\n\n"
                        f"Log masuk: {login_url}\nTiket anda: {tiket_url}"
                    )
                    _msg = _EMA(
                        subject=f"Akaun & Tiket Anda — {bengkel.title}",
                        body=_txt,
                        from_email=getattr(_cfg, "DEFAULT_FROM_EMAIL", "noreply@ndhb.my"),
                        to=[email],
                    )
                    _msg.attach_alternative(_html, "text/html")
                    _msg.send()
                except Exception:
                    pass  # Never block registration because of email failure

            return redirect("bengkel:tiket", token=j.token)

        return render(request, "bengkel/open_reg.html", {
            "bengkel": bengkel, "errors": errors, "post": request.POST,
        })

    return render(request, "bengkel/open_reg.html", {
        "bengkel": bengkel, "errors": {}, "post": {},
    })


# ── QR Scanner & Check-in ─────────────────────────────────────────────────────

@login_required
def qr_scan(request, pk):
    bengkel       = get_object_or_404(Bengkel, pk=pk)
    kehadiran_list = (
        Kehadiran.objects
        .filter(jemputan__bengkel=bengkel)
        .select_related("jemputan", "checked_in_by")
        .order_by("-checked_in_at")
    )
    return render(request, "bengkel/scan.html", {
        "bengkel": bengkel, "kehadiran_list": kehadiran_list, "active": "bengkel",
    })


@login_required
def check_in_api(request, qr_token):
    """AJAX endpoint — called by the scanner page via fetch()."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed."}, status=405)

    try:
        j = Jemputan.objects.select_related("bengkel").prefetch_related("kehadiran").get(qr_token=qr_token)
    except Jemputan.DoesNotExist:
        return JsonResponse({"success": False, "error": "QR kod tidak dikenali."})

    if j.status != "accepted":
        return JsonResponse({
            "success": False,
            "error": f"Jemputan belum diterima (status: {j.get_status_display()}).",
        })

    if j.sudah_hadir:
        return JsonResponse({
            "success": False, "already": True,
            "error": f"{j.nama} sudah daftar masuk pada {j.kehadiran.checked_in_at:%H:%M}.",
        })

    Kehadiran.objects.create(jemputan=j, checked_in_by=request.user)
    return JsonResponse({
        "success": True,
        "nama": j.nama,
        "organisasi": j.organisasi or "–",
        "bengkel": j.bengkel.title,
    })


@login_required
def check_in_staff(request, qr_token):
    """Staff navigates directly to QR URL to mark attendance."""
    try:
        j = Jemputan.objects.select_related("bengkel").prefetch_related("kehadiran").get(qr_token=qr_token)
    except Jemputan.DoesNotExist:
        messages.error(request, "QR kod tidak sah.")
        return redirect("bengkel:list")

    if j.status != "accepted":
        messages.error(request, f"Jemputan ini belum 'Diterima' (status: {j.get_status_display()}).")
        return redirect("bengkel:detail", pk=j.bengkel_id)

    if j.sudah_hadir:
        messages.warning(request, f"{j.nama} sudah daftar masuk pada {j.kehadiran.checked_in_at:%H:%M}.")
    else:
        Kehadiran.objects.create(jemputan=j, checked_in_by=request.user)
        messages.success(request, f"✓ {j.nama} berjaya daftar masuk.")

    return redirect("bengkel:qr_scan", pk=j.bengkel_id)


# ── Public Invitation Pages (no login required) ───────────────────────────────

def invitation_response(request, token):
    j = get_object_or_404(Jemputan, token=token)
    return render(request, "bengkel/response.html", {"jemputan": j, "bengkel": j.bengkel})


def invitation_accept(request, token):
    j = get_object_or_404(Jemputan, token=token)
    if request.method == "POST" and j.status == "pending":
        # Allow invitee to fill in / update their own details
        nama = request.POST.get("nama", "").strip()
        if nama:
            j.nama = nama
        email = request.POST.get("email", "").strip()
        if email:
            j.email = email
        org = request.POST.get("organisasi", "").strip()
        if org:
            j.organisasi = org
        jaw = request.POST.get("jawatan", "").strip()
        if jaw:
            j.jawatan = jaw
        j.status          = "accepted"
        j.responded_at    = timezone.now()
        j.catatan_invitee = request.POST.get("catatan", "").strip()
        j.save()
        _send_ticket_email(request, j)
    return redirect("bengkel:tiket", token=token)


def invitation_reject(request, token):
    j = get_object_or_404(Jemputan, token=token)
    if request.method == "POST" and j.status == "pending":
        j.status        = "rejected"
        j.responded_at  = timezone.now()
        j.catatan_invitee = request.POST.get("catatan", "").strip()
        j.save()
    return redirect("bengkel:response", token=token)


def invitation_ticket(request, token):
    j = get_object_or_404(Jemputan, token=token)
    if j.status != "accepted":
        return redirect("bengkel:response", token=token)
    check_in_url = request.build_absolute_uri(f"/bengkel/hadir/{j.qr_token}/")
    return render(request, "bengkel/tiket.html", {
        "jemputan": j, "bengkel": j.bengkel, "check_in_url": check_in_url,
    })


# ── Public Portal (no login required) — peserta mendaftar sendiri ─────────────

def portal_list(request):
    """Public page listing all upcoming bengkels."""
    from django.utils import timezone
    bengkels = Bengkel.objects.filter(tarikh__gte=timezone.now()).order_by("tarikh")
    return render(request, "bengkel/portal_list.html", {"bengkels": bengkels})


def portal_detail(request, pk):
    """Public detail + self-registration form for a bengkel."""
    bengkel = get_object_or_404(Bengkel, pk=pk)
    penuh = bool(bengkel.had_peserta and bengkel.jumlah_diterima >= bengkel.had_peserta)
    form_data = {
        "nama": "",
        "email": "",
        "username": "",
        "organisasi": "",
        "jawatan": "",
        "unit": "",
        "alamat": "",
    }

    if request.method == "POST":
        nama        = request.POST.get("nama", "").strip()
        email       = request.POST.get("email", "").strip()
        username    = request.POST.get("username", "").strip()
        organisasi  = request.POST.get("organisasi", "").strip()
        jawatan     = request.POST.get("jawatan", "").strip()
        unit        = request.POST.get("unit", "").strip()
        alamat      = request.POST.get("alamat", "").strip()
        form_data = {
            "nama": nama,
            "email": email,
            "username": username,
            "organisasi": organisasi,
            "jawatan": jawatan,
            "unit": unit,
            "alamat": alamat,
        }
        errors = {}
        if penuh:
            errors["__all__"] = "Pendaftaran untuk bengkel ini telah penuh."
        if not nama:  errors["nama"]  = "Nama wajib diisi."
        if not email: errors["email"] = "E-mel wajib diisi."
        if not username: errors["username"] = "Nama pengguna wajib diisi."
        elif len(username) < 3:
            errors["username"] = "Nama pengguna mesti sekurang-kurangnya 3 aksara."
        elif User.objects.filter(username=username).exists():
            errors["username"] = "Nama pengguna ini telah digunakan."

        if not errors:
            if Jemputan.objects.filter(bengkel=bengkel, email__iexact=email).exists():
                errors["email"] = "E-mel ini sudah didaftarkan untuk bengkel ini."
            else:
                j = Jemputan.objects.create(
                    bengkel=bengkel,
                    nama=nama, email=email, username=username,
                    organisasi=organisasi, jawatan=jawatan, unit=unit, alamat=alamat,
                    status="accepted",           # auto-accept self-registration
                    responded_at=timezone.now(),
                )
                return redirect("bengkel:portal_tiket", token=j.token)

        return render(request, "bengkel/portal_detail.html", {
            "bengkel": bengkel,
            "errors": errors,
            "form_data": form_data,
            "penuh": penuh,
        })

    return render(request, "bengkel/portal_detail.html", {
        "bengkel": bengkel,
        "errors": {},
        "form_data": form_data,
        "penuh": penuh,
    })


def portal_tiket(request, token):
    """QR ticket for self-registered attendee."""
    j = get_object_or_404(Jemputan, token=token, status="accepted")
    check_in_url = request.build_absolute_uri(f"/bengkel/hadir/{j.qr_token}/")
    return render(request, "bengkel/tiket.html", {
        "jemputan": j, "bengkel": j.bengkel, "check_in_url": check_in_url,
    })


# ── User Dashboard (login required) ──────────────────────────────────────────

@login_required
def user_dashboard(request):
    """Logged-in user sees all their jemputan."""
    from bengkel.signals import link_jemputan_to_user, ensure_profile
    from django.utils import timezone
    link_jemputan_to_user(request.user)
    ensure_profile(request.user)

    now = timezone.now()

    # Stats count ALL-time jemputan (incl. past)
    all_jemputan = Jemputan.objects.filter(user=request.user)

    from problems.models import ProblemStatement
    stats = {
        "total_jemputan":   all_jemputan.count(),
        "total_diterima":   all_jemputan.filter(status="accepted").count(),
        "total_hadir":      sum(1 for j in all_jemputan.prefetch_related("kehadiran") if j.sudah_hadir),
        "total_pernyataan": ProblemStatement.objects.filter(jemputan__user=request.user).count(),
    }

    # Dashboard shows upcoming + recently past bengkel (within 30 days)
    jemputan_qs = (
        Jemputan.objects
        .filter(user=request.user)
        .filter(bengkel__tarikh__gte=now - timezone.timedelta(days=30))
        .select_related("bengkel")
        .prefetch_related("kehadiran", "pernyataan", "bengkel__tentative")
        .order_by("bengkel__tarikh")
    )

    # Check penganjur request status
    penganjur_req = PenganjurRequest.objects.filter(user=request.user).first()

    return render(request, "bengkel/user_dashboard.html", {
        "jemputan_list": jemputan_qs,
        "stats": stats,
        "active": "dashboard",
        "penganjur_req": penganjur_req,
    })


# ── Edit Profile ──────────────────────────────────────────────────────────────

@login_required
def edit_profile(request):
    from .models import UserProfile
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name  = request.POST.get("last_name", "").strip()
        email      = request.POST.get("email", "").strip()
        telefon    = request.POST.get("telefon", "").strip()
        jabatan    = request.POST.get("jabatan", "").strip()
        organisasi = request.POST.get("organisasi", "").strip()
        unit       = request.POST.get("unit", "").strip()
        alamat     = request.POST.get("alamat", "").strip()

        errors = {}
        if not first_name:
            errors["first_name"] = "Nama pertama wajib diisi."
        if not email:
            errors["email"] = "E-mel wajib diisi."
        elif (
            User.objects.exclude(pk=request.user.pk)
            .filter(email__iexact=email).exists()
        ):
            errors["email"] = "E-mel ini sudah digunakan oleh pengguna lain."

        if errors:
            return render(request, "bengkel/edit_profile.html", {
                "errors":    errors,
                "form_data": request.POST,
                "profile":   profile,
                "back_url":  _home_url(request.user),
            })

        request.user.first_name = first_name
        request.user.last_name  = last_name
        request.user.email      = email
        request.user.save()

        profile.telefon    = telefon
        profile.jabatan    = jabatan
        profile.organisasi = organisasi
        profile.unit       = unit
        profile.alamat     = alamat
        profile.save()

        messages.success(request, "Profil berjaya dikemaskini.")
        return redirect(_home_url(request.user))

    return render(request, "bengkel/edit_profile.html", {
        "profile":  profile,
        "back_url": _home_url(request.user),
        "form_data": {
            "first_name": request.user.first_name,
            "last_name":  request.user.last_name,
            "email":      request.user.email,
            "username":   request.user.username,
            "telefon":    profile.telefon,
            "jabatan":    profile.jabatan,
            "organisasi": profile.organisasi,
            "unit":       profile.unit,
            "alamat":     profile.alamat,
        },
    })


# ── Change Password ───────────────────────────────────────────────────────────

@login_required
def change_password(request):
    if request.method == "POST":
        current  = request.POST.get("current_password", "")
        new_pw   = request.POST.get("new_password", "")
        confirm  = request.POST.get("confirm_password", "")

        errors = {}
        if not request.user.check_password(current):
            errors["current_password"] = "Kata laluan semasa tidak betul."
        if len(new_pw) < 8:
            errors["new_password"] = "Kata laluan baru mestilah sekurang-kurangnya 8 aksara."
        elif new_pw != confirm:
            errors["confirm_password"] = "Pengesahan kata laluan tidak sepadan."

        if errors:
            return render(request, "bengkel/change_password.html", {"errors": errors, "back_url": _home_url(request.user)})

        from django.contrib.auth import update_session_auth_hash
        request.user.set_password(new_pw)
        request.user.save()
        update_session_auth_hash(request, request.user)
        messages.success(request, "Kata laluan berjaya ditukar.")
        return redirect(_home_url(request.user))

    return render(request, "bengkel/change_password.html", {"errors": {}, "back_url": _home_url(request.user)})


# ── Penganjur Approval Request ────────────────────────────────────────────────

@login_required
def peserta_saya(request):
    """Penganjur — see all participants across their own bengkel."""
    if not request.user.is_staff or request.user.is_superuser:
        return redirect("bengkel:dashboard")

    bengkel_qs = Bengkel.objects.filter(created_by=request.user)
    jemputan = (
        Jemputan.objects
        .filter(bengkel__in=bengkel_qs)
        .select_related("bengkel", "user")
        .prefetch_related("kehadiran")
        .order_by("bengkel__tarikh", "nama")
    )

    # Filters
    bengkel_filter = request.GET.get("bengkel", "")
    status_filter  = request.GET.get("status", "")
    cari           = request.GET.get("cari", "").strip()

    if bengkel_filter:
        jemputan = jemputan.filter(bengkel__pk=bengkel_filter)
    if status_filter:
        jemputan = jemputan.filter(status=status_filter)
    if cari:
        jemputan = jemputan.filter(nama__icontains=cari) | jemputan.filter(email__icontains=cari) | jemputan.filter(organisasi__icontains=cari)

    return render(request, "bengkel/peserta_saya.html", {
        "jemputan":       jemputan,
        "bengkel_list":   bengkel_qs,
        "bengkel_filter": bengkel_filter,
        "status_filter":  status_filter,
        "cari":           cari,
        "active":         "peserta",
    })


@login_required
@require_POST
def mohon_penganjur(request):
    """Peserta submits a request to become Penganjur."""
    if request.user.is_staff or request.user.is_superuser:
        return redirect("bengkel:dashboard")

    # One active request at a time
    existing = PenganjurRequest.objects.filter(user=request.user).first()
    if existing and existing.status == "pending":
        messages.warning(request, "Permohonan anda masih dalam semakan.")
        return redirect("bengkel:dashboard")

    # Re-use or create
    sebab = request.POST.get("sebab", "").strip()
    if existing:
        existing.status = "pending"
        existing.sebab  = sebab
        existing.catatan_admin = ""
        existing.save()
    else:
        PenganjurRequest.objects.create(user=request.user, sebab=sebab)

    messages.success(request, "Permohonan anda telah dihantar. Sila tunggu kelulusan daripada admin.")
    return redirect("bengkel:dashboard")


# ── Problem Statement submission by attendee ──────────────────────────────────

def submit_pernyataan(request, token):
    """Attendee submits a problem statement for the bengkel they attended."""
    from problems.models import ProblemStatement
    import re as _re
    from collections import Counter

    STOP_WORDS = {
        "the","a","an","and","or","but","in","on","at","to","for","of","with",
        "by","from","is","are","was","were","be","been","being","have","has",
        "had","do","does","did","will","would","could","should","may","might",
        "shall","can","that","this","these","those","it","its","not","no",
        "so","yet","as","if","when","where","which","who","whom","how","why",
        "what","i","we","you","he","she","they","me","us","him","her","them",
        "my","our","your","his","their","into","than","then","also","more",
        "such","there","about","up","out","all","very","just","each","every",
        "some","other","need","still","even","too","many","much",
    }

    j = get_object_or_404(Jemputan, token=token, status="accepted")
    if not j.sudah_hadir:
        return render(request, "bengkel/submit_pernyataan.html", {
            "jemputan": j, "bengkel": j.bengkel, "belum_hadir": True,
        })

    DOMAINS = [
        "Electronic Medical Records (EMR/EHR)",
        "Telehealth & Telemedicine",
        "Health Information Exchange",
        "Medical Imaging & Diagnostics",
        "Pharmacy & Medication Management",
        "Laboratory Information Systems",
        "Patient Engagement & Mobile Health",
        "Administrative & Billing Systems",
        "Cybersecurity & Data Privacy",
        "Artificial Intelligence & Analytics",
        "IoT & Wearable Devices",
        "Supply Chain & Inventory",
        "Human Resource Management",
        "Interoperability & Standards",
        "Digital Infrastructure & Connectivity",
        "Regulatory & Compliance",
        "Training & Digital Literacy",
        "Other",
    ]

    if request.method == "POST":
        title        = request.POST.get("title", "").strip()
        description  = request.POST.get("description", "").strip()
        domain       = request.POST.get("domain", "").strip()
        priority     = request.POST.get("priority", "medium")
        region       = request.POST.get("region", "").strip()

        errors = {}
        if not title:       errors["title"]       = "Tajuk wajib diisi."
        if not description: errors["description"] = "Penerangan wajib diisi."
        if not domain:      errors["domain"]      = "Domain wajib dipilih."

        if not errors:
            words = _re.findall(r"\b[a-zA-Z]{3,}\b", (title + " " + description).lower())
            keywords = [w for w, _ in Counter([w for w in words if w not in STOP_WORDS]).most_common(10)]

            ps = ProblemStatement.objects.create(
                title=title,
                description=description,
                domain=domain,
                priority=priority,
                region=region,
                submitter_type=j.jawatan or "Peserta Bengkel",
                keywords=keywords,
                word_count=len(description.split()),
                submitted_by=j.user,
                jemputan=j,
            )
            return render(request, "bengkel/submit_pernyataan.html", {
                "jemputan": j, "bengkel": j.bengkel, "berjaya": True, "ps": ps,
            })

        return render(request, "bengkel/submit_pernyataan.html", {
            "jemputan": j, "bengkel": j.bengkel,
            "errors": errors, "domains": DOMAINS,
            "form_data": {"title": title, "description": description,
                          "domain": domain, "priority": priority, "region": region},
        })

    pernyataan_sedia = ProblemStatement.objects.filter(jemputan=j)
    return render(request, "bengkel/submit_pernyataan.html", {
        "jemputan": j, "bengkel": j.bengkel,
        "domains": DOMAINS, "pernyataan_sedia": pernyataan_sedia,
    })


# ─────────────────────────────────────────────────────────────────────────────
# CONTRIBUTION — file upload + comment per peserta
# ─────────────────────────────────────────────────────────────────────────────

def contribute(request, token):
    """Peserta yang sudah hadir boleh upload fail rujukan & tulis ulasan."""
    j = get_object_or_404(Jemputan, token=token, status="accepted")

    if not j.sudah_hadir:
        return render(request, "bengkel/contribute.html", {
            "jemputan": j, "bengkel": j.bengkel, "belum_hadir": True,
        })

    from .models import BengkelContribution, ContributionFile

    contribution, _ = BengkelContribution.objects.get_or_create(
        bengkel=j.bengkel, jemputan=j
    )

    if request.method == "POST":
        # Each uploaded file is paired with a summary: POST sends
        # file_summary_0, file_summary_1, ... alongside the files list.
        files = request.FILES.getlist("files")
        summaries = []
        for i in range(len(files)):
            summaries.append(request.POST.get(f"file_summary_{i}", "").strip())

        for f, summary in zip(files, summaries):
            ContributionFile.objects.create(
                contribution=contribution,
                file=f,
                original_name=f.name,
                summary=summary,
            )

        comment_lines = request.POST.getlist("comment_line")
        comment_raw = request.POST.get("comment", "").strip()
        comment = "\n".join(l.strip() for l in comment_lines if l.strip()) or comment_raw
        if comment:
            contribution.comment = comment
        elif not comment and not files:
            # no input at all — keep existing comment
            pass
        contribution.save()

        messages.success(request, "Sumbangan anda telah disimpan.")

        # Check if ALL accepted+hadir peserta have submitted — if so, trigger LLM
        bengkel = j.bengkel
        hadir_ids = set(
            Kehadiran.objects.filter(jemputan__bengkel=bengkel)
            .values_list("jemputan_id", flat=True)
        )
        submitted_ids = set(
            BengkelContribution.objects.filter(bengkel=bengkel)
            .values_list("jemputan_id", flat=True)
        )
        if hadir_ids and hadir_ids.issubset(submitted_ids):
            import threading
            t = threading.Thread(target=_process_bengkel, args=(bengkel.pk,), daemon=True)
            t.start()

        return redirect("bengkel:contribute", token=token)

    return render(request, "bengkel/contribute.html", {
        "jemputan": j,
        "bengkel": j.bengkel,
        "contribution": contribution,
    })


# ─────────────────────────────────────────────────────────────────────────────
# LLM PROCESSING — collect contributions, call Gemini, generate PDFs
# ─────────────────────────────────────────────────────────────────────────────

def _extract_text_from_file(file_path):
    """Extract plain text from PDF, DOCX, or plain-text files."""
    import os
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".pdf":
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages)
        elif ext in (".docx", ".doc"):
            import docx as _docx
            doc = _docx.Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs)
        else:
            # Try reading as plain text
            with open(file_path, encoding="utf-8", errors="ignore") as fh:
                return fh.read()
    except Exception:
        return ""


def _process_bengkel(bengkel_pk):
    """
    Background task: collect all contributions, call Gemini, generate PDFs.
    Called in a daemon thread when all peserta have submitted.
    """
    import os, json, re as _re
    import django
    django.setup()

    from django.conf import settings as _settings
    from .models import Bengkel, BengkelContribution, BengkelLaporan

    bengkel = Bengkel.objects.get(pk=bengkel_pk)

    # Mark a single "processing" record so UI can show progress
    BengkelLaporan.objects.filter(bengkel=bengkel, status__in=["pending", "failed"]).delete()
    placeholder = BengkelLaporan.objects.create(
        bengkel=bengkel,
        tajuk="Sedang memproses semua sumbangan…",
        status="processing",
    )

    try:
        # ── 1. Collect all contributions ─────────────────────────────────────
        corpus = []
        for contrib in BengkelContribution.objects.filter(bengkel=bengkel).select_related("jemputan"):
            name = contrib.jemputan.nama or "Peserta"
            parts = [f"### Nama: {name}"]
            if contrib.comment:
                parts.append(f"**Ulasan/Pendapat:**\n{contrib.comment}")
            for cf in contrib.files.all():
                abs_path = os.path.join(_settings.MEDIA_ROOT, cf.file.name)
                text = _extract_text_from_file(abs_path)
                file_part = f"**Fail: {cf.original_name}**"
                if cf.summary:
                    file_part += f"\nRingkasan oleh peserta: {cf.summary}"
                if text.strip():
                    file_part += f"\nKandungan fail:\n{text[:5000]}"
                parts.append(file_part)
            corpus.append("\n".join(parts))

        # ── 2. Chunked Gemini processing (50 peserta per batch) ───────────────
        import time
        from google import genai
        client = genai.Client(api_key=_settings.GEMINI_API_KEY)

        BATCH_SIZE = 50
        batch_summaries = []

        def _call_gemini(prompt_text, retries=3):
            for attempt in range(retries):
                try:
                    resp = client.models.generate_content(
                        model="gemini-2.0-flash", contents=prompt_text
                    )
                    return resp.text.strip()
                except Exception as e:
                    if attempt < retries - 1:
                        time.sleep(5)
                    else:
                        raise

        def _strip_fences(text):
            text = _re.sub(r"^```json\s*", "", text, flags=_re.MULTILINE)
            text = _re.sub(r"^```\s*$", "", text, flags=_re.MULTILINE)
            return text.strip()

        # Step A: Summarise each batch of 50
        for i in range(0, len(corpus), BATCH_SIZE):
            batch = corpus[i:i + BATCH_SIZE]
            batch_text = "\n\n---\n\n".join(batch)
            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(corpus) + BATCH_SIZE - 1) // BATCH_SIZE

            placeholder.tajuk = f"Memproses kumpulan {batch_num}/{total_batches}…"
            placeholder.save()

            batch_prompt = f"""
Anda ialah penganalisis bengkel digital kesihatan Malaysia: "{bengkel.title}".
Ini adalah sumbangan daripada kumpulan {batch_num} (peserta {i+1}–{i+len(batch)}).

TUGASAN: Analisis sumbangan dan hasilkan ringkasan structured.
Kembalikan HANYA JSON sah (tanpa markdown, tanpa ```):
{{
  "domains": [
    {{
      "tajuk": "nama domain",
      "isu_utama": ["isu 1", "isu 2"],
      "cadangan": ["cadangan 1"],
      "sumber": ["Nama Peserta: petikan ringkas"],
      "isu_berulang": ["isu yang disebut >1 peserta dalam batch ini"]
    }}
  ]
}}

=== SUMBANGAN ===
{batch_text}
"""
            raw = _call_gemini(batch_prompt)
            raw = _strip_fences(raw)
            try:
                batch_result = json.loads(raw)
                batch_summaries.append(batch_result)
            except json.JSONDecodeError:
                # If JSON fails, store raw text and continue
                batch_summaries.append({"raw": raw, "domains": []})

            # Polite delay to stay within 15 RPM
            if i + BATCH_SIZE < len(corpus):
                time.sleep(4)

        # Step B: Synthesise all batch summaries into final report
        placeholder.tajuk = "Menyatukan semua analisis kumpulan…"
        placeholder.save()

        summaries_text = json.dumps(batch_summaries, ensure_ascii=False, indent=2)

        final_prompt = f"""
Anda ialah penganalisis bengkel digital kesihatan Malaysia: "{bengkel.title}".
Di bawah adalah ringkasan analisis daripada {len(batch_summaries)} kumpulan peserta (jumlah {len(corpus)} peserta).

TUGASAN:
1. Gabungkan semua domains yang serupa/sama.
2. Susun semua isu utama — tandakan isu DUPLIKAT/BERULANG dan nyatakan ia disebut oleh ramai peserta.
3. Senaraikan cadangan terbaik per domain.
4. Tulis ringkasan eksekutif keseluruhan bengkel.

Kembalikan HANYA JSON sah (tanpa markdown, tanpa ```):
{{
  "ringkasan_eksekutif": "...",
  "domains": [
    {{
      "tajuk": "...",
      "isu_utama": ["..."],
      "cadangan": ["..."],
      "sumber": ["..."],
      "isu_duplikat": [
        {{"isu": "...", "disebut_oleh": ["nama1", "nama2"]}}
      ]
    }}
  ]
}}

=== RINGKASAN KUMPULAN ===
{summaries_text[:80000]}
"""
        raw_final = _call_gemini(final_prompt)
        raw_final = _strip_fences(raw_final)
        data = json.loads(raw_final)

        # ── 3. Generate PDFs ──────────────────────────────────────────────────
        from fpdf import FPDF
        import datetime

        placeholder.delete()

        def _make_pdf(tajuk_laporan, ringkasan, domains_subset):
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()

            # Title
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_fill_color(15, 23, 42)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 12, tajuk_laporan[:80], ln=True, fill=True, align="C")
            pdf.ln(4)

            # Bengkel info
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 5, f"Bengkel: {bengkel.title}   |   Laporan dijana: {datetime.date.today()}", ln=True)
            pdf.ln(6)

            # Executive summary (only in summary PDF)
            if ringkasan:
                pdf.set_font("Helvetica", "B", 11)
                pdf.set_text_color(15, 23, 42)
                pdf.cell(0, 7, "Ringkasan Eksekutif", ln=True)
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(50, 50, 50)
                pdf.multi_cell(0, 6, ringkasan.encode("latin-1", "replace").decode("latin-1"))
                pdf.ln(6)

            for domain in domains_subset:
                # Domain heading
                pdf.set_font("Helvetica", "B", 13)
                pdf.set_fill_color(30, 58, 138)
                pdf.set_text_color(255, 255, 255)
                pdf.cell(0, 9, domain["tajuk"][:80].encode("latin-1", "replace").decode("latin-1"),
                         ln=True, fill=True)
                pdf.ln(2)

                # Isu utama
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_text_color(15, 23, 42)
                pdf.cell(0, 6, "Isu Utama:", ln=True)
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(50, 50, 50)
                for isu in domain.get("isu_utama", []):
                    pdf.multi_cell(0, 5, f"  - {isu}".encode("latin-1", "replace").decode("latin-1"))

                # Cadangan
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_text_color(15, 23, 42)
                pdf.cell(0, 6, "Cadangan:", ln=True)
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(50, 50, 50)
                for c in domain.get("cadangan", []):
                    pdf.multi_cell(0, 5, f"  - {c}".encode("latin-1", "replace").decode("latin-1"))

                # Duplikat
                duplikat = domain.get("isu_duplikat", [])
                if duplikat:
                    pdf.ln(2)
                    pdf.set_font("Helvetica", "B", 10)
                    pdf.set_text_color(180, 50, 50)
                    pdf.cell(0, 6, "Isu Bertindih (Telah Digabungkan):", ln=True)
                    pdf.set_font("Helvetica", "I", 9)
                    pdf.set_text_color(120, 40, 40)
                    for d in duplikat:
                        disebut = ", ".join(d.get("disebut_oleh", []))
                        pdf.multi_cell(0, 5,
                            f"  \"{d['isu']}\" — disebut oleh: {disebut}"
                            .encode("latin-1", "replace").decode("latin-1"))

                pdf.ln(6)

            # Save to media
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = tmp.name
            pdf.output(tmp_path)

            import shutil
            from django.core.files import File
            laporan = BengkelLaporan.objects.create(bengkel=bengkel, tajuk=tajuk_laporan, status="done")
            with open(tmp_path, "rb") as f:
                laporan.pdf_file.save(f"laporan_{laporan.pk}.pdf", File(f), save=True)
            os.unlink(tmp_path)

        # One PDF per domain
        for domain in data.get("domains", []):
            _make_pdf(domain["tajuk"], None, [domain])

        # Ringkasan PDF
        _make_pdf(
            f"Ringkasan Eksekutif — {bengkel.title}",
            data.get("ringkasan_eksekutif", ""),
            data.get("domains", [])
        )

    except Exception as exc:
        placeholder.tajuk = "Gagal memproses sumbangan"
        placeholder.status = "failed"
        placeholder.ralat  = str(exc)
        placeholder.save()


# ─────────────────────────────────────────────────────────────────────────────
# LAPORAN — view list of generated PDFs for a bengkel
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def laporan_list(request, pk):
    """Penganjur / peserta views the LLM-generated laporan for a bengkel."""
    bengkel = get_object_or_404(Bengkel, pk=pk)

    from .models import BengkelContribution

    # Only allow: bengkel creator, staff, superuser, or peserta yg hadir
    is_organizer = request.user.is_staff or request.user.is_superuser or bengkel.created_by == request.user
    is_peserta   = Jemputan.objects.filter(bengkel=bengkel, user=request.user, status="accepted").exists()

    if not (is_organizer or is_peserta):
        messages.error(request, "Anda tidak mempunyai akses ke laporan ini.")
        return redirect("bengkel:dashboard")

    laporan   = bengkel.laporan.all()
    hadir_ids = set(Kehadiran.objects.filter(jemputan__bengkel=bengkel).values_list("jemputan_id", flat=True))
    submitted_ids = set(BengkelContribution.objects.filter(bengkel=bengkel).values_list("jemputan_id", flat=True))
    jumlah_hadir     = len(hadir_ids)
    jumlah_submitted = len(submitted_ids & hadir_ids)

    return render(request, "bengkel/laporan_list.html", {
        "bengkel": bengkel,
        "laporan": laporan,
        "jumlah_hadir":     jumlah_hadir,
        "jumlah_submitted": jumlah_submitted,
        "semua_submitted":  hadir_ids and hadir_ids.issubset(submitted_ids),
        "is_organizer":     is_organizer,
    })


# ─────────────────────────────────────────────────────────────────────────────
# TENTATIVE — penganjur urus jadual program
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def tentative_manage(request, pk):
    bengkel = get_object_or_404(Bengkel, pk=pk)
    if not (request.user.is_staff or request.user.is_superuser or bengkel.created_by == request.user):
        messages.error(request, "Akses ditolak.")
        return redirect("bengkel:penganjur_home")

    from .models import TentativeBengkel

    if request.method == "POST":
        masa     = request.POST.get("masa", "").strip()
        aktiviti = request.POST.get("aktiviti", "").strip()
        penerangan = request.POST.get("penerangan", "").strip()
        urutan   = request.POST.get("urutan", "0").strip() or "0"
        if masa and aktiviti:
            TentativeBengkel.objects.create(
                bengkel=bengkel, masa=masa, aktiviti=aktiviti,
                penerangan=penerangan, urutan=int(urutan)
            )
            messages.success(request, "Item tentative berjaya ditambah.")
        else:
            messages.error(request, "Masa dan aktiviti diperlukan.")
        return redirect("bengkel:tentative", pk=pk)

    items = bengkel.tentative.all()
    if request.user.is_superuser:
        from django.urls import reverse
        back_url = reverse("superadmin:detail_bengkel", kwargs={"bid": bengkel.pk})
    else:
        from django.urls import reverse
        back_url = reverse("bengkel:detail", kwargs={"pk": bengkel.pk})
    return render(request, "bengkel/tentative.html", {"bengkel": bengkel, "items": items, "back_url": back_url})


@login_required
@require_POST
def tentative_edit(request, pk, tid):
    bengkel = get_object_or_404(Bengkel, pk=pk)
    if not (request.user.is_staff or request.user.is_superuser or bengkel.created_by == request.user):
        messages.error(request, "Akses ditolak.")
        return redirect("bengkel:penganjur_home")

    from .models import TentativeBengkel
    item = get_object_or_404(TentativeBengkel, pk=tid, bengkel=bengkel)
    masa      = request.POST.get("masa", "").strip()
    aktiviti  = request.POST.get("aktiviti", "").strip()
    penerangan = request.POST.get("penerangan", "").strip()
    urutan    = request.POST.get("urutan", "0").strip() or "0"
    if masa and aktiviti:
        item.masa       = masa
        item.aktiviti   = aktiviti
        item.penerangan = penerangan
        item.urutan     = int(urutan)
        item.save()
        messages.success(request, "Item tentative berjaya dikemaskini.")
    else:
        messages.error(request, "Masa dan aktiviti diperlukan.")
    return redirect("bengkel:tentative", pk=pk)


@login_required
@require_POST
def tentative_delete(request, pk, tid):
    bengkel = get_object_or_404(Bengkel, pk=pk)
    if not (request.user.is_staff or request.user.is_superuser or bengkel.created_by == request.user):
        messages.error(request, "Akses ditolak.")
        return redirect("bengkel:penganjur_home")

    from .models import TentativeBengkel
    item = get_object_or_404(TentativeBengkel, pk=tid, bengkel=bengkel)
    item.delete()
    messages.success(request, "Item tentative berjaya dipadam.")
    return redirect("bengkel:tentative", pk=pk)


# ---------------------------------------------------------------------------
#  SITUATIONAL ANALYSIS VIEWS
# ---------------------------------------------------------------------------

@login_required
def analisis_swot(request):
    from .models import AnalisisSWOT
    existing = AnalisisSWOT.objects.filter(user=request.user).order_by('-created_at')
    saved = None
    if request.method == 'POST':
        saved = AnalisisSWOT.objects.create(
            user=request.user,
            kekuatan=request.POST.get('kekuatan',''),
            kelemahan=request.POST.get('kelemahan',''),
            peluang=request.POST.get('peluang',''),
            ancaman=request.POST.get('ancaman',''),
            catatan=request.POST.get('catatan',''),
        )
        messages.success(request, 'Analisis SWOT berjaya disimpan.')
        return redirect('bengkel:analisis_swot')
    return render(request, 'bengkel/analisis/swot.html', {'existing': existing, 'saved': saved})


@login_required
def analisis_swot_delete(request, pk):
    from .models import AnalisisSWOT
    obj = get_object_or_404(AnalisisSWOT, pk=pk, user=request.user)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Analisis SWOT dipadam.')
    return redirect('bengkel:analisis_swot')


@login_required
def analisis_pestel(request):
    from .models import AnalisisPESTEL
    existing = AnalisisPESTEL.objects.filter(user=request.user).order_by('-created_at')
    if request.method == 'POST':
        AnalisisPESTEL.objects.create(
            user=request.user,
            politik=request.POST.get('politik',''),
            ekonomi=request.POST.get('ekonomi',''),
            sosial=request.POST.get('sosial',''),
            teknologi=request.POST.get('teknologi',''),
            alam_sekitar=request.POST.get('alam_sekitar',''),
            undang_undang=request.POST.get('undang_undang',''),
            catatan=request.POST.get('catatan',''),
        )
        messages.success(request, 'Analisis PESTEL berjaya disimpan.')
        return redirect('bengkel:analisis_pestel')
    return render(request, 'bengkel/analisis/pestel.html', {'existing': existing})


@login_required
def analisis_pestel_delete(request, pk):
    from .models import AnalisisPESTEL
    obj = get_object_or_404(AnalisisPESTEL, pk=pk, user=request.user)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Analisis PESTEL dipadam.')
    return redirect('bengkel:analisis_pestel')


@login_required
def analisis_vmost(request):
    from .models import AnalisisVMOST
    existing = AnalisisVMOST.objects.filter(user=request.user).order_by('-created_at')
    if request.method == 'POST':
        AnalisisVMOST.objects.create(
            user=request.user,
            visi=request.POST.get('visi',''),
            misi=request.POST.get('misi',''),
            objektif=request.POST.get('objektif',''),
            strategi=request.POST.get('strategi',''),
            taktik=request.POST.get('taktik',''),
            catatan=request.POST.get('catatan',''),
        )
        messages.success(request, 'Analisis VMOST berjaya disimpan.')
        return redirect('bengkel:analisis_vmost')
    return render(request, 'bengkel/analisis/vmost.html', {'existing': existing})


@login_required
def analisis_vmost_delete(request, pk):
    from .models import AnalisisVMOST
    obj = get_object_or_404(AnalisisVMOST, pk=pk, user=request.user)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Analisis VMOST dipadam.')
    return redirect('bengkel:analisis_vmost')


@login_required
def analisis_5c(request):
    from .models import Analisis5C
    existing = Analisis5C.objects.filter(user=request.user).order_by('-created_at')
    if request.method == 'POST':
        Analisis5C.objects.create(
            user=request.user,
            syarikat=request.POST.get('syarikat',''),
            pelanggan=request.POST.get('pelanggan',''),
            pesaing=request.POST.get('pesaing',''),
            rakan_kongsi=request.POST.get('rakan_kongsi',''),
            persekitaran=request.POST.get('persekitaran',''),
            catatan=request.POST.get('catatan',''),
        )
        messages.success(request, 'Analisis 5C berjaya disimpan.')
        return redirect('bengkel:analisis_5c')
    return render(request, 'bengkel/analisis/5c.html', {'existing': existing})


@login_required
def analisis_5c_delete(request, pk):
    from .models import Analisis5C
    obj = get_object_or_404(Analisis5C, pk=pk, user=request.user)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Analisis 5C dipadam.')
    return redirect('bengkel:analisis_5c')


@login_required
def analisis_soar(request):
    from .models import AnalisisSOAR
    existing = AnalisisSOAR.objects.filter(user=request.user).order_by('-created_at')
    if request.method == 'POST':
        AnalisisSOAR.objects.create(
            user=request.user,
            kekuatan=request.POST.get('kekuatan',''),
            peluang=request.POST.get('peluang',''),
            aspirasi=request.POST.get('aspirasi',''),
            keputusan=request.POST.get('keputusan',''),
            catatan=request.POST.get('catatan',''),
        )
        messages.success(request, 'Analisis SOAR berjaya disimpan.')
        return redirect('bengkel:analisis_soar')
    return render(request, 'bengkel/analisis/soar.html', {'existing': existing})


@login_required
def analisis_soar_delete(request, pk):
    from .models import AnalisisSOAR
    obj = get_object_or_404(AnalisisSOAR, pk=pk, user=request.user)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Analisis SOAR dipadam.')
    return redirect('bengkel:analisis_soar')


@login_required
def blueprint_peserta(request, pk):
    """User-facing blueprint progress page — main activity hub for participants."""
    from .models import BengkelContribution, ContributionFile, SpafPainPoint, SpafProblemStatement, BlueprintTheme

    bengkel   = get_object_or_404(Bengkel, pk=pk)
    jemputan  = get_object_or_404(Jemputan, bengkel=bengkel, user=request.user, status="accepted")
    bp_url    = reverse("bengkel:blueprint_peserta", kwargs={"pk": pk})

    if request.method == "POST":
        action = request.POST.get("action", "")

        # ── Upload file rujukan ─────────────────────────────────────────────
        if action == "upload_file":
            if not jemputan.sudah_hadir:
                messages.error(request, "Anda perlu hadir ke bengkel dahulu sebelum boleh muat naik rujukan.")
            else:
                contribution, _ = BengkelContribution.objects.get_or_create(
                    bengkel=bengkel, jemputan=jemputan
                )
                files     = request.FILES.getlist("files")
                summaries = [request.POST.get("file_summary_%d" % i, "").strip() for i in range(len(files))]
                for f, summary in zip(files, summaries):
                    ContributionFile.objects.create(
                        contribution=contribution,
                        file=f,
                        original_name=f.name,
                        summary=summary,
                    )
                if files:
                    messages.success(request, "%d fail berjaya dimuat naik." % len(files))
            return redirect(bp_url + "?tab=rujukan")

        # ── Delete contribution file ────────────────────────────────────────
        elif action == "del_file":
            fid = request.POST.get("file_id")
            try:
                cf = ContributionFile.objects.get(pk=fid, contribution__jemputan=jemputan)
                cf.delete()
                messages.success(request, "Fail dipadam.")
            except ContributionFile.DoesNotExist:
                pass
            return redirect(bp_url + "?tab=rujukan")

        # ── Save Pain Points + AI generate Problem Statement ───────────────
        elif action == "pain_point":
            raw_pps = [p.strip() for p in request.POST.getlist("pain_point") if p.strip()]
            if not raw_pps:
                messages.error(request, "Sila isi sekurang-kurangnya satu Pain Point.")
                return redirect(bp_url + "?tab=spaf")
            for i, text in enumerate(raw_pps, 1):
                SpafPainPoint.objects.create(
                    user=request.user,
                    tajuk="Pain Point %d" % i,
                    keterangan=text,
                    kesan="",
                    keutamaan="sederhana",
                    catatan="",
                )
            messages.success(request, "%d Pain Point disimpan. AI sedang jana cadangan Problem Statement..." % len(raw_pps))
            try:
                import json
                from google import genai as _genai
                from django.conf import settings as _cfg
                _client = _genai.Client(api_key=_cfg.GEMINI_API_KEY)
                sep = "\n"
                pp_list = sep.join("%d. %s" % (i, t) for i, t in enumerate(raw_pps, 1))
                _prompt = (
                    "Anda adalah pakar analisis masalah dalam konteks organisasi sektor awam Malaysia."
                    + sep
                    + sep
                    + "Berdasarkan senarai Pain Point berikut, jana SATU ayat Pernyataan Masalah Utama dalam BAHASA MELAYU yang jelas, padat, dan tepat."
                    + sep
                    + sep
                    + "Senarai Pain Point:"
                    + sep
                    + pp_list
                    + sep
                    + sep
                    + "Jana respons dalam format JSON SAHAJA (tanpa markdown, tanpa ```json), dengan satu medan:"
                    + sep
                    + '{"masalah_utama":"..."}'
                )
                _MODELS = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-2.0-flash"]
                ai_raw = None
                for _m in _MODELS:
                    try:
                        ai_raw = _client.models.generate_content(model=_m, contents=_prompt).text.strip()
                        break
                    except Exception:
                        continue
                if ai_raw:
                    if ai_raw.startswith("```"):
                        ai_raw = ai_raw.split(sep, 1)[1].rsplit("```", 1)[0].strip()
                    request.session["spaf_generated_ps"] = json.loads(ai_raw)
                    request.session["spaf_ai_error"] = None
            except Exception as _e:
                request.session["spaf_ai_error"] = str(_e)
            request.session.modified = True
            return redirect(bp_url + "?tab=spaf")

        # ── Delete Pain Point ───────────────────────────────────────────────
        elif action == "del_pp":
            pid = request.POST.get("pp_id")
            SpafPainPoint.objects.filter(pk=pid, user=request.user).delete()
            return redirect(bp_url + "?tab=spaf")

        # ── Save Problem Statement (manual or from AI suggestion) ──────────
        elif action == "save_ps":
            SpafProblemStatement.objects.create(
                user=request.user,
                masalah_utama=request.POST.get("masalah_utama", ""),
                skop=request.POST.get("skop", ""),
                sasaran=request.POST.get("sasaran", ""),
                matlamat=request.POST.get("matlamat", ""),
                catatan=request.POST.get("catatan", ""),
            )
            messages.success(request, "Problem Statement berjaya disimpan.")
            request.session.pop("spaf_generated_ps", None)
            request.session.modified = True
            return redirect(bp_url + "?tab=spaf")

        # ── Delete Problem Statement ────────────────────────────────────────
        elif action == "del_ps":
            pid = request.POST.get("ps_id")
            SpafProblemStatement.objects.filter(pk=pid, user=request.user).delete()
            return redirect(bp_url + "?tab=spaf")

        # ── Generate Tema from Problem Statements (AI) — auto-save ────────
        elif action == "generate_tema":
            ps_qs = SpafProblemStatement.objects.filter(user=request.user).values_list("masalah_utama", flat=True)
            if not ps_qs.exists():
                messages.error(request, "Sila masukkan sekurang-kurangnya satu Problem Statement dahulu.")
                return redirect(bp_url + "?tab=tema")
            try:
                import json
                from google import genai as _genai
                from django.conf import settings as _cfg
                _client = _genai.Client(api_key=_cfg.GEMINI_API_KEY)
                sep = "\n"
                ps_list = sep.join("%d. %s" % (i, t) for i, t in enumerate(ps_qs, 1))
                _prompt = (
                    "Anda adalah pakar perancangan strategik sektor awam Malaysia."
                    + sep + sep
                    + "Berdasarkan senarai Pernyataan Masalah Utama berikut, kenal pasti dan jana TEMA-TEMA UTAMA dalam BAHASA MELAYU."
                    + sep + sep
                    + "Senarai Pernyataan Masalah:"
                    + sep + ps_list
                    + sep + sep
                    + "Jana antara 2 hingga 5 tema. Setiap tema mesti merangkumi beberapa masalah yang berkait."
                    + sep
                    + "Jana respons dalam format JSON array SAHAJA (tanpa markdown, tanpa ```json), contoh:"
                    + sep
                    + '[{"tema":"...","penerangan":"...","kata_kunci":"..."},{"tema":"...","penerangan":"...","kata_kunci":"..."}]'
                )
                _MODELS = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-2.0-flash"]
                ai_raw = None
                for _m in _MODELS:
                    try:
                        ai_raw = _client.models.generate_content(model=_m, contents=_prompt).text.strip()
                        break
                    except Exception:
                        continue
                if ai_raw:
                    if ai_raw.startswith("```"):
                        ai_raw = ai_raw.split(sep, 1)[1].rsplit("```", 1)[0].strip()
                    parsed = json.loads(ai_raw)
                    # Normalise: single dict → wrap in list
                    if isinstance(parsed, dict):
                        parsed = [parsed]
                    # Save immediately to DB
                    bengkel.blueprint_themes.all().delete()
                    for i, t in enumerate(parsed, 1):
                        BlueprintTheme.objects.create(
                            bengkel=bengkel,
                            urutan=i,
                            tema=t.get("tema", ""),
                            penerangan=t.get("penerangan", ""),
                            kata_kunci=t.get("kata_kunci", ""),
                            frequency=1,
                        )
                    messages.success(request, "%d tema berjaya dijana dan disimpan." % len(parsed))
                else:
                    messages.error(request, "AI tidak memberikan respons. Cuba lagi.")
            except Exception as _e:
                messages.error(request, "AI gagal jana tema: %s" % str(_e))
            return redirect(bp_url + "?tab=tema")

        # ── Delete a single Tema ────────────────────────────────────────────
        elif action == "del_tema":
            tid = request.POST.get("tema_id")
            BlueprintTheme.objects.filter(pk=tid, bengkel=bengkel).delete()
            return redirect(bp_url + "?tab=tema")

    pain_points     = SpafPainPoint.objects.filter(user=request.user).order_by("-created_at")
    prob_stmts      = SpafProblemStatement.objects.filter(user=request.user).order_by("-created_at")
    contribution    = getattr(jemputan, "contribution", None)
    themes          = bengkel.blueprint_themes.all()
    generated       = request.session.pop("spaf_generated_ps", None)
    ai_error        = request.session.pop("spaf_ai_error", None)
    request.session.modified = True
    active_tab      = request.GET.get("tab", "rujukan")

    return render(request, "bengkel/blueprint_peserta.html", {
        "bengkel":      bengkel,
        "jemputan":     jemputan,
        "pain_points":  pain_points,
        "prob_stmts":   prob_stmts,
        "contribution": contribution,
        "themes":       themes,
        "generated":    generated,
        "ai_error":     ai_error,
        "active_tab":   active_tab,
    })


# ── SPAF standalone stubs (consolidated into blueprint page) ──────────────────

@login_required
def spaf_hub(request):
    return redirect("bengkel:dashboard")

@login_required
def spaf_pain_point(request):
    return redirect("bengkel:dashboard")

@login_required
def spaf_pain_point_delete(request, pk):
    return redirect("bengkel:dashboard")

@login_required
def spaf_problem_statement(request):
    return redirect("bengkel:dashboard")

@login_required
def spaf_problem_statement_delete(request, pk):
    return redirect("bengkel:dashboard")

@login_required
def spaf_rca(request):
    return redirect("bengkel:dashboard")

@login_required
def spaf_rca_delete(request, pk):
    return redirect("bengkel:dashboard")

@login_required
def spaf_rcv(request):
    return redirect("bengkel:dashboard")

@login_required
def spaf_rcv_delete(request, pk):
    return redirect("bengkel:dashboard")

@login_required
def spaf_risk(request):
    return redirect("bengkel:dashboard")

@login_required
def spaf_risk_delete(request, pk):
    return redirect("bengkel:dashboard")

