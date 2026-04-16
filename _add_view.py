path = r'c:\Users\rahma\Desktop\blueprint\backend\bengkel\views.py'

view_code = '''

@login_required
def blueprint_peserta(request, pk):
    """User-facing blueprint progress page — main activity hub for participants."""
    from .models import BengkelContribution, ContributionFile, SpafPainPoint, SpafProblemStatement

    bengkel    = get_object_or_404(Bengkel, pk=pk)
    jemputan   = get_object_or_404(Jemputan, bengkel=bengkel, user=request.user, status="accepted")
    blueprint_url = reverse("bengkel:blueprint_peserta", kwargs={"pk": pk})

    if request.method == "POST":
        action = request.POST.get("action", "")

        # ── Upload file rujukan
        if action == "upload_file":
            if not jemputan.sudah_hadir:
                messages.error(request, "Anda perlu hadir ke bengkel dahulu sebelum boleh muat naik rujukan.")
            else:
                contribution, _ = BengkelContribution.objects.get_or_create(
                    bengkel=bengkel, jemputan=jemputan
                )
                files     = request.FILES.getlist("files")
                summaries = [request.POST.get(f"file_summary_{i}", "").strip() for i in range(len(files))]
                for f, summary in zip(files, summaries):
                    ContributionFile.objects.create(
                        contribution=contribution,
                        file=f,
                        original_name=f.name,
                        summary=summary,
                    )
                comment = request.POST.get("comment", "").strip()
                if comment:
                    contribution.comment = comment
                    contribution.save()
                if files:
                    messages.success(request, f"{len(files)} fail berjaya dimuat naik.")
                elif comment:
                    messages.success(request, "Komen anda telah disimpan.")
            return redirect(blueprint_url + "?tab=rujukan")

        # ── Delete contribution file
        elif action == "del_file":
            fid = request.POST.get("file_id")
            try:
                cf = ContributionFile.objects.get(pk=fid, contribution__jemputan=jemputan)
                cf.delete()
                messages.success(request, "Fail dipadam.")
            except ContributionFile.DoesNotExist:
                pass
            return redirect(blueprint_url + "?tab=rujukan")

        # ── Save Pain Points + generate Problem Statement via AI
        elif action == "pain_point":
            pain_points_raw = [p.strip() for p in request.POST.getlist("pain_point") if p.strip()]
            if not pain_points_raw:
                messages.error(request, "Sila isi sekurang-kurangnya satu Pain Point.")
                return redirect(blueprint_url + "?tab=spaf")
            created = []
            for i, text in enumerate(pain_points_raw, 1):
                obj = SpafPainPoint.objects.create(
                    user=request.user,
                    tajuk=f"Pain Point {i}",
                    keterangan=text,
                    kesan="",
                    keutamaan="sederhana",
                    catatan="",
                )
                created.append(obj)
            messages.success(request, f"{len(created)} Pain Point disimpan. AI sedang jana cadangan Problem Statement...")
            # ── Gemini AI generation
            try:
                import json
                from google import genai as _genai
                from django.conf import settings as _cfg
                _client = _genai.Client(api_key=_cfg.GEMINI_API_KEY)
                pp_list = "\n".join(f"{i}. {t}" for i, t in enumerate(pain_points_raw, 1))
                _prompt = (
                    "Anda adalah pakar analisis masalah dalam konteks organisasi sektor awam Malaysia.\n\n"
                    "Berdasarkan senarai Pain Point berikut, jana Problem Statement yang terstruktur dalam BAHASA MELAYU.\n\n"
                    f"Senarai Pain Point:\n{pp_list}\n\n"
                    'Jana respons dalam format JSON SAHAJA (tanpa markdown, tanpa ```json), dengan 4 medan:\n'
                    '{"masalah_utama":"...","skop":"...","sasaran":"...","matlamat":"..."}'
                )
                _MODELS = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-2.0-flash"]
                raw = None
                for _m in _MODELS:
                    try:
                        raw = _client.models.generate_content(model=_m, contents=_prompt).text.strip()
                        break
                    except Exception:
                        continue
                if raw:
                    if raw.startswith("```"):
                        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                    request.session["spaf_generated_ps"] = json.loads(raw)
                    request.session["spaf_ai_error"] = None
            except Exception as _e:
                request.session["spaf_ai_error"] = str(_e)
            request.session.modified = True
            return redirect(blueprint_url + "?tab=ps")

        # ── Delete Pain Point
        elif action == "del_pp":
            pid = request.POST.get("pp_id")
            SpafPainPoint.objects.filter(pk=pid, user=request.user).delete()
            return redirect(blueprint_url + "?tab=spaf")

        # ── Save Problem Statement (manual or from AI suggestion)
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
            return redirect(blueprint_url + "?tab=ps")

        # ── Delete Problem Statement
        elif action == "del_ps":
            pid = request.POST.get("ps_id")
            SpafProblemStatement.objects.filter(pk=pid, user=request.user).delete()
            return redirect(blueprint_url + "?tab=ps")

    pain_points  = SpafPainPoint.objects.filter(user=request.user).order_by("-created_at")
    prob_stmts   = SpafProblemStatement.objects.filter(user=request.user).order_by("-created_at")
    contribution = getattr(jemputan, "contribution", None)
    themes       = bengkel.blueprint_themes.all()
    generated    = request.session.pop("spaf_generated_ps", None)
    ai_error     = request.session.pop("spaf_ai_error", None)
    request.session.modified = True

    active_tab = request.GET.get("tab", "rujukan")

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
'''

with open(path, 'a', encoding='utf-8') as f:
    f.write(view_code)

print("appended — verifying...")
text = open(path, encoding='utf-8').read()
print("blueprint_peserta found:", "def blueprint_peserta" in text)
print("tab=ps found:", "?tab=ps" in text)
