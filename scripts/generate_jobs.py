# -*- coding: utf-8 -*-
"""Erzeugt fuer jede offene Stelle aus YAVIS eine eigene statische Seite (SEO)
plus die Jobs-Uebersicht und die sitemap.xml.
Datenquelle: oeffentliche Supabase-Edge-Function "jobs" (gleiche Quelle wie das CRM).
Laeuft lokal (python3 scripts/generate_jobs.py) und taeglich per GitHub Action.
"""
import json, re, os, shutil, html, datetime, urllib.request

EP = "https://afbyqrwqnccgudpqxziv.supabase.co/functions/v1/jobs"
BASIS = "https://senolconsulting.de"
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_DIR = os.path.join(WURZEL, "jobs")
HEUTE = datetime.date.today().isoformat()

def esc(s): return html.escape("" if s is None else str(s), quote=True)

# Slug-Logik: MUSS identisch zum CRM (index.html jobSlug/jobAnker) bleiben!
def job_slug(x):
    s = ("" if x is None else str(x)).lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss")
    s = re.sub(r"[^a-z0-9]+","-",s)
    return s.strip("-")

def job_anker(titel, stadt):
    t, st = job_slug(titel), job_slug(stadt)
    return (t+"-"+st) if (st and st not in t) else t

def render_beschr(text):
    zeilen = str(text or "").splitlines(); out=[]; liste=False
    koepfe = {"Ihre Aufgaben","Ihr Profil","Wir bieten"}
    def zu():
        nonlocal liste
        if liste: out.append("</ul>"); liste=False
    for ln in zeilen:
        t = ln.strip()
        if not t: zu(); continue
        if t in koepfe: zu(); out.append('<div class="kopf">'+esc(t)+'</div>'); continue
        m = re.match(r"^[-•]\s+(.*)$", t)
        if m:
            if not liste: out.append("<ul>"); liste=True
            out.append("<li>"+esc(m.group(1))+"</li>"); continue
        zu(); out.append('<p>'+esc(t)+'</p>')
    zu(); return "\n".join(out)

def kurzbeschreibung(text, maxlen=155):
    t = re.sub(r"\s+"," ",str(text or "")).strip()
    return (t[:maxlen-1].rsplit(" ",1)[0]+"…") if len(t)>maxlen else t

def gehalt_jahreswert(text):
    """Freitext-Gehalt ('80.000€', '90 T € p.A.') -> Jahreswert in EUR (int) oder None."""
    t = str(text or "").strip()
    if not t: return None
    m = re.search(r"(\d[\d.,]*)", t)
    if not m: return None
    zahl = m.group(1).replace(".", "").replace(",", ".")
    try: wert = float(zahl)
    except ValueError: return None
    if re.search(r"\d\s*[tT]\b|\bT\s*€", t) or wert < 1000:  # '90 T €' = Tausender
        wert *= 1000
    wert = int(round(wert))
    return wert if 20000 <= wert <= 400000 else None  # Plausibilitätsfenster

