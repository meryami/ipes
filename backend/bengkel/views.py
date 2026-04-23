from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
import csv
import io as _io
import json
from collections import defaultdict
from django.db.models import Count
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

from .models import (Bengkel, Jemputan, Kehadiran, PenganjurRequest, UserProfile,
    SpafPainPoint, SpafProblemStatement, SpafRootCauseAnalysis,
    SpafRootCauseValidation, SpafRiskAnalysis,
    AnalisisSWOT, AnalisisPESTEL, Analisis5C, AnalisisSOAR, AnalisisVMOST,
    BengkelContribution, ContributionFile, ForumPesan)


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
def penganjur_insight(request, pk):
    """Penganjur — Analytics/Insight page for their own bengkel."""
    if not request.user.is_staff or request.user.is_superuser:
        return redirect("home")

    bengkel = get_object_or_404(Bengkel, pk=pk, created_by=request.user)

    # ── Core querysets ────────────────────────────────────────────────────────
    jemputan_qs  = Jemputan.objects.filter(bengkel=bengkel).select_related('user').prefetch_related('kehadiran')
    kehadiran_qs = Kehadiran.objects.filter(jemputan__bengkel=bengkel)

    stats = {
        "total_jemputan": jemputan_qs.count(),
        "total_hadir":    kehadiran_qs.count(),
        "total_diterima": jemputan_qs.filter(status="accepted").count(),
        "total_pending":  jemputan_qs.filter(status="pending").count(),
        "total_ditolak":  jemputan_qs.filter(status="rejected").count(),
    }

    # ── Contribution / file stats ─────────────────────────────────────────────
    contribution_files = ContributionFile.objects.filter(
        contribution__bengkel=bengkel
    ).select_related('contribution__jemputan')
    total_files = contribution_files.count()

    # File format breakdown
    word_exts  = {'doc', 'docx'}
    excel_exts = {'xls', 'xlsx'}
    pptx_exts  = {'ppt', 'pptx'}
    image_exts = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'}
    ext_map    = {'pdf': 0, 'word': 0, 'excel': 0, 'pptx': 0, 'image': 0, 'txt': 0}
    for cf in contribution_files:
        ext = cf.original_name.rsplit('.', 1)[-1].lower() if '.' in cf.original_name else ''
        if ext == 'pdf':             ext_map['pdf']   += 1
        elif ext in word_exts:       ext_map['word']  += 1
        elif ext in excel_exts:      ext_map['excel'] += 1
        elif ext in pptx_exts:       ext_map['pptx']  += 1
        elif ext in image_exts:      ext_map['image'] += 1
        else:                        ext_map['txt']   += 1

    jenis_fail_semua = [
        ext_map['pdf'], ext_map['word'], ext_map['excel'],
        ext_map['pptx'], ext_map['image'], ext_map['txt']
    ]

    # ── Mind-map: group jemputan by organisasi ────────────────────────────────
    COLOR_BG  = ['bg-blue-600','bg-cyan-600','bg-emerald-600','bg-lime-500',
                 'bg-amber-600','bg-red-600','bg-purple-600','bg-pink-600',
                 'bg-indigo-600','bg-orange-600']
    COLOR_HEX = ['#2563eb','#0891b2','#059669','#84cc16',
                 '#d97706','#dc2626','#7c3aed','#db2777',
                 '#4f46e5','#ea580c']

    org_dict = defaultdict(list)
    for j in jemputan_qs:
        org = (j.organisasi or '').strip() or 'Tidak Dinyatakan'
        org_dict[org].append({'id': j.id, 'nama': j.nama, 'kumpulan': j.jawatan or 'Umum'})

    hierarki         = []
    pglb_semua       = []
    smbn_semua       = []
    data_mockup      = {}
    org_list_ordered = sorted(org_dict.items(), key=lambda x: -len(x[1]))

    for i, (org, members) in enumerate(org_list_ordered):
        cidx      = i % len(COLOR_BG)
        ids       = [m['id'] for m in members]
        org_files = ContributionFile.objects.filter(
            contribution__jemputan_id__in=ids
        ).count()

        hierarki.append({
            'kategori': org,
            'pax':      len(members),
            'warnaBg':  COLOR_BG[cidx],
            'warnaHex': COLOR_HEX[cidx],
            'cawangan': [{'nama': org, 'ahli': members}]
        })
        pglb_semua.append(len(members))
        smbn_semua.append(org_files)

        # Per-org filter arrays for chart update
        n = len(org_list_ordered)
        data_mockup[org] = {
            'penglibatan': [len(members) if j == i else 0 for j in range(n)],
            'sumbangan':   [org_files   if j == i else 0 for j in range(n)],
            'jenisFail':   jenis_fail_semua,
        }

    data_mockup['Semua'] = {
        'penglibatan': pglb_semua,
        'sumbangan':   smbn_semua,
        'jenisFail':   jenis_fail_semua,
    }

    # ── Trend line: check-ins grouped by hour ─────────────────────────────────
    # Use Python-level grouping to avoid MySQL timezone issues
    kehadiran_list = list(kehadiran_qs.order_by('checked_in_at').values_list('checked_in_at', flat=True))
    hour_counts = defaultdict(int)
    for dt in kehadiran_list:
        if dt:
            hour_counts[dt.strftime('%H:%M')] += 1
    trend_labels = list(hour_counts.keys())
    trend_values = list(hour_counts.values())

    # ── Top contributors (most files uploaded) ────────────────────────────────
    top_contrib_qs = (
        jemputan_qs
        .annotate(file_count=Count('contribution__files', distinct=True))
        .filter(file_count__gt=0)
        .order_by('-file_count')[:5]
    )
    top_contributors = []
    for j in top_contrib_qs:
        nama = j.nama or 'Tanpa Nama'
        top_contributors.append({
            'id':       j.id,
            'nama':     nama,
            'org':      j.organisasi or 'Tidak Dinyatakan',
            'files':    j.file_count,
            'initials': ''.join([w[0].upper() for w in nama.split()[:2]]),
        })

    # ── Passive participants (no contribution yet) ────────────────────────────
    contributed_ids = BengkelContribution.objects.filter(
        bengkel=bengkel
    ).values_list('jemputan_id', flat=True)
    passive_qs = jemputan_qs.exclude(id__in=contributed_ids).order_by('nama')[:5]
    passive_list = []
    for j in passive_qs:
        nama = j.nama or 'Tanpa Nama'
        passive_list.append({
            'id':       j.id,
            'nama':     nama,
            'org':      j.organisasi or 'Tidak Dinyatakan',
            'initials': ''.join([w[0].upper() for w in nama.split()[:2]]),
        })

    # ── AI Audit stats ────────────────────────────────────────────────────────
    total_submissions = BengkelContribution.objects.filter(bengkel=bengkel).count()
    indexed_pct = round((total_files / (total_files + 1)) * 100) if total_files else 0  # placeholder
    audit_stats = {
        'total_files':   total_files,
        'pdf':           ext_map['pdf'],
        'word':          ext_map['word'],
        'excel':         ext_map['excel'],
        'pptx':          ext_map['pptx'],
        'image':         ext_map['image'],
        'txt':           ext_map['txt'],
        'submissions':   total_submissions,
        'indexed_pct':   indexed_pct,
    }

    # ── Forum messages ────────────────────────────────────────────────────────
    forum_messages = list(
        ForumPesan.objects.filter(bengkel=bengkel)
        .order_by('created_at')[:30]
        .values('id','nama_paparan','organisasi','mesej','created_at')
    )
    for fm in forum_messages:
        nm = fm['nama_paparan'] or 'X'
        fm['initials'] = ''.join([w[0].upper() for w in nm.split()[:2]])
        fm['masa'] = fm['created_at'].strftime('%H:%M') if fm['created_at'] else ''
    forum_count = ForumPesan.objects.filter(bengkel=bengkel).count()

    # ── Seating (assign seat number by creation order) ────────────────────────
    seating_list = list(jemputan_qs.order_by('created_at').values(
        'id','nama','organisasi','status'
    ))
    for idx, seat in enumerate(seating_list):
        seat['no_tempat_duduk'] = idx + 1
        nm = seat['nama'] or 'X'
        seat['initials'] = ''.join([w[0].upper() for w in nm.split()[:2]])

    # ── SPAF contribution word-count proxy ────────────────────────────────────
    spaf_words = 0
    for pp in SpafPainPoint.objects.filter(user__jemputan__bengkel=bengkel):
        spaf_words += len((pp.keterangan + ' ' + pp.kesan).split())
    for ps in SpafProblemStatement.objects.filter(user__jemputan__bengkel=bengkel):
        spaf_words += len((ps.masalah_utama + ' ' + ps.skop).split())
    corpus_k = round(spaf_words / 1000, 1)

    return render(request, "bengkel/insight.html", {
        "bengkel":              bengkel,
        "stats":                stats,
        "jemputan_list":        jemputan_qs.order_by('nama')[:50],
        "top_participants":     jemputan_qs.filter(status="accepted").order_by('nama')[:5],
        "passive_participants": jemputan_qs.filter(status="pending").order_by('nama')[:5],
        "total_contributions":  total_submissions,
        "total_files":          total_files,
        "corpus_k":             corpus_k,
        # JSON blobs for JavaScript
        "hierarki_json":         json.dumps(hierarki,          ensure_ascii=False),
        "data_mockup_json":      json.dumps(data_mockup,       ensure_ascii=False),
        "trend_labels_json":     json.dumps(trend_labels,      ensure_ascii=False),
        "trend_values_json":     json.dumps(trend_values,      ensure_ascii=False),
        "top_contributors_json": json.dumps(top_contributors,  ensure_ascii=False),
        "passive_list_json":     json.dumps(passive_list,      ensure_ascii=False),
        "audit_stats_json":      json.dumps(audit_stats,       ensure_ascii=False),
        "forum_messages_json":   json.dumps(forum_messages,    ensure_ascii=False, default=str),
        "forum_count":           forum_count,
        "seating_json":          json.dumps(seating_list,      ensure_ascii=False),
        "jemputan_list_json":    json.dumps(list(jemputan_qs.order_by('nama')[:50].values('id', 'nama', 'organisasi', 'jawatan')), ensure_ascii=False),
    })


