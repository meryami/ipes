content = r"""<!DOCTYPE html>
<html lang="ms">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Portal Peserta — NDHB</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet"/>
  <style>
    *{box-sizing:border-box}
    body{font-family:"Inter",sans-serif;background:#f1f5f9;color:#0f172a;margin:0;min-height:100vh}
    .card{background:#fff;border-radius:12px;border:1px solid #e2e8f0;box-shadow:0 1px 3px rgba(0,0,0,.06)}
    .badge{display:inline-flex;align-items:center;gap:3px;padding:2px 9px;border-radius:99px;font-size:11px;font-weight:700}
    .btn{display:inline-flex;align-items:center;gap:6px;padding:9px 16px;border-radius:8px;font-size:12.5px;font-weight:700;text-decoration:none;transition:opacity .15s}
    .btn:hover{opacity:.82}
    .cd-unit{background:#1e3a8a;border-radius:8px;padding:9px 14px;text-align:center;min-width:50px}
    hr.dv{border:none;border-top:1px solid #f1f5f9;margin:0}
    .sec-hd{font-size:10.5px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:#94a3b8;margin-bottom:12px}

    /* PAGE system */
    .page{display:none}
    .page.active{display:block;animation:fu .22s ease both}
    @keyframes fu{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:translateY(0)}}

    /* ── Top bar (brand + profile) ── */
    .topbar{background:#0f172a;border-bottom:1px solid rgba(255,255,255,.07);position:sticky;top:0;z-index:50}

    /* ── Navbar ── */
    .navbar{background:#fff;border-bottom:1px solid #e2e8f0;position:sticky;top:52px;z-index:40;box-shadow:0 1px 4px rgba(0,0,0,.04)}
    .nav-item{display:inline-flex;align-items:center;gap:7px;padding:0 18px;height:44px;font-size:12.5px;font-weight:600;color:#64748b;border:none;background:transparent;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px;transition:all .18s;white-space:nowrap;text-decoration:none}
    .nav-item.active{color:#1e40af;border-bottom-color:#1e40af;font-weight:700}
    .nav-item:hover:not(.active){color:#334155;background:#f8fafc}
  </style>
</head>
<body class="pb-16">

<!-- ══ TOP BAR (brand + user) ══ -->
<div class="topbar">
  <div style="max-width:900px;margin:0 auto;padding:0 20px;height:52px;display:flex;align-items:center;justify-content:space-between">
    <!-- Brand -->
    <div style="display:flex;align-items:center;gap:10px">
      <div style="width:32px;height:32px;border-radius:8px;background:#2563eb;color:#fff;font-weight:800;font-size:13px;display:flex;align-items:center;justify-content:center;flex-shrink:0">
        {{ user.first_name|first|upper|default:user.username|first|upper }}{{ user.last_name|first|upper }}
      </div>
      <div>
        <div style="font-size:9px;color:rgba(255,255,255,.28);font-weight:700;letter-spacing:.12em;text-transform:uppercase">Portal Peserta</div>
        <div style="font-size:13px;color:#fff;font-weight:600;line-height:1.15">{{ user.get_full_name|default:user.username }}</div>
      </div>
    </div>
    <!-- Actions -->
    <div style="display:flex;align-items:center;gap:3px">
      <a href="{% url 'bengkel:edit_profile' %}" style="padding:6px 11px;border-radius:6px;font-size:12px;font-weight:600;color:rgba(255,255,255,.38);text-decoration:none;transition:.15s" onmouseover="this.style.color='#fff';this.style.background='rgba(255,255,255,.09)'" onmouseout="this.style.color='rgba(255,255,255,.38)';this.style.background='transparent'">Profil</a>
      <form method="post" action="{% url 'logout' %}">{% csrf_token %}
        <button style="padding:6px 11px;border:none;border-radius:6px;font-size:12px;font-weight:600;color:rgba(252,165,165,.5);background:transparent;cursor:pointer;transition:.15s" onmouseover="this.style.color='#fca5a5';this.style.background='rgba(255,255,255,.07)'" onmouseout="this.style.color='rgba(252,165,165,.5)';this.style.background='transparent'">Keluar</button>
      </form>
    </div>
  </div>
</div>

<!-- ══ NAVBAR ══ -->
<div class="navbar">
  <div style="max-width:900px;margin:0 auto;padding:0 20px;display:flex;overflow-x:auto;scrollbar-width:none">
    <button class="nav-item active" onclick="goPage('home',this)">
      <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>
      Utama
    </button>
    <button class="nav-item" onclick="goPage('bengkel',this)">
      <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
      Bengkel
    </button>
    <button class="nav-item" onclick="goPage('situational',this)">
      <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
      Situational Analysis
    </button>
    <button class="nav-item" onclick="goPage('tentative',this)">
      <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
      Tentative
    </button>
  </div>
</div>

<!-- ══ PAGE CONTENT ══ -->
<div style="max-width:900px;margin:0 auto;padding:28px 20px">

  {% if messages %}
  <div style="margin-bottom:18px">
    {% for m in messages %}
    <div style="padding:12px 15px;border-radius:9px;font-size:13px;font-weight:600;margin-bottom:6px;{% if m.tags == 'success' %}background:#f0fdf4;color:#166534;border:1px solid #bbf7d0{% else %}background:#fef2f2;color:#991b1b;border:1px solid #fecaca{% endif %}">{{ m }}</div>
    {% endfor %}
  </div>
  {% endif %}

  <!-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       PAGE: UTAMA
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
  <div id="page-home" class="page active">

    <!-- Hero -->
    <div style="background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 55%,#1d4ed8 100%);border-radius:16px;padding:32px 28px 30px;margin-bottom:22px">
      <p style="font-size:12px;color:rgba(255,255,255,.3);margin:0 0 4px">{{ user.email }}</p>
      <h1 style="font-size:26px;font-weight:800;color:#fff;margin:0 0 4px;line-height:1.25">Selamat Datang 👋</h1>
      <p style="font-size:13px;color:rgba(255,255,255,.38);margin:0 0 26px">Papan pemuka program bengkel anda</p>

      <!-- Stats -->
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">
        <div style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:14px 12px;text-align:center">
          <div style="font-size:28px;font-weight:800;color:#fff;line-height:1">{{ stats.total_jemputan }}</div>
          <div style="font-size:9.5px;font-weight:700;color:rgba(255,255,255,.3);margin-top:5px;letter-spacing:.06em;text-transform:uppercase">Jemputan</div>
        </div>
        <div style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:14px 12px;text-align:center">
          <div style="font-size:28px;font-weight:800;color:#34d399;line-height:1">{{ stats.total_diterima }}</div>
          <div style="font-size:9.5px;font-weight:700;color:rgba(255,255,255,.3);margin-top:5px;letter-spacing:.06em;text-transform:uppercase">Diterima</div>
        </div>
        <div style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:14px 12px;text-align:center">
          <div style="font-size:28px;font-weight:800;color:#fbbf24;line-height:1">{{ stats.total_hadir }}</div>
          <div style="font-size:9.5px;font-weight:700;color:rgba(255,255,255,.3);margin-top:5px;letter-spacing:.06em;text-transform:uppercase">Hadir</div>
        </div>
        <div style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:14px 12px;text-align:center">
          <div style="font-size:28px;font-weight:800;color:#a78bfa;line-height:1">{{ stats.total_pernyataan }}</div>
          <div style="font-size:9.5px;font-weight:700;color:rgba(255,255,255,.3);margin-top:5px;letter-spacing:.06em;text-transform:uppercase">Pernyataan</div>
        </div>
      </div>
    </div>

    <!-- Quick nav cards -->
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
      <button onclick="goPage('bengkel', document.querySelector('[onclick*=bengkel]'))" style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:20px 18px;text-align:left;cursor:pointer;transition:all .18s;box-shadow:0 1px 3px rgba(0,0,0,.06)" onmouseover="this.style.boxShadow='0 6px 20px rgba(30,64,175,.12)';this.style.borderColor='#bfdbfe'" onmouseout="this.style.boxShadow='0 1px 3px rgba(0,0,0,.06)';this.style.borderColor='#e2e8f0'">
        <div style="width:36px;height:36px;border-radius:8px;background:#eff6ff;display:flex;align-items:center;justify-content:center;margin-bottom:10px;font-size:17px">📅</div>
        <div style="font-size:13.5px;font-weight:700;color:#0f172a;margin-bottom:3px">Bengkel</div>
        <div style="font-size:11.5px;color:#94a3b8">Lihat bengkel aktif & countdown</div>
      </button>
      <button onclick="goPage('situational', document.querySelector('[onclick*=situational]'))" style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:20px 18px;text-align:left;cursor:pointer;transition:all .18s;box-shadow:0 1px 3px rgba(0,0,0,.06)" onmouseover="this.style.boxShadow='0 6px 20px rgba(30,64,175,.12)';this.style.borderColor='#bfdbfe'" onmouseout="this.style.boxShadow='0 1px 3px rgba(0,0,0,.06)';this.style.borderColor='#e2e8f0'">
        <div style="width:36px;height:36px;border-radius:8px;background:#f0fdf4;display:flex;align-items:center;justify-content:center;margin-bottom:10px;font-size:17px">📊</div>
        <div style="font-size:13.5px;font-weight:700;color:#0f172a;margin-bottom:3px">Situational</div>
        <div style="font-size:11.5px;color:#94a3b8">Status jemputan & tindakan</div>
      </button>
      <button onclick="goPage('tentative', document.querySelector('[onclick*=tentative]'))" style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:20px 18px;text-align:left;cursor:pointer;transition:all .18s;box-shadow:0 1px 3px rgba(0,0,0,.06)" onmouseover="this.style.boxShadow='0 6px 20px rgba(30,64,175,.12)';this.style.borderColor='#bfdbfe'" onmouseout="this.style.boxShadow='0 1px 3px rgba(0,0,0,.06)';this.style.borderColor='#e2e8f0'">
        <div style="width:36px;height:36px;border-radius:8px;background:#faf5ff;display:flex;align-items:center;justify-content:center;margin-bottom:10px;font-size:17px">📋</div>
        <div style="font-size:13.5px;font-weight:700;color:#0f172a;margin-bottom:3px">Tentative</div>
        <div style="font-size:11.5px;color:#94a3b8">Jadual & butiran bengkel</div>
      </button>
    </div>

    <!-- Recent activity preview -->
    {% if jemputan_list %}
    <div style="margin-top:22px">
      <div class="sec-hd">Jemputan Terkini</div>
      {% for j in jemputan_list|slice:":3" %}
      <div class="card" style="display:flex;align-items:center;gap:12px;padding:14px 16px;margin-bottom:8px">
        <div style="width:8px;height:8px;border-radius:50%;flex-shrink:0;{% if j.status == 'accepted' %}background:#10b981{% elif j.status == 'rejected' %}background:#ef4444{% else %}background:#f59e0b{% endif %}"></div>
        <div style="flex:1;min-width:0">
          <div style="font-size:13.5px;font-weight:600;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ j.bengkel.title }}</div>
          <div style="font-size:11.5px;color:#94a3b8;margin-top:1px">{{ j.bengkel.tarikh|date:"d M Y, H:i" }} · {{ j.bengkel.lokasi_nama }}</div>
        </div>
        {% if j.status == 'accepted' %}<span class="badge" style="background:#dcfce7;color:#15803d;flex-shrink:0">Diterima</span>
        {% elif j.status == 'rejected' %}<span class="badge" style="background:#fee2e2;color:#b91c1c;flex-shrink:0">Ditolak</span>
        {% else %}<span class="badge" style="background:#fef3c7;color:#b45309;flex-shrink:0">Menunggu</span>{% endif %}
      </div>
      {% endfor %}
    </div>
    {% endif %}

  </div>

  <!-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       PAGE: BENGKEL
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
  <div id="page-bengkel" class="page">
    <div class="sec-hd">Bengkel Aktif</div>

    {% if jemputan_list %}
      {% for j in jemputan_list %}{% if j.status == 'accepted' %}
      <div class="card overflow-hidden mb-5" style="box-shadow:0 4px 20px rgba(30,64,175,.1)">
        <!-- Dark header -->
        <div style="background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);padding:22px 22px 20px">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
            <span style="font-size:10px;font-weight:700;color:rgba(255,255,255,.33);letter-spacing:.1em;text-transform:uppercase">{{ j.bengkel.tarikh|date:"d M Y" }}</span>
            {% if j.sudah_hadir %}<span class="badge" style="background:rgba(16,185,129,.15);color:#6ee7b7;border:1px solid rgba(16,185,129,.2)">✓ Telah Hadir</span>
            {% else %}<span class="badge" style="background:rgba(251,191,36,.1);color:#fde68a;border:1px solid rgba(251,191,36,.2)">Dijemput</span>{% endif %}
          </div>
          <h2 style="font-size:19px;font-weight:800;color:#fff;margin:0 0 4px;line-height:1.3">{{ j.bengkel.title }}</h2>
          <p style="font-size:12px;color:rgba(255,255,255,.33);margin:0 0 18px">📍 {{ j.bengkel.lokasi_nama }}{% if j.bengkel.lokasi_alamat %}, {{ j.bengkel.lokasi_alamat }}{% endif %}</p>
          <div style="font-size:9px;font-weight:700;color:rgba(255,255,255,.2);letter-spacing:.1em;text-transform:uppercase;margin-bottom:7px">Masa Menuju Acara</div>
          <div style="display:flex;gap:7px" id="cd-{{ forloop.counter }}" data-dt="{{ j.bengkel.tarikh|date:'Y-m-d H:i:s' }}">
            <div class="cd-unit"><div style="font-size:20px;font-weight:800;color:#fff;line-height:1" class="cd-d">--</div><div style="font-size:8px;font-weight:600;color:rgba(255,255,255,.23);margin-top:4px">HARI</div></div>
            <div class="cd-unit"><div style="font-size:20px;font-weight:800;color:#fff;line-height:1" class="cd-h">--</div><div style="font-size:8px;font-weight:600;color:rgba(255,255,255,.23);margin-top:4px">JAM</div></div>
            <div class="cd-unit"><div style="font-size:20px;font-weight:800;color:#fff;line-height:1" class="cd-m">--</div><div style="font-size:8px;font-weight:600;color:rgba(255,255,255,.23);margin-top:4px">MINIT</div></div>
            <div class="cd-unit"><div style="font-size:20px;font-weight:800;color:#fff;line-height:1" class="cd-s">--</div><div style="font-size:8px;font-weight:600;color:rgba(255,255,255,.23);margin-top:4px">SAAT</div></div>
          </div>
        </div>
        <!-- Body -->
        <div style="padding:18px 22px">
          <div style="display:flex;gap:10px;align-items:center;margin-bottom:12px">
            <div style="width:30px;height:30px;border-radius:7px;background:#eff6ff;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:14px">🕐</div>
            <div>
              <div style="font-size:9.5px;font-weight:700;color:#94a3b8;letter-spacing:.07em;text-transform:uppercase;margin-bottom:1px">Masa</div>
              <div style="font-size:13px;font-weight:600;color:#0f172a">{{ j.bengkel.tarikh|date:"H:i" }}{% if j.bengkel.tarikh_tamat %} — {{ j.bengkel.tarikh_tamat|date:"H:i" }}{% endif %} <span style="font-size:11.5px;color:#94a3b8;font-weight:400">· {{ j.bengkel.tarikh|date:"d M Y" }}</span></div>
            </div>
          </div>
          <hr class="dv" style="margin-bottom:12px"/>
          <div style="display:flex;gap:10px;align-items:center;margin-bottom:14px">
            <div style="width:30px;height:30px;border-radius:7px;background:#faf5ff;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:14px">👤</div>
            <div>
              <div style="font-size:9.5px;font-weight:700;color:#94a3b8;letter-spacing:.07em;text-transform:uppercase;margin-bottom:1px">Penganjur</div>
              <div style="font-size:13px;font-weight:600;color:#0f172a">{{ j.bengkel.organizer_nama|default:"—" }}</div>
              {% if j.bengkel.organizer_email %}<div style="font-size:11px;color:#94a3b8">{{ j.bengkel.organizer_email }}</div>{% endif %}
            </div>
          </div>
          {% if j.bengkel.description %}
          <hr class="dv" style="margin-bottom:12px"/>
          <div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:14px">
            <div style="width:30px;height:30px;border-radius:7px;background:#f0fdf4;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:14px;margin-top:1px">📋</div>
            <div style="flex:1">
              <div style="font-size:9.5px;font-weight:700;color:#94a3b8;letter-spacing:.07em;text-transform:uppercase;margin-bottom:3px">Penerangan</div>
              <p style="font-size:12.5px;color:#475569;line-height:1.6;margin:0">{{ j.bengkel.description|truncatechars:400 }}</p>
            </div>
          </div>
          {% endif %}
          <hr class="dv" style="margin-bottom:14px"/>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <a href="{% url 'bengkel:tiket' token=j.token %}" class="btn" style="color:#fff;background:#059669">🎫 Tiket QR</a>
            {% if j.sudah_hadir %}
            <a href="{% url 'bengkel:submit_pernyataan' token=j.token %}" class="btn" style="color:#92400e;background:#fffbeb;border:1px solid #fde68a">✏️ Pernyataan</a>
            <a href="{% url 'bengkel:contribute' token=j.token %}" class="btn" style="color:#3730a3;background:#eef2ff;border:1px solid #c7d2fe">📎 Sumbangan & Fail</a>
            {% endif %}
          </div>
        </div>
      </div>
      {% endif %}{% endfor %}

      {% for j in jemputan_list %}{% if j.status != 'accepted' %}
      <div class="card mb-2" style="padding:13px 16px;display:flex;align-items:center;gap:12px;opacity:.6">
        <div style="width:34px;height:34px;border-radius:8px;background:#f1f5f9;display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0">📅</div>
        <div style="flex:1;min-width:0">
          <div style="font-size:13px;font-weight:600;color:#334155;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ j.bengkel.title }}</div>
          <div style="font-size:11px;color:#94a3b8;margin-top:1px">{{ j.bengkel.tarikh|date:"d M Y, H:i" }}</div>
        </div>
        {% if j.status == 'pending' %}<span class="badge" style="background:#fef3c7;color:#b45309;flex-shrink:0">Menunggu</span>
        {% else %}<span class="badge" style="background:#fee2e2;color:#b91c1c;flex-shrink:0">Ditolak</span>{% endif %}
      </div>
      {% endif %}{% endfor %}

    {% else %}
    <div class="card" style="padding:52px 24px;text-align:center">
      <div style="font-size:38px;margin-bottom:12px">📅</div>
      <div style="font-size:15px;font-weight:700;color:#334155;margin-bottom:4px">Tiada Bengkel Dijadualkan</div>
      <p style="font-size:13px;color:#94a3b8;margin:0">Tentative akan dipapar setelah jemputan diterima.</p>
    </div>
    {% endif %}
  </div>

  <!-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       PAGE: SITUATIONAL ANALYSIS
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
  <div id="page-situational" class="page">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
      <div class="sec-hd" style="margin-bottom:0">Jemputan Anda</div>
      {% if jemputan_list %}<span class="badge" style="background:#dbeafe;color:#1e40af">{{ jemputan_list|length }} rekod</span>{% endif %}
    </div>

    {% if jemputan_list %}
    <div style="display:flex;flex-direction:column;gap:10px">
      {% for j in jemputan_list %}
      <div class="card" style="display:flex;overflow:hidden;transition:box-shadow .2s" onmouseover="this.style.boxShadow='0 4px 16px rgba(0,0,0,.09)'" onmouseout="this.style.boxShadow='0 1px 3px rgba(0,0,0,.06)'">
        <div style="width:4px;flex-shrink:0;{% if j.status == 'accepted' %}background:#10b981{% elif j.status == 'rejected' %}background:#ef4444{% else %}background:#f59e0b{% endif %}"></div>
        <div style="padding:16px 18px;flex:1">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:6px">
            <div style="display:flex;gap:6px;flex-wrap:wrap">
              {% if j.status == 'accepted' %}<span class="badge" style="background:#dcfce7;color:#15803d">✓ Diterima</span>
              {% elif j.status == 'rejected' %}<span class="badge" style="background:#fee2e2;color:#b91c1c">✗ Ditolak</span>
              {% else %}<span class="badge" style="background:#fef3c7;color:#b45309">⏱ Menunggu</span>{% endif %}
              {% if j.sudah_hadir %}<span class="badge" style="background:#e0f2fe;color:#0369a1">✓ Hadir</span>{% endif %}
            </div>
            <span style="font-size:11px;color:#94a3b8;flex-shrink:0;white-space:nowrap">{{ j.bengkel.tarikh|date:"d M Y" }}</span>
          </div>
          <div style="font-size:14.5px;font-weight:700;color:#0f172a;margin-bottom:5px">{{ j.bengkel.title }}</div>
          <div style="font-size:11.5px;color:#64748b;display:flex;gap:14px;flex-wrap:wrap;margin-bottom:11px">
            <span>🕐 {{ j.bengkel.tarikh|date:"H:i" }}{% if j.bengkel.tarikh_tamat %} — {{ j.bengkel.tarikh_tamat|date:"H:i" }}{% endif %}</span>
            <span>📍 {{ j.bengkel.lokasi_nama }}</span>
          </div>
          <div style="display:flex;gap:7px;flex-wrap:wrap">
            {% if j.status == 'pending' %}
              <a href="{% url 'bengkel:response' token=j.token %}" class="btn" style="color:#fff;background:#2563eb">Buka Jemputan →</a>
            {% elif j.status == 'accepted' %}
              <a href="{% url 'bengkel:tiket' token=j.token %}" class="btn" style="color:#fff;background:#059669">🎫 Tiket QR</a>
              {% if j.sudah_hadir %}
              <a href="{% url 'bengkel:submit_pernyataan' token=j.token %}" class="btn" style="color:#92400e;background:#fffbeb;border:1px solid #fde68a">✏️ Pernyataan</a>
              <a href="{% url 'bengkel:contribute' token=j.token %}" class="btn" style="color:#3730a3;background:#eef2ff;border:1px solid #c7d2fe">📎 Sumbangan</a>
              {% endif %}
            {% endif %}
          </div>
          {% if j.pernyataan.exists %}
          <div style="margin-top:10px;padding-top:10px;border-top:1px solid #f8fafc">
            {% for ps in j.pernyataan.all %}
            <div style="font-size:11.5px;color:#475569;display:flex;align-items:center;gap:5px;margin-bottom:3px"><span style="color:#10b981;font-weight:800">✓</span> {{ ps.title }}</div>
            {% endfor %}
          </div>
          {% endif %}
        </div>
      </div>
      {% endfor %}
    </div>
    {% else %}
    <div class="card" style="padding:52px 24px;text-align:center">
      <div style="font-size:38px;margin-bottom:12px">📭</div>
      <div style="font-size:15px;font-weight:700;color:#334155;margin-bottom:4px">Tiada Jemputan Aktif</div>
      <p style="font-size:13px;color:#94a3b8;margin:0">Tunggu jemputan daripada penganjur untuk hadir ke bengkel.</p>
    </div>
    {% endif %}
  </div>

  <!-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       PAGE: TENTATIVE
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
  <div id="page-tentative" class="page">
    <div class="sec-hd">Jadual & Tentative</div>

    {% if jemputan_list %}
    <div style="display:flex;flex-direction:column;gap:8px">
      {% for j in jemputan_list %}
      <div class="card" style="overflow:hidden">
        <div style="display:flex">
          <div style="width:5px;flex-shrink:0;{% if j.status == 'accepted' %}background:#1d4ed8{% elif j.status == 'rejected' %}background:#ef4444{% else %}background:#f59e0b{% endif %}"></div>
          <div style="padding:16px 18px;flex:1">
            <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px">
              <div style="flex:1;min-width:0">
                <div style="font-size:11px;color:#94a3b8;margin-bottom:3px">{{ j.bengkel.tarikh|date:"d M Y, H:i" }}{% if j.bengkel.tarikh_tamat %} — {{ j.bengkel.tarikh_tamat|date:"H:i" }}{% endif %}</div>
                <div style="font-size:14px;font-weight:700;color:#0f172a;margin-bottom:3px">{{ j.bengkel.title }}</div>
                <div style="font-size:12px;color:#64748b">📍 {{ j.bengkel.lokasi_nama }}</div>
                {% if j.bengkel.organizer_nama %}
                <div style="font-size:11.5px;color:#94a3b8;margin-top:2px">👤 {{ j.bengkel.organizer_nama }}</div>
                {% endif %}
              </div>
              <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex-shrink:0">
                {% if j.status == 'accepted' %}<span class="badge" style="background:#dcfce7;color:#15803d">✓ Diterima</span>
                {% elif j.status == 'rejected' %}<span class="badge" style="background:#fee2e2;color:#b91c1c">Ditolak</span>
                {% else %}<span class="badge" style="background:#fef3c7;color:#b45309">Menunggu</span>{% endif %}
                {% if j.sudah_hadir %}<span class="badge" style="background:#e0f2fe;color:#0369a1">✓ Hadir</span>{% endif %}
              </div>
            </div>
            {% if j.status == 'accepted' %}
            <div style="margin-top:12px;display:flex;gap:7px;flex-wrap:wrap">
              <a href="{% url 'bengkel:tiket' token=j.token %}" class="btn" style="color:#fff;background:#059669;padding:7px 14px;font-size:12px">🎫 Tiket QR</a>
              {% if j.sudah_hadir %}
              <a href="{% url 'bengkel:contribute' token=j.token %}" class="btn" style="color:#3730a3;background:#eef2ff;border:1px solid #c7d2fe;padding:7px 14px;font-size:12px">📎 Sumbangan & Fail</a>
              {% endif %}
            </div>
            {% endif %}
          </div>
        </div>
      </div>
      {% endfor %}
    </div>
    {% else %}
    <div class="card" style="padding:52px 24px;text-align:center">
      <div style="font-size:38px;margin-bottom:12px">📋</div>
      <div style="font-size:15px;font-weight:700;color:#334155;margin-bottom:4px">Tiada Rekod</div>
      <p style="font-size:13px;color:#94a3b8;margin:0">Tentative akan dipapar setelah jemputan diterima.</p>
    </div>
    {% endif %}
  </div>

</div><!-- end content wrapper -->

<footer style="text-align:center;padding:14px 0 24px;font-size:11px;color:#cbd5e1">
  2026 Kementerian Kesihatan Malaysia — Nasional Digital Healthcare Blueprint
</footer>

<script>
  function goPage(name, btn) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    document.getElementById('page-' + name).classList.add('active');
    if (btn) btn.classList.add('active');
  }
  function tick() {
    document.querySelectorAll('[id^="cd-"]').forEach(el => {
      var raw = el.dataset.dt; if (!raw) return;
      var p = raw.split(' '), d = p[0].split('-'), t = (p[1] || '0:0:0').split(':');
      var target = new Date(d[0], d[1]-1, d[2], t[0], t[1], t[2]);
      var diff = target - new Date();
      var dv=el.querySelector('.cd-d'), hv=el.querySelector('.cd-h'), mv=el.querySelector('.cd-m'), sv=el.querySelector('.cd-s');
      if (diff <= 0) { if(dv)dv.textContent='0'; if(hv)hv.textContent='00'; if(mv)mv.textContent='00'; if(sv)sv.textContent='00'; return; }
      if(dv) dv.textContent = Math.floor(diff/86400000);
      if(hv) hv.textContent = String(Math.floor((diff%86400000)/3600000)).padStart(2,'0');
      if(mv) mv.textContent = String(Math.floor((diff%3600000)/60000)).padStart(2,'0');
      if(sv) sv.textContent = String(Math.floor((diff%60000)/1000)).padStart(2,'0');
    });
  }
  tick(); setInterval(tick, 1000);
</script>
</body>
</html>"""

with open("backend/templates/bengkel/user_dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)
print("Done", len(content), "chars")
