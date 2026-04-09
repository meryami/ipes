import uuid
from django.db import models
from django.contrib.auth.models import User


class Bengkel(models.Model):
    title             = models.CharField(max_length=255)
    description       = models.TextField(blank=True)
    tarikh            = models.DateTimeField()
    tarikh_tamat      = models.DateTimeField(null=True, blank=True)
    lokasi_nama       = models.CharField(max_length=300)
    lokasi_alamat     = models.TextField(blank=True)
    organizer_nama    = models.CharField(max_length=200)
    organizer_email   = models.EmailField(blank=True)
    organizer_telefon = models.CharField(max_length=30, blank=True)
    video_ucapan_url  = models.URLField(blank=True)   # alu-aluan / welcome speech
    video_arah_url    = models.URLField(blank=True)   # directions to hall
    had_peserta       = models.PositiveIntegerField(default=0)  # 0 = no limit
    # Open registration link (one link, many people)
    reg_token         = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    reg_enabled       = models.BooleanField(default=False)
    reg_had           = models.PositiveIntegerField(default=0)  # 0 = no extra cap
    created_by        = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="bengkel_dicipta"
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering         = ["-tarikh"]
        verbose_name     = "Bengkel"
        verbose_name_plural = "Senarai Bengkel"

    def __str__(self):
        return self.title

    @property
    def jumlah_jemputan(self):
        return self.jemputan.count()

    @property
    def jumlah_diterima(self):
        return self.jemputan.filter(status="accepted").count()

    @property
    def jumlah_ditolak(self):
        return self.jemputan.filter(status="rejected").count()

    @property
    def jumlah_menunggu(self):
        return self.jemputan.filter(status="pending").count()

    @property
    def jumlah_hadir(self):
        return Kehadiran.objects.filter(jemputan__bengkel=self).count()

    def _youtube_embed(self, url):
        """Convert YouTube watch/short URL to embed URL."""
        if not url:
            return url
        if "youtube.com/watch?v=" in url:
            vid = url.split("watch?v=")[1].split("&")[0]
            return f"https://www.youtube.com/embed/{vid}"
        if "youtu.be/" in url:
            vid = url.split("youtu.be/")[1].split("?")[0]
            return f"https://www.youtube.com/embed/{vid}"
        return url

    @property
    def video_ucapan_embed(self):
        return self._youtube_embed(self.video_ucapan_url)

    @property
    def video_arah_embed(self):
        return self._youtube_embed(self.video_arah_url)


class Jemputan(models.Model):
    STATUS_CHOICES = [
        ("pending",  "Menunggu"),
        ("accepted", "Diterima"),
        ("rejected", "Ditolak"),
    ]

    bengkel          = models.ForeignKey(Bengkel, on_delete=models.CASCADE, related_name="jemputan")
    nama             = models.CharField(max_length=200, blank=True)
    email            = models.EmailField(blank=True)
    organisasi       = models.CharField(max_length=200, blank=True)
    jawatan          = models.CharField(max_length=200, blank=True)
    # Linked user account (auto-linked when user logs in with same email)
    user             = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="jemputan"
    )
    # Unique tokens
    token            = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    qr_token         = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    # State
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    dijemput_oleh    = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="jemputan_dihantar"
    )
    responded_at     = models.DateTimeField(null=True, blank=True)
    catatan_invitee  = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering            = ["-created_at"]
        verbose_name        = "Jemputan"
        verbose_name_plural = "Senarai Jemputan"

    def __str__(self):
        return f"{self.nama} — {self.bengkel.title}"

    @property
    def sudah_hadir(self):
        return hasattr(self, "kehadiran")


class Kehadiran(models.Model):
    jemputan       = models.OneToOneField(Jemputan, on_delete=models.CASCADE, related_name="kehadiran")
    checked_in_at  = models.DateTimeField(auto_now_add=True)
    checked_in_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="check_ins"
    )

    class Meta:
        verbose_name        = "Kehadiran"
        verbose_name_plural = "Rekod Kehadiran"

    def __str__(self):
        return f"{self.jemputan.nama} — {self.checked_in_at:%d/%m/%Y %H:%M}"