@login_required
def profil_peserta(request, jid):
    """Show detailed analytics profile for a participant (penganjur version of profil_SME)."""
    if not request.user.is_staff:
        return redirect("bengkel:dashboard")
    
    j = get_object_or_404(Jemputan, pk=jid)
    bengkel = j.bengkel
    
    # Verify user owns this bengkel
    if bengkel.created_by != request.user:
        return redirect("bengkel:dashboard")
    
    # Get participant's contributions
    contributions = BengkelContribution.objects.filter(bengkel=bengkel, jemputan=j)
    files = ContributionFile.objects.filter(contribution__in=contributions)
    
    # Calculate mock scores based on real data
    total_files = files.count()
    quality_score = min(95, 60 + total_files * 5)  # Base 60, +5 per file, max 95
    index_rate = 100 if total_files > 0 else 0
    
    # Get file types for radar chart
    file_types = {'pdf': 0, 'doc': 0, 'xls': 0, 'ppt': 0, 'img': 0, 'txt': 0}
    for f in files:
        ext = f.original_name.rsplit('.', 1)[-1].lower() if '.' in f.original_name else ''
        if ext == 'pdf': file_types['pdf'] += 1
        elif ext in ('doc', 'docx'): file_types['doc'] += 1
        elif ext in ('xls', 'xlsx'): file_types['xls'] += 1
        elif ext in ('ppt', 'pptx'): file_types['ppt'] += 1
        elif ext in ('jpg', 'jpeg', 'png', 'gif'): file_types['img'] += 1
        else: file_types['txt'] += 1
    
    # REAL persona radar analysis from contribution summaries
    keyword_categories = {
        'klinikal': ['pesakit', 'clinic', 'hospital', 'doctor', 'medical', 'clinical', 'diagnosis', 'treatment', 'patient', 'sakit', 'ubat', 'rawatan'],
        'polisi': ['policy', 'dasar', 'regulation', 'guideline', 'procedure', 'garis panduan', 'peraturan', 'compliance', 'piawaian', 'standard'],
        'teknologi': ['system', 'teknologi', 'IT', 'software', 'database', 'cloud', 'digital', 'API', 'integration', 'sistem', 'komputer'],
        'kewangan': ['budget', 'cost', 'financial', 'kewangan', 'belanjawan', 'expense', 'revenue', 'pelaburan', 'investment', 'wang'],
        'infrastruktur': ['infrastructure', 'facility', 'bangunan', 'premises', 'equipment', 'hardware', 'server', 'network', 'rangkaian']
    }
    
    # Collect all text from contribution summaries AND SPAF forms
    all_text = ''
    
    # From contribution files
    for cf in files:
        if cf.summary:
            all_text += ' ' + cf.summary.lower()
    
    # From SPAF Pain Points
    for pp in SpafPainPoint.objects.filter(user__jemputan=j):
        all_text += ' ' + (pp.keterangan or '').lower() + ' ' + (pp.kesan or '').lower()
    
    # From SPAF Problem Statements
    for ps in SpafProblemStatement.objects.filter(user__jemputan=j):
        all_text += ' ' + (ps.masalah_utama or '').lower() + ' ' + (ps.skop or '').lower()
    
    # From SPAF Root Cause Analysis
    for rca in SpafRootCauseAnalysis.objects.filter(user__jemputan=j):
        all_text += ' ' + (rca.masalah or '').lower() + ' ' + (rca.punca_utama or '').lower() + ' ' + (rca.punca_penyumbang or '').lower() + ' ' + (rca.bukti or '').lower()
    
    # From SPAF Root Cause Validation
    for rcv in SpafRootCauseValidation.objects.filter(user__jemputan=j):
        all_text += ' ' + (rcv.pengesahan or '').lower() + ' ' + (rcv.cadangan or '').lower()
    
    # From SPAF Risk Analysis
    for ra in SpafRiskAnalysis.objects.filter(user__jemputan=j):
        all_text += ' ' + (ra.risiko or '').lower() + ' ' + (ra.impak or '').lower() + ' ' + (ra.mitoligasi or '').lower()
    
    # Count keyword occurrences per category
    category_scores = {cat: 0 for cat in keyword_categories}
    total_keywords = 0
    
    for text in all_text.split():
        for category, keywords in keyword_categories.items():
            if any(kw in text for kw in keywords):
                category_scores[category] += 1
                total_keywords += 1
    
    # Convert to percentages (0-100 scale)
    if total_keywords > 0:
        persona_radar = {
            cat: round((score / total_keywords) * 100, 1)
            for cat, score in category_scores.items()
        }
    else:
        # No contributions = 0% for all categories
        persona_radar = {'klinikal': 0, 'polisi': 0, 'teknologi': 0, 'kewangan': 0, 'infrastruktur': 0}
    
    # Build events timeline (mock - would need actual event history in production)
    events = [
        {
            'id': f'evt{bengkel.id}',
            'nama': bengkel.title,
            'tarikh': bengkel.tarikh.strftime('%d %B %Y') if bengkel.tarikh else 'TBD',
            'status': 'Ongoing' if bengkel.tarikh and bengkel.tarikh <= timezone.now() <= (bengkel.tarikh_tamat or bengkel.tarikh) else 'Upcoming',
            'badgeWarna': 'bg-emerald-100 text-emerald-700 border-emerald-200' if bengkel.tarikh and bengkel.tarikh <= timezone.now() else 'bg-amber-100 text-amber-700 border-amber-200',
            'ikon': 'fa-dot-circle animate-pulse text-emerald-500' if bengkel.tarikh and bengkel.tarikh <= timezone.now() else 'fa-clock text-amber-500',
            'skor': quality_score,
            'kataKunci': ['Digital Transformation', 'Data Management', 'System Integration'][:min(3, total_files + 1)],
            'dokumen': [
                {
                    'jenis': 'File' if cf.original_name else 'Form',
                    'tajuk': cf.original_name or f'Contribution Form #{cf.id}',
                    'kategori': 'Document',
                    'vol': f'{len(cf.summary or "")} w' if cf.summary else f'{total_files * 500} w'
                }
                for cf in files[:5]
            ]
        }
    ]
    
    # Ecosystem role determination based on actual content
    clinical_keywords = ['pesakit', 'doctor', 'medical', 'clinical', 'hospital', 'ubat', 'rawatan', 'diagnosis']
    tech_keywords = ['system', 'IT', 'software', 'database', 'API', 'digital', 'cloud', 'sistem', 'teknologi']
    
    clinical_count = sum(1 for word in all_text.split() if any(kw in word for kw in clinical_keywords))
    tech_count = sum(1 for word in all_text.split() if any(kw in word for kw in tech_keywords))
    
    if clinical_count > 0 and tech_count > 0:
        ecosystem_role = 'The Translator'
        role_desc = 'IT & Medical Liaison'
        role_recommendation = 'bridges the communication gap between medical practitioners and IT vendors'
        best_for = ['System Integration Workshops', 'SOP & Policy Drafting']
    elif clinical_count > tech_count:
        ecosystem_role = 'The Clinical Expert'
        role_desc = 'Medical Domain Specialist'
        role_recommendation = 'provides deep clinical insights and patient workflow expertise'
        best_for = ['Clinical Workflow Design', 'Medical Policy Development']
    elif tech_count > clinical_count:
        ecosystem_role = 'The Technical Expert'
        role_desc = 'IT & Systems Specialist'
        role_recommendation = 'drives technical implementation and system architecture decisions'
        best_for = ['Technical Architecture Planning', 'IT Infrastructure Design']
    else:
        ecosystem_role = 'The Strategist'
        role_desc = 'Policy & Management'
        role_recommendation = 'focuses on strategic planning and organizational governance'
        best_for = ['Strategic Planning Sessions', 'Governance & Compliance']
    
    # Working style (Executor vs Visionary) based on content structure
    executor_keywords = ['SOP', 'procedure', 'step', 'process', 'cost', 'budget', 'implementation', 'action', 'garis panduan', 'langkah']
    visionary_keywords = ['vision', 'future', 'innovate', 'transform', 'potential', 'opportunity', 'strategy', 'vision', 'masa depan', 'inovasi']
    
    executor_count = sum(1 for word in all_text.split() if any(kw.lower() in word for kw in executor_keywords))
    visionary_count = sum(1 for word in all_text.split() if any(kw.lower() in word for kw in visionary_keywords))
    
    total_style = executor_count + visionary_count
    if total_style > 0:
        executor_pct = round((executor_count / total_style) * 100)
    else:
        executor_pct = 50  # Default if no style indicators
    
    executor_pct = min(95, max(5, executor_pct))  # Clamp between 5-95%
    
    # Digital readiness level based on tech keywords and file types
    tech_depth_keywords = ['API', 'cloud', 'microservice', 'blockchain', 'AI', 'machine learning', 'big data', 'analytics', 'integration']
    tech_depth_count = sum(1 for word in all_text.split() if any(kw.lower() in word for kw in tech_depth_keywords))
    
    if tech_depth_count > 10:
        digital_level = 5
        digital_desc = 'Expert level. Fluent in discussing advanced concepts like microservices, AI/ML, and enterprise architecture.'
    elif tech_depth_count > 5:
        digital_level = 4
        digital_desc = 'Advanced. Fluent in discussing system integration, APIs, Cloud migration, and Big Data.'
    elif tech_depth_count > 2:
        digital_level = 3
        digital_desc = 'Intermediate. Understands the need for new systems and basic technical concepts.'
    elif tech_count > 0:
        digital_level = 2
        digital_desc = 'Basic. Familiar with general IT concepts but limited technical depth.'
    else:
        digital_level = 1
        digital_desc = 'Limited. Minimal exposure to digital transformation concepts.'
    
    # Blindspots based on missing topics in contributions
    blindspots = []
    
    security_keywords = ['security', 'cybersecurity', 'privacy', 'PDPA', 'encryption', 'authentication', 'keselamatan', 'privasi']
    if not any(kw in all_text for kw in security_keywords):
        blindspots.append({'area': 'Cybersecurity', 'desc': 'No mentions of security protocols. Monitor for potential patient privacy (PDPA) oversights.'})
    
    change_keywords = ['change management', 'adoption', 'training', 'user acceptance', 'pengurusan perubahan', 'latihan']
    if not any(kw in all_text for kw in change_keywords):
        blindspots.append({'area': 'Change Management', 'desc': 'Lacks focus on end-user emotional adaptation and training needs.'})
    
    if not blindspots:
        blindspots.append({'area': 'Risk Management', 'desc': 'Consider addressing potential implementation risks and contingency planning.'})
    
    return render(request, "bengkel/profil_peserta.html", {
        'jemputan': j,
        'bengkel': bengkel,
        'quality_score': quality_score,
        'index_rate': index_rate,
        'persona_radar': persona_radar,
        'events': json.dumps(events, ensure_ascii=False),
        'ecosystem_role': ecosystem_role,
        'role_desc': role_desc,
        'role_recommendation': role_recommendation,
        'best_for': json.dumps(best_for, ensure_ascii=False),
        'executor_pct': executor_pct,
        'digital_level': digital_level,
        'digital_desc': digital_desc,
        'blindspots': json.dumps(blindspots, ensure_ascii=False),
    })


