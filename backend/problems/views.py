import re
import json
from collections import Counter

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login
from django.db.models import Count, Avg
from django.views.decorators.http import require_POST

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import ProblemStatement
from .serializers import ProblemStatementSerializer, VALID_DOMAINS, VALID_SUBMITTER_TYPES
from bengkel.models import UserProfile, PenganjurRequest

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "that", "this",
    "these", "those", "it", "its", "not", "no", "so", "yet", "as", "if",
    "when", "where", "which", "who", "whom", "how", "why", "what", "i",
    "we", "you", "he", "she", "they", "me", "us", "him", "her", "them",
    "my", "our", "your", "his", "their", "into", "than", "then", "also",
    "more", "such", "there", "about", "up", "out", "all", "very", "just",
    "each", "every", "some", "other", "need", "still", "even", "too",
    "many", "much",
}


def extract_keywords(text: str, top_n: int = 10):
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    filtered = [w for w in words if w not in STOP_WORDS]
    return [word for word, _ in Counter(filtered).most_common(top_n)]


def count_words(text: str) -> int:
    return len(text.split())


# ─── Problem Statement endpoints ──────────────────────────────────────────────

@api_view(["GET", "POST"])
def problem_list_create(request):
    if request.method == "GET":
        qs = ProblemStatement.objects.all()
        domain = request.query_params.get("domain")
        priority = request.query_params.get("priority")
        if domain:
            qs = qs.filter(domain=domain)
        if priority:
            qs = qs.filter(priority=priority)
        serializer = ProblemStatementSerializer(qs, many=True)
        return Response(serializer.data)

    # POST
    serializer = ProblemStatementSerializer(data=request.data)
    if serializer.is_valid():
        title = serializer.validated_data["title"]
        description = serializer.validated_data["description"]
        keywords = extract_keywords(f"{title} {description}")
        wc = count_words(description)
        instance = serializer.save(keywords=keywords, word_count=wc)
        return Response(ProblemStatementSerializer(instance).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "DELETE"])
def problem_detail(request, pk):
    try:
        problem = ProblemStatement.objects.get(pk=pk)
    except ProblemStatement.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(ProblemStatementSerializer(problem).data)

    problem.delete()
    return Response({"message": "Deleted successfully."}, status=status.HTTP_200_OK)


# ─── Data Profile endpoint ────────────────────────────────────────────────────

@api_view(["GET"])
def data_profile(request):
    problems = list(ProblemStatement.objects.all().order_by("created_at"))

    if not problems:
        return Response({
            "total_submissions": 0,
            "domain_distribution": [],
            "priority_distribution": [],
            "submitter_distribution": [],
            "region_distribution": [],
            "avg_word_count": 0,
            "min_word_count": 0,
            "max_word_count": 0,
            "total_word_count": 0,
            "top_keywords": [],
            "submissions_timeline": [],
            "quality_metrics": {
                "completeness_rate": 0,
                "avg_description_length": 0,
                "domains_covered": 0,
                "unique_regions": 0,
            },
        })

    domain_dist: dict = {}
    priority_dist: dict = {}
    submitter_dist: dict = {}
    region_dist: dict = {}
    all_keywords: list = []
    word_counts: list = []
    timeline: dict = {}
    complete_count = 0

    for p in problems:
        domain_dist[p.domain] = domain_dist.get(p.domain, 0) + 1
        priority_dist[p.priority] = priority_dist.get(p.priority, 0) + 1
        submitter_dist[p.submitter_type] = submitter_dist.get(p.submitter_type, 0) + 1

        region_key = p.region.strip() if p.region and p.region.strip() else "Not Specified"
        region_dist[region_key] = region_dist.get(region_key, 0) + 1

        if p.keywords:
            all_keywords.extend(p.keywords)

        if p.word_count:
            word_counts.append(p.word_count)

        date_key = p.created_at.strftime("%Y-%m-%d")
        timeline[date_key] = timeline.get(date_key, 0) + 1

        if p.title and p.description and p.domain and p.region:
            complete_count += 1

    keyword_counter = Counter(all_keywords)
    top_keywords = [{"word": w, "count": c} for w, c in keyword_counter.most_common(20)]

    timeline_sorted = sorted(
        [{"date": k, "count": v} for k, v in timeline.items()],
        key=lambda x: x["date"],
    )

    avg_wc = round(sum(word_counts) / len(word_counts), 1) if word_counts else 0
    unique_regions = len([k for k in region_dist if k != "Not Specified"])

    return Response({
        "total_submissions": len(problems),
        "domain_distribution": [{"name": k, "count": v} for k, v in sorted(domain_dist.items(), key=lambda x: -x[1])],
        "priority_distribution": [{"name": k.capitalize(), "count": v} for k, v in priority_dist.items()],
        "submitter_distribution": [{"name": k, "count": v} for k, v in sorted(submitter_dist.items(), key=lambda x: -x[1])],
        "region_distribution": [{"name": k, "count": v} for k, v in sorted(region_dist.items(), key=lambda x: -x[1])],
        "avg_word_count": avg_wc,
        "min_word_count": min(word_counts) if word_counts else 0,
        "max_word_count": max(word_counts) if word_counts else 0,
        "total_word_count": sum(word_counts),
        "top_keywords": top_keywords,
        "submissions_timeline": timeline_sorted,
        "quality_metrics": {
            "completeness_rate": round((complete_count / len(problems)) * 100, 1),
            "avg_description_length": avg_wc,
            "domains_covered": len(domain_dist),
            "unique_regions": unique_regions,
        },
    })