class UserProfile(models.Model):
    user        = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    telefon     = models.CharField(max_length=30, blank=True)
    jabatan     = models.CharField(max_length=200, blank=True)
    organisasi  = models.CharField(max_length=200, blank=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Profil Pengguna"
        verbose_name_plural = "Profil Pengguna"

    def __str__(self):
        return f"Profil {self.user.username}"


class PenganjurRequest(models.Model):
    STATUS_CHOICES = [
        ("pending",  "Menunggu Semakan"),
        ("approved", "Diluluskan"),
        ("rejected", "Ditolak"),
    ]

    user            = models.OneToOneField(User, on_delete=models.CASCADE, related_name="penganjur_request")
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    sebab           = models.TextField(blank=True, help_text="Sebab permohonan (ditulis oleh pemohon)")
    catatan_admin   = models.TextField(blank=True, help_text="Catatan semakan admin")
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Permohonan Penganjur"
        verbose_name_plural = "Permohonan Penganjur"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} — {self.get_status_display()}"


# ── Contribution (file upload + comment) ─────────────────────────────────────

class BengkelContribution(models.Model):
    bengkel      = models.ForeignKey(Bengkel, on_delete=models.CASCADE, related_name="contributions")
    jemputan     = models.OneToOneField(Jemputan, on_delete=models.CASCADE, related_name="contribution")
    comment      = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Sumbangan Peserta"
        verbose_name_plural = "Sumbangan Peserta"
        ordering            = ["submitted_at"]

    def __str__(self):
        return f"{self.jemputan.nama} — {self.bengkel.title}"


class ContributionFile(models.Model):
    contribution  = models.ForeignKey(BengkelContribution, on_delete=models.CASCADE, related_name="files")
    file          = models.FileField(upload_to="contributions/%Y/%m/")
    original_name = models.CharField(max_length=255)
    summary       = models.TextField(blank=True)   # per-file comment/summary
    uploaded_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return self.original_name


# ── LLM-generated laporan (PDF per domain) ───────────────────────────────────

class TentativeBengkel(models.Model):
    bengkel    = models.ForeignKey(Bengkel, on_delete=models.CASCADE, related_name="tentative")
    masa       = models.CharField(max_length=50, help_text="Contoh: 08:00 - 09:00")
    aktiviti   = models.CharField(max_length=300)
    penerangan = models.TextField(blank=True)
    urutan     = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Tentative"
        verbose_name_plural = "Tentative Bengkel"
        ordering            = ["urutan", "created_at"]

    def __str__(self):
        return f"{self.masa} — {self.aktiviti}"


class BengkelLaporan(models.Model):
    STATUS_CHOICES = [
        ("pending",    "Menunggu"),
        ("processing", "Sedang Diproses"),
        ("done",       "Selesai"),
        ("failed",     "Gagal"),
    ]

    bengkel      = models.ForeignKey(Bengkel, on_delete=models.CASCADE, related_name="laporan")
    tajuk        = models.CharField(max_length=300)
    pdf_file     = models.FileField(upload_to="laporan/%Y/%m/", blank=True)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    ralat        = models.TextField(blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering            = ["generated_at"]
        verbose_name        = "Laporan Bengkel"
        verbose_name_plural = "Laporan Bengkel"

    def __str__(self):
        return f"{self.bengkel.title} — {self.tajuk}"


# ── Situational Analysis Tools ───────────────────────────────────────────────

class AnalisisSWOT(models.Model):
    bengkel     = models.ForeignKey(Bengkel, on_delete=models.CASCADE, related_name="swot_set", null=True, blank=True)
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name="swot_set")
    kekuatan    = models.TextField(verbose_name="Kekuatan (Strengths)")
    kelemahan   = models.TextField(verbose_name="Kelemahan (Weaknesses)")
    peluang     = models.TextField(verbose_name="Peluang (Opportunities)")
    ancaman     = models.TextField(verbose_name="Ancaman (Threats)")
    catatan     = models.TextField(blank=True, verbose_name="Catatan Tambahan")
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Analisis SWOT"
        verbose_name_plural = "Analisis SWOT"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"SWOT — {self.user.get_full_name() or self.user.username} ({self.created_at:%d/%m/%Y})"