STIL = """
:root{--ink:#191817;--ink-soft:#26241f;--paper:#f6f5f2;--coral:#ef9873;--coral-deep:#d97247;--muted:#6e6a63;--line:#e2dfd8}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font-family:"Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;font-size:16.5px;line-height:1.65;-webkit-font-smoothing:antialiased}
::selection{background:var(--coral);color:var(--ink)}
a{color:inherit;text-decoration:none}
header{position:sticky;top:0;z-index:50;background:rgba(246,245,242,.92);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.nav{max-width:920px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;padding:16px 28px}
.brand{font-family:"Segoe UI Black","Segoe UI",Arial,sans-serif;font-weight:900;font-size:24px;letter-spacing:-.02em}
.brand em{font-style:normal;color:var(--coral);font-size:28px;line-height:0}
.nav a.back{font-size:14px;font-weight:600;color:var(--muted)}
.nav a.back:hover{color:var(--ink)}
main{max-width:920px;margin:0 auto;padding:64px 28px 110px}
.mono{font-family:Consolas,"Cascadia Mono","Courier New",monospace;font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--coral-deep)}
h1{font-family:"Segoe UI Black","Segoe UI",Arial,sans-serif;font-weight:900;font-size:clamp(30px,4.8vw,48px);letter-spacing:-.025em;line-height:1.08;margin:14px 0 10px;text-wrap:balance}
h1 .dot{display:inline-block;width:.3em;height:.3em;border-radius:50%;background:var(--coral)}
.meta{font-size:14px;color:var(--muted);margin-bottom:36px}
.beschr{max-width:46em}
.beschr p{margin:0 0 12px;color:#3c3a35;font-size:15.5px}
.beschr ul{margin:0 0 10px;padding-left:22px}
.beschr li{margin:4px 0;color:#3c3a35;font-size:15.5px}
.beschr .kopf{font-weight:700;color:var(--ink);margin:22px 0 8px;font-size:16.5px}
.cta{margin-top:34px;display:flex;gap:10px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;padding:12px 22px;border-radius:3px;font-weight:700;font-size:14.5px;border:1px solid transparent;cursor:pointer;font-family:inherit}
.btn-coral{background:var(--coral);color:var(--ink)}
.btn-coral:hover{background:#f4a988}
.btn-line{background:none;border-color:var(--line);color:var(--muted)}
.btn-line:hover{border-color:var(--ink);color:var(--ink)}
.abschluss{margin-top:52px;padding:30px 32px;background:var(--ink);color:var(--paper);border-radius:6px;display:flex;justify-content:space-between;align-items:center;gap:24px;flex-wrap:wrap}
.abschluss b{font-size:17px;display:block;margin-bottom:4px}
.abschluss span{color:#9a958c;font-size:14px}
.abschluss a{background:var(--coral);color:var(--ink);padding:11px 22px;border-radius:3px;font-weight:700;font-size:14px}
footer{border-top:1px solid var(--line);padding:22px 28px;font-size:13px;color:var(--muted)}
footer .in{max-width:920px;margin:0 auto;display:flex;gap:24px;flex-wrap:wrap;justify-content:space-between}
footer a:hover{color:var(--ink)}
.jl-card{display:block;border:1px solid var(--line);border-radius:6px;margin:0 0 12px;background:#fcfbf9;padding:20px 24px;transition:border-color .18s}
.jl-card:hover{border-color:#c9c4ba}
.jl-titel{font-size:17.5px;font-weight:700;letter-spacing:-.01em}
.jl-titel::after{content:" →";color:var(--coral-deep)}
.jl-meta{font-size:13px;color:var(--muted);margin-top:5px}
#zaehler{font-family:Consolas,"Cascadia Mono",monospace;font-size:12px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin:34px 0 16px}
a:focus-visible,button:focus-visible{outline:2px solid var(--coral);outline-offset:3px}
"""

FUSS = ('<footer><div class="in"><span>© 2026 YSC Senol Consulting · Personalberatung für TGA &amp; Bau</span>'
        '<span><a href="/impressum.html">Impressum</a> · <a href="/datenschutz.html">Datenschutz</a></span></div></footer>')

def seite(titel, beschreibung, kanonisch, kopf_extra, body):
    return f'''<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(titel)}</title>
<meta name="description" content="{esc(beschreibung)}">
<link rel="canonical" href="{kanonisch}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ccircle cx='50' cy='50' r='42' fill='%23ef9873'/%3E%3C/svg%3E">
<meta property="og:type" content="website">
<meta property="og:site_name" content="YSC Senol Consulting">
<meta property="og:title" content="{esc(titel)}">
<meta property="og:description" content="{esc(beschreibung)}">
<meta property="og:url" content="{kanonisch}">
<meta property="og:locale" content="de_DE">
<meta property="og:image" content="{BASIS}/og-banner.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="YSC Senol Consulting — Personalberatung für TGA &amp; Bau">
<meta name="twitter:card" content="summary_large_image">
<style>{STIL}</style>
{kopf_extra}
</head>
<body>
{body}
</body>
</html>'''

def lade_jobs():
    with urllib.request.urlopen(EP, timeout=30) as r:
        return (json.load(r) or {}).get("jobs") or []