# ─── Meta endpoint ────────────────────────────────────────────────────────────

@api_view(["GET"])
def meta(request):
    return Response({
        "domains": VALID_DOMAINS,
        "priorities": ["high", "medium", "low"],
        "submitter_types": VALID_SUBMITTER_TYPES,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Django Template Views (HTML pages — no React)
# ═══════════════════════════════════════════════════════════════════════════════

def home(request):
    """Landing page with real-time stats."""
    # Penganjur has their own landing page
    if request.user.is_authenticated and request.user.is_staff and not request.user.is_superuser:
        return redirect("bengkel:penganjur_home")

    total = ProblemStatement.objects.count()
    domains_covered = ProblemStatement.objects.values("domain").distinct().count()
    high_priority = ProblemStatement.objects.filter(priority="high").count()
    submitter_types_count = ProblemStatement.objects.values("submitter_type").distinct().count()

    priority_counts = {
        item["priority"]: item["count"]
        for item in ProblemStatement.objects.values("priority").annotate(count=Count("id"))
    }
    avg_words_qs = ProblemStatement.objects.aggregate(avg=Avg("word_count"))
    avg_words = round(avg_words_qs["avg"] or 0)

    priority_tags = [
        {"label": "Tinggi", "count": priority_counts.get("high", 0), "color": "bg-red-400"},
        {"label": "Sederhana", "count": priority_counts.get("medium", 0), "color": "bg-amber-400"},
        {"label": "Rendah", "count": priority_counts.get("low", 0), "color": "bg-emerald-400"},
    ]
    total_pct = min(100, (total / 50) * 100) if total else 0
    domain_pct = min(100, (domains_covered / 18) * 100)
    high_pct = min(100, (high_priority / max(total, 1)) * 100)

    why_items = [
        "Mengumpul masalah nyata dari pelbagai lapisan masyarakat",
        "Menyokong proses pembuat keputusan berasaskan bukti",
        "Mengenal pasti jurang dalam ekosistem kesihatan digital",
        "Memastikan suara pesakit dan pengamal didengar",
        "Membina Blueprint Digital Kesihatan yang inklusif",
    ]

    milestones = [
        {"year": "2024–2025", "title": "Fasa Pengumpulan Data", "desc": "Mengumpul pernyataan masalah dari seluruh ekosistem kesihatan", "active": True},
        {"year": "2026–2028", "title": "Analisis & Pelan Tindakan", "desc": "Memetakan keutamaan dan membangun pelan pelaksanaan", "active": False},
        {"year": "2029–2035", "title": "Transformasi Digital Awal", "desc": "Pelaksanaan pendigitalan sistem penjagaan primer dan hospital", "active": False},
        {"year": "2036–2045", "title": "Integrasi Ekosistem", "desc": "Interoperabiliti penuh antara semua sistem kesihatan nasional", "active": False},
        {"year": "2046–2055", "title": "Masa Hadapan Kesihatan", "desc": "AI, genomik, dan penjagaan kesihatan prediktif berskala nasional", "active": False},
    ]

    faqs = [
        {"q": "Siapa yang boleh menghantar pernyataan masalah?", "a": "Sesiapa sahaja boleh menyumbang — pesakit, warganegara, doktor, jururawat, pentadbir hospital, penggubal dasar, mahupun penyelidik. Tiada log masuk diperlukan untuk menghantar."},
        {"q": "Adakah maklumat saya akan dirahsiakan?", "a": "Ya. Semua data yang dikemukakan adalah tertakluk kepada Akta Perlindungan Data Peribadi 2010 (PDPA) dan hanya digunakan untuk tujuan perancangan dasar kesihatan digital kebangsaan."},
        {"q": "Bagaimana pernyataan saya akan digunakan?", "a": "Pernyataan masalah yang dikemukakan akan dianalisis oleh pasukan Bahagian Pembangunan Kesihatan Digital KKM untuk mengenal pasti jurang, pola, dan keutamaan dalam pembangunan Blueprint Digital Kesihatan Kebangsaan."},
        {"q": "Apakah format pernyataan masalah yang baik?", "a": "Huraikan masalah secara spesifik — termasuk konteks, impak kepada pesakit atau sistem, skop populasi yang terjejas, dan cadangan penyelesaian jika ada. Semakin terperinci, semakin berguna untuk analisis dasar."},
        {"q": "Berapa lama proses semakan mengambil masa?", "a": "Pernyataan masalah akan disemak oleh pasukan teknikal KKM dalam masa 30 hari bekerja. Analisis menyeluruh bagi setiap kitaran pengumpulan data akan diterbitkan sebagai laporan dwi-tahunan."},
    ]

    return render(request, "problems/home.html", {
        "total": total,
        "domains_covered": domains_covered,
        "high_priority": high_priority,
        "submitter_types_count": submitter_types_count,
        "avg_words": avg_words,
        "priority_tags": priority_tags,
        "total_pct": int(total_pct),
        "domain_pct": int(domain_pct),
        "high_pct": int(high_pct),
        "why_items": why_items,
        "milestones": milestones,
        "faqs": faqs,
        "domains": VALID_DOMAINS,
        "active": "home",
    })


@login_required
def submit_view(request):
    """GET: show form. POST: save problem statement."""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("home")
    if request.method == "POST":
        data = {
            "title": request.POST.get("title", "").strip(),
            "description": request.POST.get("description", "").strip(),
            "domain": request.POST.get("domain", ""),
            "priority": request.POST.get("priority", "medium"),
            "region": request.POST.get("region", "").strip(),
            "submitter_type": request.POST.get("submitter_type", ""),
        }
        serializer = ProblemStatementSerializer(data=data)
        if serializer.is_valid():
            title = serializer.validated_data["title"]
            description = serializer.validated_data["description"]
            keywords = extract_keywords(f"{title} {description}")
            wc = count_words(description)
            submitted_by = request.user if request.user.is_authenticated else None
            serializer.save(keywords=keywords, word_count=wc, submitted_by=submitted_by)
            messages.success(request, "Pernyataan masalah berjaya dihantar!")
            return redirect("submit")
        else:
            return render(request, "problems/submit.html", {
                "domains": VALID_DOMAINS,
                "submitter_types": VALID_SUBMITTER_TYPES,
                "errors": serializer.errors,
                "form_data": data,
                "active": "submit",
            })

    return render(request, "problems/submit.html", {
        "domains": VALID_DOMAINS,
        "submitter_types": VALID_SUBMITTER_TYPES,
        "active": "submit",
    })


@login_required
def list_view(request):
    """Show all problem statements with optional filters."""
    if request.user.is_staff and not request.user.is_superuser:
        return redirect("bengkel:list")
    qs = ProblemStatement.objects.all()
    domain_filter = request.GET.get("domain", "")
    priority_filter = request.GET.get("priority", "")
    if domain_filter:
        qs = qs.filter(domain=domain_filter)
    if priority_filter:
        qs = qs.filter(priority=priority_filter)

    all_domains = ProblemStatement.objects.values_list("domain", flat=True).distinct().order_by("domain")

    return render(request, "problems/list.html", {
        "problems": qs,
        "all_domains": all_domains,
        "domain_filter": domain_filter,
        "priority_filter": priority_filter,
        "total": qs.count(),
        "total_all": ProblemStatement.objects.count(),
        "active": "list",
    })


@login_required
def delete_view(request, pk):
    """Delete a problem statement."""
    if not request.user.is_superuser:
        return redirect("list")
    problem = get_object_or_404(ProblemStatement, pk=pk)
    if request.method == "POST":
        problem.delete()
        messages.success(request, "Problem statement deleted.")
    return redirect("list")


@login_required
def profile_view(request):
    """Data profile page with charts (Chart.js via CDN)."""
    if request.user.is_staff and not request.user.is_superuser:
        return redirect("bengkel:list")
    problems = list(ProblemStatement.objects.all().order_by("created_at"))

    if not problems:
        return render(request, "problems/profile.html", {"empty": True, "active": "profile"})

    domain_dist: dict = {}
    priority_dist: dict = {}
    submitter_dist: dict = {}
    region_dist: dict = {}
    all_keywords: list = []
    word_counts: list = []
    timeline: dict = {}
    complete_count = 0

    for p in problems:
        domain_dist[p.domain] = domain_dist.get(p.domain, 0) + 1
        priority_dist[p.priority] = priority_dist.get(p.priority, 0) + 1
        submitter_dist[p.submitter_type] = submitter_dist.get(p.submitter_type, 0) + 1
        region_key = p.region.strip() if p.region and p.region.strip() else "Not Specified"
        region_dist[region_key] = region_dist.get(region_key, 0) + 1
        if p.keywords:
            all_keywords.extend(p.keywords)
        if p.word_count:
            word_counts.append(p.word_count)
        date_key = p.created_at.strftime("%Y-%m-%d")
        timeline[date_key] = timeline.get(date_key, 0) + 1
        if p.title and p.description and p.domain and p.region:
            complete_count += 1

    keyword_counter = Counter(all_keywords)
    top_keywords = [{"word": w, "count": c} for w, c in keyword_counter.most_common(20)]
    avg_wc = round(sum(word_counts) / len(word_counts), 1) if word_counts else 0
    unique_regions = len([k for k in region_dist if k != "Not Specified"])

    domain_sorted = sorted(domain_dist.items(), key=lambda x: -x[1])
    priority_sorted = sorted(priority_dist.items(), key=lambda x: -x[1])
    submitter_sorted = sorted(submitter_dist.items(), key=lambda x: -x[1])
    region_sorted = sorted(region_dist.items(), key=lambda x: -x[1])
    timeline_sorted = sorted(timeline.items())

    return render(request, "problems/profile.html", {
        "empty": False,
        "total": len(problems),
        "avg_wc": avg_wc,
        "min_wc": min(word_counts) if word_counts else 0,
        "max_wc": max(word_counts) if word_counts else 0,
        "total_wc": sum(word_counts),
        "domains_covered": len(domain_dist),
        "unique_regions": unique_regions,
        "completeness_rate": round((complete_count / len(problems)) * 100, 1),
        "top_keywords": top_keywords,
        # JSON for Chart.js
        "domain_labels": json.dumps([k for k, _ in domain_sorted]),
        "domain_data": json.dumps([v for _, v in domain_sorted]),
        "priority_labels": json.dumps([k.capitalize() for k, _ in priority_sorted]),
        "priority_data": json.dumps([v for _, v in priority_sorted]),
        "submitter_labels": json.dumps([k for k, _ in submitter_sorted]),
        "submitter_data": json.dumps([v for _, v in submitter_sorted]),
        "region_labels": json.dumps([k for k, _ in region_sorted]),
        "region_data": json.dumps([v for _, v in region_sorted]),
        "timeline_labels": json.dumps([k for k, _ in timeline_sorted]),
        "timeline_data": json.dumps([v for _, v in timeline_sorted]),
        "active": "profile",
    })


# ─── Auth Views ────────────────────────────────────────────────────────────────

from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm

def custom_login_view(request):
    """Login — accepts username or email; redirects based on role."""
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect("superadmin:dashboard")
        return redirect("bengkel:list" if request.user.is_staff else "bengkel:dashboard")

    error = None
    if request.method == "POST":
        from django.contrib.auth import authenticate
        identifier = request.POST.get("username", "").strip()
        password   = request.POST.get("password", "")

        # Allow login with email
        if "@" in identifier:
            try:
                identifier = User.objects.get(email__iexact=identifier).username
            except User.DoesNotExist:
                pass

        user = authenticate(request, username=identifier, password=password)
        if user is not None:
            auth_login(request, user)
            next_url = request.GET.get("next") or request.POST.get("next", "")
            if next_url:
                return redirect(next_url)
            if user.is_superuser:
                return redirect("superadmin:dashboard")
            return redirect("bengkel:penganjur_home" if user.is_staff else "bengkel:dashboard")
        else:
            error = "Nama pengguna / e-mel atau kata laluan tidak sah."

    return render(request, "registration/login.html", {"error": error})


# ─── User Registration ─────────────────────────────────────────────────────────

def register_view(request):
    """Public user registration (Peserta or Penganjur request)."""
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        role       = request.POST.get("role", "peserta")
        username   = request.POST.get("username", "").strip()
        email      = request.POST.get("email", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name  = request.POST.get("last_name", "").strip()
        organisasi = request.POST.get("organisasi", "").strip()
        jabatan    = request.POST.get("jabatan", "").strip()
        telefon    = request.POST.get("telefon", "").strip()
        sebab      = request.POST.get("sebab", "").strip()
        pw1        = request.POST.get("password1", "")
        pw2        = request.POST.get("password2", "")
        terms      = request.POST.get("terms")

        form_data = {
            "username": username, "email": email,
            "first_name": first_name, "last_name": last_name,
            "organisasi": organisasi, "jabatan": jabatan,
            "telefon": telefon, "sebab": sebab, "role": role,
        }

        def _err(msg):
            return render(request, "registration/register.html", {"error": msg, "form_data": form_data})

        import re as _re

        # ── Penganjur flow ────────────────────────────────────────────────────
        if role == "penganjur":
            if not email or not _re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
                return _err("Sila masukkan alamat e-mel yang sah.")
            if User.objects.filter(email=email).exists():
                return _err("E-mel ini sudah berdaftar. Sila gunakan e-mel lain atau log masuk.")
            if not organisasi:
                return _err("Nama organisasi wajib diisi untuk permohonan penganjur.")
            if not terms:
                return _err("Sila bersetuju dengan Dasar Privasi untuk meneruskan pendaftaran.")

            # Auto-generate username from email prefix
            base = _re.sub(r'[^\w]', '_', email.split('@')[0])[:24] or "penganjur"
            candidate = base
            suffix = 1
            while User.objects.filter(username=candidate).exists():
                candidate = f"{base}_{suffix}"
                suffix += 1
            username = candidate

            # Create inactive account (no password yet — will be set upon approval)
            user = User.objects.create_user(
                username=username, email=email, password=None,
                first_name=first_name, last_name=last_name,
                is_active=False,
            )
            user.set_unusable_password()
            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.organisasi = organisasi
            profile.jabatan    = jabatan
            profile.telefon    = telefon
            profile.save()
            PenganjurRequest.objects.create(user=user, sebab=sebab)

            # Send "pending" confirmation email
            try:
                from django.core.mail import EmailMultiAlternatives
                from django.conf import settings as _cfg
                _subj = "Permohonan Penganjur Anda Telah Diterima — NDHB"
                _txt = (
                    f"Assalamualaikum / Salam Sejahtera,\n\n"
                    f"Terima kasih kerana mendaftar sebagai Penganjur dalam Sistem Pengurusan Bengkel NDHB.\n"
                    f"Permohonan anda kini sedang dalam semakan oleh pentadbir.\n\n"
                    f"Anda akan menerima e-mel seterusnya setelah permohonan diproses.\n\n"
                    f"Sila JANGAN cuba log masuk sehingga permohonan anda diluluskan.\n\n"
                    f"Terima kasih.\nPasukan NDHB"
                )
                _html = f"""
                <div style="font-family:Inter,Arial,sans-serif;max-width:560px;margin:auto;background:#0f172a;
                            color:#e2e8f0;padding:36px 40px;border-radius:16px;">
                  <h2 style="color:#f59e0b;margin-top:0;">Permohonan Diterima &#8987;</h2>
                  <p>Assalamualaikum / Salam Sejahtera,</p>
                  <p>Terima kasih kerana mendaftar sebagai <strong>Penganjur</strong> dalam
                     Sistem Pengurusan Bengkel NDHB.</p>
                  <div style="background:#1e293b;border-radius:10px;padding:16px 20px;margin:20px 0;
                              border-left:4px solid #f59e0b;">
                    <p style="margin:0;font-size:14px;color:#fcd34d;">
                      &#128336;&nbsp; Permohonan anda kini <strong>sedang dalam semakan</strong> oleh pentadbir.
                      Anda akan dihubungi melalui e-mel ini setelah permohonan diproses.
                    </p>
                  </div>
                  <p style="font-size:13px;color:#94a3b8;">
                    Sila <strong style="color:#f87171;">JANGAN cuba log masuk</strong> sehingga
                    permohonan anda diluluskan.
                  </p>
                  <hr style="border:none;border-top:1px solid #1e293b;margin:28px 0;">
                  <p style="font-size:12px;color:#475569;margin:0;">Sistem Pengurusan Bengkel &middot; NDHB</p>
                </div>
                """
                _msg = EmailMultiAlternatives(
                    subject=_subj, body=_txt,
                    from_email=getattr(_cfg, "DEFAULT_FROM_EMAIL", "noreply@ndhb.my"),
                    to=[email],
                )
                _msg.attach_alternative(_html, "text/html")
                _msg.send()
            except Exception:
                pass  # Silent fail — do not block registration

            return redirect("permohonan_pending")

        # ── Peserta flow ──────────────────────────────────────────────────────
        if not username or len(username) < 3:
            return _err("Nama pengguna mesti sekurang-kurangnya 3 aksara.")
        if not _re.match(r'^[\w]+$', username):
            return _err("Nama pengguna hanya boleh mengandungi huruf, nombor, dan garis bawah (_).")
        if User.objects.filter(username=username).exists():
            return _err("Nama pengguna ini sudah digunakan. Sila pilih nama lain.")
        if not email or not _re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return _err("Sila masukkan alamat e-mel yang sah.")
        if User.objects.filter(email=email).exists():
            return _err("E-mel ini sudah berdaftar. Sila gunakan e-mel lain.")
        if len(pw1) < 8:
            return _err("Kata laluan mesti sekurang-kurangnya 8 aksara.")
        if pw1 != pw2:
            return _err("Kata laluan tidak sepadan. Sila cuba semula.")
        if not terms:
            return _err("Sila bersetuju dengan Dasar Privasi untuk meneruskan pendaftaran.")

        user = User.objects.create_user(
            username=username, email=email, password=pw1,
            first_name=first_name, last_name=last_name,
        )
        auth_login(request, user)
        messages.success(request, f"Selamat datang, {username}! Akaun anda telah berjaya didaftarkan.")
        return redirect("bengkel:dashboard")

    return render(request, "registration/register.html", {})


def permohonan_pending_view(request):
    """Displayed after a penganjur submits their registration request."""
    return render(request, "registration/permohonan_pending.html", {})


def check_email(request):
    """AJAX — check if email already registered (used by register page)."""
    email = request.GET.get("email", "").strip()
    exists = User.objects.filter(email=email).exists() if email else False
    return JsonResponse({"exists": exists})


# ─── Admin: User Management ────────────────────────────────────────────────────

@login_required
def users_view(request):
    """Superadmin — list all registered users with submission counts."""
    if not request.user.is_superuser:
        messages.error(request, "Akses ditolak. Hanya superadmin dibenarkan.")
        return redirect("home")

    users = User.objects.annotate(submission_count=Count("submissions")).order_by("date_joined")

    return render(request, "problems/users.html", {
        "users": users,
        "total_users": users.count(),
        "active_users": users.filter(is_active=True).count(),
        "admin_users": users.filter(is_staff=True).count(),
        "total_submissions": ProblemStatement.objects.count(),
        "active": "users",
    })


@login_required
@require_POST
def toggle_user_active(request, pk):
    """Superadmin — toggle a user's is_active status."""
    if not request.user.is_superuser:
        messages.error(request, "Akses ditolak.")
        return redirect("home")
    if pk == request.user.pk:
        messages.error(request, "Anda tidak boleh nyahaktifkan akaun anda sendiri.")
        return redirect("users")
    user = get_object_or_404(User, pk=pk)
    if user.is_superuser:
        messages.error(request, "Akaun superadmin tidak boleh diubah.")
        return redirect("users")
    user.is_active = not user.is_active
    user.save()
    status_label = "diaktifkan" if user.is_active else "dinyahaktifkan"
    messages.success(request, f"Akaun {user.username} telah {status_label}.")
    return redirect("users")