@login_required
@require_POST
def forum_post(request, pk):
    """AJAX: post a message to bengkel forum."""
    bengkel = get_object_or_404(Bengkel, pk=pk)
    mesej = request.POST.get('mesej', '').strip()
    if not mesej:
        return JsonResponse({'ok': False, 'error': 'Mesej kosong'}, status=400)

    # Resolve display name from linked jemputan or profile
    nama_paparan = request.user.get_full_name() or request.user.username
    organisasi   = ''
    try:
        j = Jemputan.objects.filter(bengkel=bengkel, user=request.user).first()
        if j:
            nama_paparan = j.nama or nama_paparan
            organisasi   = j.organisasi or ''
        elif hasattr(request.user, 'profile'):
            organisasi = request.user.profile.organisasi or ''
    except Exception:
        pass

    pesan = ForumPesan.objects.create(
        bengkel      = bengkel,
        pengirim     = request.user,
        nama_paparan = nama_paparan,
        organisasi   = organisasi,
        mesej        = mesej,
    )
    nm = pesan.nama_paparan or 'X'
    return JsonResponse({
        'ok':       True,
        'id':       pesan.id,
        'nama':     pesan.nama_paparan,
        'org':      pesan.organisasi,
        'mesej':    pesan.mesej,
        'masa':     pesan.created_at.strftime('%H:%M'),
        'initials': ''.join([w[0].upper() for w in nm.split()[:2]]),
    })


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
        org      = request.POST.get("organisasi", "").strip()
        jawatan  = request.POST.get("jawatan", "").strip()

        errors = {}
        if not nama:
            errors["nama"] = "Nama penuh wajib diisi."
        if not email:
            errors["email"] = "E-mel wajib diisi."

        if not errors:
            import random, string, re as _re
            from django.core.mail import EmailMultiAlternatives as _EMA
            from django.conf import settings as _cfg

            # Check for existing active user with same email
            linked_user = User.objects.filter(email__iexact=email, is_active=True).first() if email else None
            new_account_pw = None

            if not linked_user and email:
                # Auto-create a Peserta account
                base = _re.sub(r'[^\w]', '_', email.split('@')[0])[:24] or "peserta"
                candidate = base
                suffix = 1
                while User.objects.filter(username=candidate).exists():
                    candidate = f"{base}_{suffix}"
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
                nama=nama, email=email,
                organisasi=org, jawatan=jawatan,
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

    if request.method == "POST":
        nama        = request.POST.get("nama", "").strip()
        email       = request.POST.get("email", "").strip()
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
        if not nama:  errors["nama"]  = "Nama wajib diisi."
        if not email: errors["email"] = "E-mel wajib diisi."

        if not errors:
            if Jemputan.objects.filter(bengkel=bengkel, email=email).exists():
                errors["email"] = "E-mel ini sudah didaftarkan untuk bengkel ini."
            else:
                j = Jemputan.objects.create(
                    bengkel=bengkel,
                    nama=nama, email=email,
                    organisasi=organisasi, jawatan=jawatan,
                    unit=unit, alamat=alamat,
                    status="accepted",           # auto-accept self-registration
                    responded_at=timezone.now(),
                )
                return redirect("bengkel:portal_tiket", token=j.token)

        return render(request, "bengkel/portal_detail.html", {
            "bengkel": bengkel, "errors": errors,
            "form_data": form_data,
        })

    return render(request, "bengkel/portal_detail.html", {"bengkel": bengkel})


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
            "telefon":    profile.telefon,
            "jabatan":    profile.jabatan,
            "organisasi": profile.organisasi,
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
#  SPAF SITUATIONAL ANALYSIS HUB
# ---------------------------------------------------------------------------