def haupt():
    jobs = lade_jobs()
    # Eindeutige Anker (bei Kollision -2, -3 …)
    belegt = {}
    for j in jobs:
        a = job_anker(j.get("jobtitel"), j.get("stadt")) or "stelle"
        n = belegt.get(a, 0) + 1
        belegt[a] = n
        j["_anker"] = a if n == 1 else f"{a}-{n}"

    # Alte generierte Einzelseiten entfernen (Ordner unter jobs/)
    if os.path.isdir(JOBS_DIR):
        for name in os.listdir(JOBS_DIR):
            p = os.path.join(JOBS_DIR, name)
            if os.path.isdir(p): shutil.rmtree(p)
    os.makedirs(JOBS_DIR, exist_ok=True)

    # ---------- Einzelseiten ----------
    for j in jobs:
        anker = j["_anker"]
        url = f"{BASIS}/jobs/{anker}/"
        ort = ", ".join(x for x in [j.get("stadt"), j.get("bundesland")] if x)
        ist_remote = str(j.get("remote"))=="true"
        gehalt_wert = gehalt_jahreswert(j.get("gehalt"))
        gehalt_anzeige = f"bis {gehalt_wert:,.0f} € p. a.".replace(",", ".") if gehalt_wert else None
        meta = "  ·  ".join(x for x in [ort, j.get("stellentyp"),
                 ("Remote möglich" if ist_remote else None), j.get("berufserfahrung"), gehalt_anzeige] if x)
        st = str(j.get("stellentyp") or "").lower()
        emptype = "FULL_TIME" if ("voll" in st or "festanstellung" in st) else ("PART_TIME" if "teil" in st else None)
        # Gültigkeit: Seiten werden täglich neu generiert -> rollierend 60 Tage ab heute
        gueltig_bis = (datetime.date.today() + datetime.timedelta(days=60)).isoformat()
        ld = {"@context":"https://schema.org","@type":"JobPosting",
              "title": j.get("jobtitel") or "",
              "description": str(j.get("beschreibung") or "").replace("\r\n","\n").replace("\n","<br>"),
              "datePosted": j.get("oeffnungsdatum") or None,
              "validThrough": gueltig_bis,
              "employmentType": emptype,
              "directApply": True,
              "hiringOrganization": {"@type":"Organization","name":"YSC Senol Consulting (Personalberatung, Besetzung im Kundenauftrag)","sameAs":BASIS},
              "jobLocation": {"@type":"Place","address":{"@type":"PostalAddress",
                    "addressLocality": j.get("stadt") or None, "addressRegion": j.get("bundesland") or None,
                    "postalCode": j.get("plz") or None, "addressCountry":"DE"}},
              "url": url}
        if gehalt_wert:
            ld["baseSalary"] = {"@type":"MonetaryAmount","currency":"EUR",
                "value":{"@type":"QuantitativeValue","value":gehalt_wert,"unitText":"YEAR"}}
        if ist_remote:
            ld["jobLocationType"] = "TELECOMMUTE"
            ld["applicantLocationRequirements"] = {"@type":"Country","name":"Deutschland"}
        ld = json.loads(json.dumps(ld))  # None-Werte bleiben; Google ignoriert null nicht -> entfernen:
        def putz(o):
            if isinstance(o, dict): return {k: putz(v) for k, v in o.items() if v is not None}
            return o
        ld = putz(ld)
        mail = "mailto:info@senolconsulting.de?subject=" + urllib.request.quote("Bewerbung: " + (j.get("jobtitel") or ""))
        body = f'''<header><nav class="nav"><a class="brand" href="/"><img src="/logo.svg" alt="YSC Senol Consulting" style="height:30px;display:block"></a><a class="back" href="/jobs/">← Alle Positionen</a></nav></header>
<main>
  <p class="mono">{esc(meta) if meta else "Offene Position"}</p>
  <h1>{esc(j.get("jobtitel"))}<span class="dot"></span></h1>
  <p class="meta">Betreut durch YSC Senol Consulting · Festanstellung direkt beim Auftraggeber · 100&nbsp;% vertraulich</p>
  <div class="beschr">{render_beschr(j.get("beschreibung"))}</div>
  <div class="cta">
    <a class="btn btn-coral" href="{mail}">Auf diese Position bewerben</a>
    <button type="button" class="btn btn-line" onclick="navigator.clipboard&&navigator.clipboard.writeText(location.href).then(()=>{{this.textContent='✓ Link kopiert'}})">🔗 Link kopieren</button>
  </div>
  <div class="abschluss">
    <div><b>Passt nicht ganz?</b><span>Viele Mandate sind nie öffentlich; ein vertrauliches Gespräch zeigt, was gerade möglich ist.</span></div>
    <a href="mailto:info@senolconsulting.de?subject=Vertrauliches%20Karrieregespr%C3%A4ch">Karrieregespräch anfragen</a>
  </div>
</main>
{FUSS}'''
        kopf_extra = '<script type="application/ld+json">'+json.dumps(ld, ensure_ascii=False)+'</script>'
        os.makedirs(os.path.join(JOBS_DIR, anker), exist_ok=True)
        with open(os.path.join(JOBS_DIR, anker, "index.html"), "w", encoding="utf-8") as f:
            f.write(seite(f'{j.get("jobtitel")} · {ort or "TGA & Bau"} | YSC Senol Consulting',
                          kurzbeschreibung(j.get("beschreibung")) or "Offene Position in TGA & Bau bei YSC Senol Consulting.",
                          url, kopf_extra, body))

    # ---------- Übersicht ----------
    karten = "\n".join(
        f'<a class="jl-card" id="job-{esc(j["_anker"])}" href="{esc(j["_anker"])}/">'
        f'<div class="jl-titel">{esc(j.get("jobtitel"))}</div>'
        + (f'<div class="jl-meta">{esc("  ·  ".join(x for x in [", ".join(y for y in [j.get("stadt"), j.get("bundesland")] if y), j.get("stellentyp"), ("Remote möglich" if str(j.get("remote"))=="true" else None)] if x))}</div>' )
        + '</a>'
        for j in jobs)
    legacy = '''<script>
// Alte Newsletter-Links (/jobs#job-<kuerzel>) auf die neue Einzelseite weiterleiten
(function(){ var h=location.hash?decodeURIComponent(location.hash.slice(1)):""; if(h.indexOf("job-")===0){ location.replace(h.slice(4)+"/"); } })();
</script>'''
    body = f'''<header><nav class="nav"><a class="brand" href="/"><img src="/logo.svg" alt="YSC Senol Consulting" style="height:30px;display:block"></a><a class="back" href="/">← Zur Startseite</a></nav></header>
<main>
  <p class="mono">Jobbörse · TGA &amp; Bau</p>
  <h1>Aktuelle Positionen<span class="dot"></span></h1>
  <p class="meta" style="margin-bottom:8px">Projektleitung, Bauleitung, Fachplanung, Führungspositionen, laufend aktualisiert. Vieles besetzen wir verdeckt: Wenn nichts Passendes dabei ist, lohnt sich ein vertrauliches Gespräch trotzdem.</p>
  <div id="zaehler">{len(jobs)} offene Stellen · Stand {datetime.date.today().strftime("%d.%m.%Y")}</div>
  {karten}
  <div class="abschluss">
    <div><b>Nichts Passendes dabei?</b><span>Viele Mandate sind nie öffentlich. Ein kurzes Gespräch zeigt, was gerade möglich ist, diskret und unverbindlich.</span></div>
    <a href="mailto:info@senolconsulting.de?subject=Vertrauliches%20Karrieregespr%C3%A4ch">Karrieregespräch anfragen</a>
  </div>
</main>
{FUSS}
{legacy}'''
    with open(os.path.join(JOBS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(seite("Aktuelle Positionen in TGA & Bau · YSC Senol Consulting",
                      "Offene Stellen in TGA und Bau: Projektleitung, Bauleitung, Fachplanung, Führungspositionen. Betreut von YSC Senol Consulting, Köln.",
                      f"{BASIS}/jobs/", "", body))

    # ---------- Sitemap ----------
    eintraege = [f'  <url><loc>{BASIS}/</loc><lastmod>{HEUTE}</lastmod><changefreq>monthly</changefreq><priority>1.0</priority></url>',
                 f'  <url><loc>{BASIS}/jobs/</loc><lastmod>{HEUTE}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>']
    eintraege += [f'  <url><loc>{BASIS}/jobs/{j["_anker"]}/</loc><lastmod>{HEUTE}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>' for j in jobs]
    with open(os.path.join(WURZEL, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + "\n".join(eintraege) + "\n</urlset>\n")

    print(f"{len(jobs)} Einzelseiten + Übersicht + Sitemap generiert")

if __name__ == "__main__":
    haupt()