class AnalisisPESTEL(models.Model):
    bengkel     = models.ForeignKey(Bengkel, on_delete=models.CASCADE, related_name="pestel_set", null=True, blank=True)
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pestel_set")
    politik     = models.TextField(verbose_name="Faktor Politik (Political)")
    ekonomi     = models.TextField(verbose_name="Faktor Ekonomi (Economic)")
    sosial      = models.TextField(verbose_name="Faktor Sosial (Social)")
    teknologi   = models.TextField(verbose_name="Faktor Teknologi (Technological)")
    alam_sekitar = models.TextField(verbose_name="Faktor Alam Sekitar (Environmental)")
    undang_undang = models.TextField(verbose_name="Faktor Undang-Undang (Legal)")
    catatan     = models.TextField(blank=True, verbose_name="Catatan Tambahan")
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Analisis PESTEL"
        verbose_name_plural = "Analisis PESTEL"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"PESTEL — {self.user.get_full_name() or self.user.username} ({self.created_at:%d/%m/%Y})"


class AnalisisVMOST(models.Model):
    bengkel     = models.ForeignKey(Bengkel, on_delete=models.CASCADE, related_name="vmost_set", null=True, blank=True)
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name="vmost_set")
    visi        = models.TextField(verbose_name="Visi (Vision)")
    misi        = models.TextField(verbose_name="Misi (Mission)")
    objektif    = models.TextField(verbose_name="Objektif (Objectives)")
    strategi    = models.TextField(verbose_name="Strategi (Strategy)")
    taktik      = models.TextField(verbose_name="Taktik (Tactics)")
    catatan     = models.TextField(blank=True, verbose_name="Catatan Tambahan")
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Analisis VMOST"
        verbose_name_plural = "Analisis VMOST"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"VMOST — {self.user.get_full_name() or self.user.username} ({self.created_at:%d/%m/%Y})"


class Analisis5C(models.Model):
    bengkel         = models.ForeignKey(Bengkel, on_delete=models.CASCADE, related_name="fivec_set", null=True, blank=True)
    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name="fivec_set")
    syarikat        = models.TextField(verbose_name="Syarikat/Organisasi (Company)")
    pelanggan       = models.TextField(verbose_name="Pelanggan (Customers)")
    pesaing         = models.TextField(verbose_name="Pesaing (Competitors)")
    rakan_kongsi    = models.TextField(verbose_name="Rakan Kongsi (Collaborators)")
    persekitaran    = models.TextField(verbose_name="Persekitaran (Climate)")
    catatan         = models.TextField(blank=True, verbose_name="Catatan Tambahan")
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Analisis 5C"
        verbose_name_plural = "Analisis 5C"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"5C — {self.user.get_full_name() or self.user.username} ({self.created_at:%d/%m/%Y})"


class AnalisisSOAR(models.Model):
    bengkel     = models.ForeignKey(Bengkel, on_delete=models.CASCADE, related_name="soar_set", null=True, blank=True)
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name="soar_set")
    kekuatan    = models.TextField(verbose_name="Kekuatan (Strengths)")
    peluang     = models.TextField(verbose_name="Peluang (Opportunities)")
    aspirasi    = models.TextField(verbose_name="Aspirasi (Aspirations)")
    keputusan   = models.TextField(verbose_name="Keputusan/Hasil (Results)")
    catatan     = models.TextField(blank=True, verbose_name="Catatan Tambahan")
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Analisis SOAR"
        verbose_name_plural = "Analisis SOAR"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"SOAR — {self.user.get_full_name() or self.user.username} ({self.created_at:%d/%m/%Y})"