@login_required
def spaf_situational(request):
    jemputan = Jemputan.objects.filter(user=request.user, status="accepted").select_related("bengkel").order_by("-created_at").first()
    if not jemputan:
        return redirect("bengkel:dashboard")
    bengkel = jemputan.bengkel

    swot_count   = AnalisisSWOT.objects.filter(user=request.user).count()
    pestel_count = AnalisisPESTEL.objects.filter(user=request.user).count()
    c5_count     = Analisis5C.objects.filter(user=request.user).count()
    soar_count   = AnalisisSOAR.objects.filter(user=request.user).count()
    vmost_count  = AnalisisVMOST.objects.filter(user=request.user).count()
    total_done   = sum([swot_count, pestel_count, c5_count, soar_count, vmost_count])

    frameworks = [
        {
            "key": "swot",   "label": "SWOT",
            "color": "#2563eb",  "light": "#dbeafe",
            "title": "SWOT Analysis",
            "desc": "Kekuatan, Kelemahan, Peluang, Ancaman",
            "url": "analisis_swot",   "count": swot_count,
            "icon": "<svg width='22' height='22' fill='none' stroke='currentColor' stroke-width='2' viewBox='0 0 24 24'><rect x='3' y='3' width='8' height='8' rx='1'/><rect x='13' y='3' width='8' height='8' rx='1'/><rect x='3' y='13' width='8' height='8' rx='1'/><rect x='13' y='13' width='8' height='8' rx='1'/></svg>",
        },
        {
            "key": "pestel", "label": "PESTEL",
            "color": "#059669",  "light": "#d1fae5",
            "title": "PESTEL Analysis",
            "desc": "Politik, Ekonomi, Sosial, Teknologi, Alam, Undang-Undang",
            "url": "analisis_pestel", "count": pestel_count,
            "icon": "<svg width='22' height='22' fill='none' stroke='currentColor' stroke-width='2' viewBox='0 0 24 24'><circle cx='12' cy='12' r='9'/><path stroke-linecap='round' d='M12 3a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z'/><path stroke-linecap='round' d='M3 12h18'/></svg>",
        },
        {
            "key": "5c",     "label": "5C",
            "color": "#d97706", "light": "#fef3c7",
            "title": "5C Analysis",
            "desc": "Syarikat, Pelanggan, Pesaing, Rakan Kongsi, Persekitaran",
            "url": "analisis_5c",     "count": c5_count,
            "icon": "<svg width='22' height='22' fill='none' stroke='currentColor' stroke-width='2' viewBox='0 0 24 24'><path stroke-linecap='round' stroke-linejoin='round' d='M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z'/></svg>",
        },
        {
            "key": "soar",   "label": "SOAR",
            "color": "#0891b2", "light": "#cffafe",
            "title": "SOAR Analysis",
            "desc": "Strengths, Opportunities, Aspirations, Results",
            "url": "analisis_soar",   "count": soar_count,
            "icon": "<svg width='22' height='22' fill='none' stroke='currentColor' stroke-width='2' viewBox='0 0 24 24'><path stroke-linecap='round' stroke-linejoin='round' d='M5 3l14 9-14 9V3z'/></svg>",
        },
        {
            "key": "vmost",  "label": "VMOST",
            "color": "#7c3aed", "light": "#ede9fe",
            "title": "VMOST Analysis",
            "desc": "Vision, Mission, Objectives, Strategies, Tactics",
            "url": "analisis_vmost",  "count": vmost_count,
            "icon": "<svg width='22' height='22' fill='none' stroke='currentColor' stroke-width='2' viewBox='0 0 24 24'><path stroke-linecap='round' stroke-linejoin='round' d='M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7'/></svg>",
        },
    ]

    return render(request, "bengkel/analisis/spaf_situational.html", {
        "bengkel": bengkel,
        "frameworks": frameworks,
        "total_done": total_done,
    })


@login_required
def analisis_swot(request):
    from .models import AnalisisSWOT
    jemputan = Jemputan.objects.filter(user=request.user, status="accepted").select_related("bengkel").order_by("-created_at").first()
    if not jemputan:
        return redirect("bengkel:dashboard")
    bengkel = jemputan.bengkel
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
    return render(request, 'bengkel/analisis/swot.html', {'bengkel': bengkel, 'existing': existing, 'saved': saved})


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
    jemputan = Jemputan.objects.filter(user=request.user, status="accepted").select_related("bengkel").order_by("-created_at").first()
    if not jemputan:
        return redirect("bengkel:dashboard")
    bengkel = jemputan.bengkel
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
    return render(request, 'bengkel/analisis/pestel.html', {'bengkel': bengkel, 'existing': existing})


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
    jemputan = Jemputan.objects.filter(user=request.user, status="accepted").select_related("bengkel").order_by("-created_at").first()
    if not jemputan:
        return redirect("bengkel:dashboard")
    bengkel = jemputan.bengkel
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
    return render(request, 'bengkel/analisis/vmost.html', {'bengkel': bengkel, 'existing': existing})


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
    jemputan = Jemputan.objects.filter(user=request.user, status="accepted").select_related("bengkel").order_by("-created_at").first()
    if not jemputan:
        return redirect("bengkel:dashboard")
    bengkel = jemputan.bengkel
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
    return render(request, 'bengkel/analisis/5c.html', {'bengkel': bengkel, 'existing': existing})


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
    jemputan = Jemputan.objects.filter(user=request.user, status="accepted").select_related("bengkel").order_by("-created_at").first()
    if not jemputan:
        return redirect("bengkel:dashboard")
    bengkel = jemputan.bengkel
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
    return render(request, 'bengkel/analisis/soar.html', {'bengkel': bengkel, 'existing': existing})


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
            # --- Try AI generation (optional) --------------------------
            ai_ok = False
            try:
                import json
                from django.conf import settings as _cfg
                if _cfg.GEMINI_API_KEY:
                    from google import genai as _genai
                    _client = _genai.Client(api_key=_cfg.GEMINI_API_KEY)
                    sep = "\n"
                    pp_list = sep.join("%d. %s" % (i, t) for i, t in enumerate(raw_pps, 1))
                    _prompt = (
                        "Anda adalah pakar analisis masalah dalam konteks organisasi sektor awam Malaysia."
                        + sep + sep
                        + "Berdasarkan senarai Pain Point berikut, jana SATU ayat Pernyataan Masalah Utama dalam BAHASA MELAYU yang jelas, padat, dan tepat."
                        + sep + sep
                        + "Senarai Pain Point:" + sep + pp_list
                        + sep + sep
                        + "Jana respons dalam format JSON SAHAJA (tanpa markdown, tanpa ```json), dengan satu medan:"
                        + sep + '{"masalah_utama":"..."}'
                    )
                    _MODELS = ["gemini-3-flash-preview", "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash"]
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
                        ai_ok = True
            except Exception as _e:
                request.session["spaf_ai_error"] = str(_e)
            if ai_ok:
                messages.success(request, "%d Pain Point disimpan. AI berjaya jana cadangan Problem Statement." % len(raw_pps))
            else:
                messages.success(request, "%d Pain Point disimpan. Sila isi Problem Statement secara manual." % len(raw_pps))
                request.session.pop("spaf_ai_error", None)
            request.session.modified = True
            return redirect(bp_url + "?tab=ps")

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
            return redirect(bp_url + "?tab=ps")

        # ── Delete Problem Statement ────────────────────────────────────────
        elif action == "del_ps":
            pid = request.POST.get("ps_id")
            SpafProblemStatement.objects.filter(pk=pid, user=request.user).delete()
            return redirect(bp_url + "?tab=ps")

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
                _MODELS = ["gemini-3-flash-preview", "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash"]
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

    # Count situational analysis records for Module 3
    sit_swot_count   = AnalisisSWOT.objects.filter(user=request.user).count()
    sit_pestel_count = AnalisisPESTEL.objects.filter(user=request.user).count()
    sit_c5_count     = Analisis5C.objects.filter(user=request.user).count()
    sit_soar_count   = AnalisisSOAR.objects.filter(user=request.user).count()
    sit_vmost_count  = AnalisisVMOST.objects.filter(user=request.user).count()
    sit_total        = sit_swot_count + sit_pestel_count + sit_c5_count + sit_soar_count + sit_vmost_count

    # SPAF pipeline progress (2 core steps + 3 situational steps)
    done = sum([
        pain_points.count() > 0,
        prob_stmts.count() > 0,
    ])
    spaf_progress = int(done / 2 * 100)

    return render(request, "bengkel/blueprint_peserta.html", {
        "bengkel":        bengkel,
        "jemputan":       jemputan,
        "pain_points":    pain_points,
        "prob_stmts":     prob_stmts,
        "contribution":   contribution,
        "themes":         themes,
        "generated":      generated,
        "ai_error":      ai_error,
        "active_tab":     active_tab,
        "spaf_progress":  spaf_progress,
        "sit_swot_count": sit_swot_count,
        "sit_pestel_count": sit_pestel_count,
        "sit_c5_count":   sit_c5_count,
        "sit_soar_count": sit_soar_count,
        "sit_vmost_count": sit_vmost_count,
        "sit_total":      sit_total,
    })


# ── SPAF standalone pages ────────────────────────────────────────────────

def _get_bengkel_for_user(request):
    """Get user's active bengkel from latest accepted invitation."""
    jemputan = Jemputan.objects.filter(user=request.user, status="accepted").select_related("bengkel").order_by("-created_at").first()
    return jemputan.bengkel if jemputan else None


@login_required
def spaf_pain_point(request):
    # Find bengkel from user's latest accepted invitation
    jemputan = Jemputan.objects.filter(user=request.user, status="accepted").select_related("bengkel").order_by("-created_at").first()
    if not jemputan:
        return redirect("bengkel:dashboard")
    bengkel = jemputan.bengkel

    pain_points = SpafPainPoint.objects.filter(user=request.user).order_by("-created_at")

    # Handle form submission — save Pain Points
    if request.method == "POST":
        raw_pps = [v.strip() for k, v in request.POST.items() if k.startswith("pain_point_") and v.strip()]
        if raw_pps:
            SpafPainPoint.objects.filter(user=request.user).delete()
            for i, text in enumerate(raw_pps, 1):
                SpafPainPoint.objects.create(
                    user=request.user,
                    tajuk="Pain Point %d" % i,
                    keterangan=text,
                    kesan="",
                    keutamaan="sederhana",
                    catatan="",
                )
            # Try AI generation — store in session for PS page
            ai_ok = False
            try:
                import json
                from django.conf import settings as _cfg
                if _cfg.GEMINI_API_KEY:
                    from google import genai as _genai
                    _client = _genai.Client(api_key=_cfg.GEMINI_API_KEY)
                    sep = "\n"
                    pp_list = sep.join("%d. %s" % (i, t) for i, t in enumerate(raw_pps, 1))
                    _prompt = (
                        "Anda adalah pakar analisis masalah dalam konteks organisasi sektor awam Malaysia."
                        + sep + sep
                        + "Berdasarkan senarai Pain Point berikut, jana SATU ayat Pernyataan Masalah Utama dalam BAHASA MELAYU yang jelas, padat, dan tepat."
                        + sep + sep
                        + "Senarai Pain Point:" + sep + pp_list
                        + sep + sep
                        + "Jana respons dalam format JSON SAHAJA (tanpa markdown, tanpa ```json), dengan satu medan:"
                        + sep + '{"masalah_utama":"..."}'
                    )
                    _MODELS = ["gemini-3-flash-preview", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
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
                        request.session.pop("spaf_ai_error", None)
                        ai_ok = True
            except Exception as _e:
                request.session["spaf_ai_error"] = str(_e)
            request.session.modified = True
            messages.success(request, "%d Pain Point disimpan. Sila lengkapkan Problem Statement seterusnya." % len(raw_pps))
            return redirect("bengkel:spaf_problem_statement")
        messages.warning(request, "Sila isi sekurang-kurangnya satu Pain Point.")
        return redirect("bengkel:spaf_pain_point")

    # Handle delete
    if request.method == "POST" and request.POST.get("del_pp"):
        SpafPainPoint.objects.filter(pk=request.POST["del_pp"], user=request.user).delete()
        messages.success(request, "Pain Point dipadam.")
        return redirect("bengkel:spaf_pain_point")

    # Initial form: load existing pain points into form fields
    existing = list(pain_points.values_list("keterangan", flat=True))
    if not existing:
        existing = [""]

    return render(request, "bengkel/analisis/spaf_pain_point.html", {
        "bengkel":     bengkel,
        "pain_points": pain_points,
        "existing":    existing,
    })


@login_required
def spaf_problem_statement(request):
    bengkel = _get_bengkel_for_user(request)
    if not bengkel:
        return redirect("bengkel:dashboard")

    prob_stmts = SpafProblemStatement.objects.filter(user=request.user).order_by("-created_at")
    generated  = request.session.pop("spaf_generated_ps", None)
    ai_error   = request.session.pop("spaf_ai_error", None)
    request.session.modified = True

    # Handle save PS
    # Handle delete
    if request.method == "POST" and request.POST.get("del_ps"):
        SpafProblemStatement.objects.filter(pk=request.POST["del_ps"], user=request.user).delete()
        messages.success(request, "Problem Statement dipadam.")
        return redirect("bengkel:spaf_problem_statement")

    if request.method == "POST":
        masalah = request.POST.get("masalah_utama", "").strip()
        if masalah:
            SpafProblemStatement.objects.create(
                user=request.user,
                masalah_utama=masalah,
                skop=request.POST.get("skop", ""),
                sasaran=request.POST.get("sasaran", ""),
                matlamat=request.POST.get("matlamat", ""),
                catatan=request.POST.get("catatan", ""),
            )
            messages.success(request, "Problem Statement berjaya disimpan.")
        else:
            messages.warning(request, "Sila isi ruangan Pernyataan Masalah.")
        return redirect("bengkel:spaf_problem_statement")

    return render(request, "bengkel/analisis/spaf_problem_statement.html", {
        "bengkel":     bengkel,
        "prob_stmts": prob_stmts,
        "generated":  generated,
        "ai_error":   ai_error,
    })


@login_required
def spaf_hub(request):
    # Find the user's active bengkel (latest accepted invitation)
    jemputan = Jemputan.objects.filter(user=request.user, status="accepted").select_related("bengkel").order_by("-created_at").first()
    if not jemputan:
        return redirect("bengkel:dashboard")
    bengkel = jemputan.bengkel

    # Count records for progress
    pain_point_count = SpafPainPoint.objects.filter(user=request.user).count()
    ps_count         = SpafProblemStatement.objects.filter(user=request.user).count()
    swot_count       = AnalisisSWOT.objects.filter(bengkel=bengkel).count()
    pestel_count     = AnalisisPESTEL.objects.filter(bengkel=bengkel).count()
    rca_count        = SpafRootCauseAnalysis.objects.filter(user=request.user).count()
    rcv_count        = SpafRootCauseValidation.objects.filter(user=request.user).count()
    risk_count        = SpafRiskAnalysis.objects.filter(user=request.user).count()

    # Pipeline progress: 1=PP, 2=PS, 3=Situational, 4=RCA, 5=RCV, 6=Risk
    done = sum([
        pain_point_count > 0,
        ps_count > 0,
        swot_count > 0 or pestel_count > 0,
        rca_count > 0,
        rcv_count > 0,
        risk_count > 0,
    ])
    progress = int(done / 6 * 100)

    modules = [
        {
            "num": 1, "color": "#be185d",   "light": "#fce7f3",   "border": "#fbcfe8",
            "title": "Pain Points Analytics",
            "desc":  "Collection, deduplication, and clustering of raw complaints from 300 participants.",
            "url":   f"/bengkel/{bengkel.pk}/blueprint/?tab=spaf",
            "count": pain_point_count,
        },
        {
            "num": 2, "color": "#7c3aed",   "light": "#ede9fe",   "border": "#ddd6fe",
            "title": "Problem Statements",
            "desc":  "Formulation of master problem statements based on combined Pain Point clusters.",
            "url":   f"/bengkel/{bengkel.pk}/blueprint/?tab=ps",
            "count": ps_count,
        },
        {
            "num": 3, "color": "#1d4ed8",   "light": "#dbeafe",   "border": "#bfdbfe",
            "title": "Situational Analysis",
            "desc":  "Environmental scanning (As-Is State) utilizing AI-driven PESTLE/SWOT frameworks.",
            "url":   f"/bengkel/{bengkel.pk}/blueprint/?tab=tema",
            "count": swot_count + pestel_count,
        },
        {
            "num": 4, "color": "#b45309",   "light": "#fef3c7",   "border": "#fde68a",
            "title": "Root Cause Analysis",
            "desc":  "Identification of root causes (Ishikawa / 5 Whys methodology) for each Problem Statement.",
            "url":   f"/bengkel/{bengkel.pk}/blueprint/?tab=teras",
            "count": rca_count,
        },
        {
            "num": 5, "color": "#047857",   "light": "#d1fae5",   "border": "#a7f3d0",
            "title": "Root Cause Validation",
            "desc":  "Validation process of root causes via cross-referencing against the 1.2M word corpus data.",
            "url":   f"/bengkel/{bengkel.pk}/blueprint/?tab=strategi",
            "count": rcv_count,
        },
        {
            "num": 6, "color": "#b91c1c",   "light": "#fee2e2",   "border": "#fecaca",
            "title": "Risk Analysis",
            "desc":  "Projection of risk matrices if the Problem Statements are left without intervention plans.",
            "url":   f"/bengkel/{bengkel.pk}/blueprint/?tab=indikator",
            "count": risk_count,
        },
    ]

    return render(request, "bengkel/analisis/spaf_hub.html", {
        "bengkel":   bengkel,
        "modules":   modules,
        "progress":  progress,
    })

@login_required
def spaf_pain_point_delete(request, pk):
    SpafPainPoint.objects.filter(pk=pk, user=request.user).delete()
    messages.success(request, "Pain Point dipadam.")
    return redirect("bengkel:spaf_pain_point")


@login_required
def spaf_problem_statement_delete(request, pk):
    SpafProblemStatement.objects.filter(pk=pk, user=request.user).delete()
    messages.success(request, "Problem Statement dipadam.")
    return redirect("bengkel:spaf_problem_statement")


@login_required
def spaf_rca(request):
    from .models import SpafRootCauseAnalysis
    jemputan = Jemputan.objects.filter(user=request.user, status="accepted").select_related("bengkel").order_by("-created_at").first()
    if not jemputan:
        return redirect("bengkel:dashboard")
    bengkel = jemputan.bengkel
    existing = SpafRootCauseAnalysis.objects.filter(user=request.user).order_by("-created_at")
    if request.method == "POST":
        SpafRootCauseAnalysis.objects.create(
            user=request.user,
            masalah=request.POST.get("masalah", ""),
            punca_utama=request.POST.get("punca_utama", ""),
            punca_penyumbang=request.POST.get("punca_penyumbang", ""),
            bukti=request.POST.get("bukti", ""),
            catatan=request.POST.get("catatan", ""),
        )
        messages.success(request, "Root Cause Analysis berjaya disimpan.")
        return redirect("bengkel:spaf_rca")
    return render(request, "bengkel/analisis/spaf_rca.html", {
        "bengkel": bengkel, "existing": existing
    })



@login_required
def spaf_rca_delete(request, pk):
    from .models import SpafRootCauseAnalysis
    SpafRootCauseAnalysis.objects.filter(pk=pk, user=request.user).delete()
    messages.success(request, "Rekod dipadam.")
    return redirect("bengkel:spaf_rca")

@login_required
def spaf_rcv(request):
    from .models import SpafRootCauseValidation
    jemputan = Jemputan.objects.filter(user=request.user, status="accepted").select_related("bengkel").order_by("-created_at").first()
    if not jemputan:
        return redirect("bengkel:dashboard")
    bengkel = jemputan.bengkel
    existing = SpafRootCauseValidation.objects.filter(user=request.user).order_by("-created_at")
    if request.method == "POST":
        SpafRootCauseValidation.objects.create(
            user=request.user,
            punca=request.POST.get("punca", ""),
            kaedah=request.POST.get("kaedah", ""),
            dapatan=request.POST.get("dapatan", ""),
            kesimpulan=request.POST.get("kesimpulan", ""),
            catatan=request.POST.get("catatan", ""),
        )
        messages.success(request, "Root Cause Validation berjaya disimpan.")
        return redirect("bengkel:spaf_rcv")
    return render(request, "bengkel/analisis/spaf_rcv.html", {
        "bengkel": bengkel, "existing": existing
    })



@login_required
def spaf_rcv_delete(request, pk):
    from .models import SpafRootCauseValidation
    SpafRootCauseValidation.objects.filter(pk=pk, user=request.user).delete()
    messages.success(request, "Rekod dipadam.")
    return redirect("bengkel:spaf_rcv")



@login_required
def spaf_risk(request):
    from .models import SpafRiskAnalysis
    jemputan = Jemputan.objects.filter(user=request.user, status="accepted").select_related("bengkel").order_by("-created_at").first()
    if not jemputan:
        return redirect("bengkel:dashboard")
    bengkel = jemputan.bengkel
    existing = SpafRiskAnalysis.objects.filter(user=request.user).order_by("-created_at")
    if request.method == "POST":
        SpafRiskAnalysis.objects.create(
            user=request.user,
            risiko=request.POST.get("risiko", ""),
            kemungkinan=request.POST.get("kemungkinan", "sederhana"),
            impak=request.POST.get("impak", "sederhana"),
            mitigasi=request.POST.get("mitigasi", ""),
            pemilik=request.POST.get("pemilik", ""),
            catatan=request.POST.get("catatan", ""),
        )
        messages.success(request, "Risk Analysis berjaya disimpan.")
        return redirect("bengkel:spaf_risk")
    return render(request, "bengkel/analisis/spaf_risk.html", {
        "bengkel": bengkel, "existing": existing
    })


@login_required
def spaf_risk_delete(request, pk):
    from .models import SpafRiskAnalysis
    SpafRiskAnalysis.objects.filter(pk=pk, user=request.user).delete()
    messages.success(request, "Rekod dipadam.")
    return redirect("bengkel:spaf_risk")


