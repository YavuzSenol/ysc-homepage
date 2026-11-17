#!/usr/bin/env python3
"""Erzeugt aus news/*.json die Branchennews-Seiten unter /wissen/<slug>/ und traegt die Karten
in die Fachwissen-Uebersicht (/wissen/index.html) zwischen den Markierungen NEWS-START und NEWS-ENDE ein.

Laeuft NUR von Hand (nach Freigabe durch Yavuz), nicht in der taeglichen Action.
Die Sitemap erledigt scripts/generate_jobs.py: Es nimmt jede Seite wissen/<name>/index.html automatisch auf.

Aufbau einer Datei news/<slug>.json:
  slug, datum (JJJJ-MM-TT), titel, teaser, absaetze (Liste), einordnung (Liste),
  quellen (Liste aus {name, titel, url, datum})
"""
import glob, html, json, os, re

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASIS = "https://senolconsulting.de"
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]


# Fachseiten, auf die Beitraege verweisen koennen (Feld "verwandt" in news/*.json). Schluessel = Ordnername im Wurzelverzeichnis.
FACHSEITEN = {
    "tga-personalberatung-koeln": "TGA Personalberatung Köln",
    "tga-headhunter-koeln": "TGA Headhunter Köln",
    "tga-headhunter-hls": "Headhunter HLS: Heizung, Lüftung, Sanitär",
    "tga-headhunter-elektrotechnik": "Headhunter Elektrotechnik",
    "tga-headhunter-kaelte-klima": "Headhunter Kälte und Klima",
    "tga-headhunter-gebaeudeautomation": "Headhunter Gebäudeautomation",
    "tga-headhunter-brandschutz": "Headhunter Brandschutz",
}


def deutsch(iso):
    j, m, t = iso.split("-")
    return f"{int(t)}. {MONATE[int(m) - 1]} {j}"


def e(s):
    return html.escape(s, quote=True)


CSS = """:root{--ink:#191817;--ink-soft:#26241f;--paper:#f6f5f2;--coral:#ef9873;--coral-deep:#d97247;--muted:#6e6a63;--line:#e2dfd8}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font-family:"Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;font-size:16.5px;line-height:1.65;-webkit-font-smoothing:antialiased}
::selection{background:var(--coral);color:var(--ink)}
a{color:inherit;text-decoration:none}
header{position:sticky;top:0;z-index:50;background:rgba(246,245,242,.92);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.nav{max-width:820px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;padding:16px 28px}
.brand{font-family:"Segoe UI Black","Segoe UI",Arial,sans-serif;font-weight:900;font-size:24px;letter-spacing:-.02em}
.nav a.back{font-size:14px;font-weight:600;color:var(--muted)}
.nav a.back:hover{color:var(--ink)}
main{max-width:820px;margin:0 auto;padding:60px 28px 100px}
.mono{font-family:Consolas,"Cascadia Mono","Courier New",monospace;font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--coral-deep)}
h1{font-family:"Segoe UI Black","Segoe UI",Arial,sans-serif;font-weight:900;font-size:clamp(30px,4.8vw,50px);letter-spacing:-.025em;line-height:1.07;margin:14px 0 12px;text-wrap:balance}
h1 .dot{display:inline-block;width:.3em;height:.3em;border-radius:50%;background:var(--coral)}
.lead{font-size:20px;line-height:1.55;color:var(--ink-soft);max-width:34em;margin:18px 0 38px}
article{max-width:40em}
article p{margin:0 0 16px;color:#33312c;font-size:16.5px}
article h2{font-family:"Segoe UI Black","Segoe UI",Arial,sans-serif;font-weight:900;font-size:24px;letter-spacing:-.015em;margin:44px 0 14px}
article strong{color:var(--ink)}
.quellen{margin-top:48px;padding-top:22px;border-top:1px solid var(--line);font-size:13.5px;color:var(--muted)}
.quellen h2{font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:10px;font-family:inherit;font-weight:700}
.quellen a{color:var(--coral-deep);text-decoration:underline;text-underline-offset:2px}
.quellen p{margin:5px 0;font-size:13.5px}
.abschluss{margin-top:52px;padding:30px 32px;background:var(--ink);color:var(--paper);border-radius:6px;display:flex;justify-content:space-between;align-items:center;gap:24px;flex-wrap:wrap}
.abschluss b{font-size:17px;display:block;margin-bottom:4px}
.abschluss span{color:#9a958c;font-size:14px}
.abschluss a{background:var(--coral);color:var(--ink);padding:11px 22px;border-radius:3px;font-weight:700;font-size:14px;white-space:nowrap}
footer{border-top:1px solid var(--line);padding:22px 28px;font-size:13px;color:var(--muted)}
footer .in{max-width:820px;margin:0 auto;display:flex;gap:24px;flex-wrap:wrap;justify-content:space-between}
footer a:hover{color:var(--ink)}
a:focus-visible{outline:2px solid var(--coral);outline-offset:3px}"""


def seite(n):
    url = f"{BASIS}/wissen/{n['slug']}/"
    titel_vollstaendig = f"{n['titel']} | YSC Senol Consulting"
    ld = json.dumps({
        "@context": "https://schema.org", "@type": "Article", "headline": n["titel"], "description": n["teaser"],
        "datePublished": n["datum"], "inLanguage": "de-DE",
        "author": {"@type": "Organization", "name": "YSC Senol Consulting"},
        "publisher": {"@type": "Organization", "name": "YSC Senol Consulting", "url": BASIS},
        "mainEntityOfPage": url}, ensure_ascii=False)
    absaetze = "\n".join(f"    <p>{e(p)}</p>" for p in n["absaetze"])
    einordnung = "\n".join(f"    <p>{e(p)}</p>" for p in n["einordnung"])
    verwandt = ""
    if n.get("verwandt"):
        links = " · ".join(f'<a href="/{s}/" style="color:var(--coral-deep);text-decoration:underline;text-underline-offset:2px">{e(FACHSEITEN[s])}</a>' for s in n["verwandt"])
        verwandt = f'\n    <p style="margin-top:28px;font-size:15px"><b>Passend dazu:</b> {links}</p>\n'
    quellen = "\n".join(
        f'      <p>{e(q["name"])}: <a href="{e(q["url"])}" rel="noopener">{e(q["titel"])}</a> ({deutsch(q["datum"])})</p>' for q in n["quellen"])
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titel_vollstaendig)}</title>
<meta name="description" content="{e(n['teaser'])}">
<link rel="canonical" href="{url}">
<link rel="icon" type="image/svg+xml" href="/favicon.svg"><link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta property="og:type" content="article">
<meta property="og:site_name" content="YSC Senol Consulting">
<meta property="og:title" content="{e(n['titel'])}">
<meta property="og:description" content="{e(n['teaser'])}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="de_DE">
<meta property="og:image" content="{BASIS}/og-banner.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="YSC Senol Consulting — Personalberatung für TGA &amp; Bau">
<meta name="twitter:card" content="summary_large_image">
<style>
{CSS}
</style>
<script type="application/ld+json">{ld}</script>
</head>
<body>
<header><nav class="nav"><a class="brand" href="/"><img src="/logo.svg" alt="YSC Senol Consulting" style="height:30px;display:block"></a><a class="back" href="/wissen/">← Fachwissen</a></nav></header>
<main>
  <p class="mono">Fachwissen · Branchennews · {deutsch(n['datum'])}</p>
  <h1>{e(n['titel'])}<span class="dot"></span></h1>
  <p class="lead">{e(n['teaser'])}</p>

  <article>
{absaetze}

    <h2>Unsere Einordnung</h2>
{einordnung}
{verwandt}
    <div class="quellen">
      <h2>Quellen</h2>
{quellen}
    </div>
  </article>

  <div class="abschluss">
    <div><b>Was bedeutet das für Ihre Laufbahn?</b><span>Ein vertrauliches Gespräch zeigt, wo Ihr Profil im aktuellen Markt steht, ganz ohne Verpflichtung.</span></div>
    <a href="mailto:info@senolconsulting.de?subject=Vertrauliches%20Karrieregespr%C3%A4ch">Karrieregespräch anfragen</a>
  </div>
</main>
<footer><div class="in"><span>© 2026 YSC Senol Consulting · Personalberatung für TGA &amp; Bau</span><span><a href="/impressum.html">Impressum</a> · <a href="/datenschutz.html">Datenschutz</a></span></div></footer>
</body>
</html>
"""


def karte(n):
    return (f'  <a class="art-card" href="/wissen/{n["slug"]}/">\n'
            f'    <span class="k">Branchennews · {deutsch(n["datum"])}</span>\n'
            f'    <h2>{e(n["titel"])}</h2>\n'
            f'    <p>{e(n["teaser"])}</p>\n'
            f'  </a>')


def main():
    eintraege = []
    for pfad in sorted(glob.glob(os.path.join(WURZEL, "news", "*.json"))):
        n = json.load(open(pfad, encoding="utf-8"))
        # Stilregel: keine Gedankenstriche, nicht das Wort "vermitteln"
        text = json.dumps(n, ensure_ascii=False)
        if re.search(r"[–—]|vermittel", text, re.I):
            raise SystemExit(f"{pfad}: Gedankenstrich oder 'vermitteln' gefunden, bitte bereinigen")
        eintraege.append(n)
        ordner = os.path.join(WURZEL, "wissen", n["slug"])
        os.makedirs(ordner, exist_ok=True)
        with open(os.path.join(ordner, "index.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(seite(n))
        print("Seite:", n["slug"])
    eintraege.sort(key=lambda x: x["datum"], reverse=True)
    hub = os.path.join(WURZEL, "wissen", "index.html")
    h = open(hub, encoding="utf-8").read()
    block = "<!--NEWS-START-->\n" + "\n\n".join(karte(n) for n in eintraege) + "\n  <!--NEWS-ENDE-->"
    if "<!--NEWS-START-->" in h:
        h = re.sub(r"<!--NEWS-START-->.*?<!--NEWS-ENDE-->", lambda m: block, h, flags=re.S)
    else:
        marke = '  <a class="art-card" href="/wissen/tga-markt-2026-wer-kauft-wen/">'
        if marke not in h:
            raise SystemExit("Einfuegestelle in wissen/index.html nicht gefunden")
        h = h.replace(marke, "  " + block + "\n\n" + marke, 1)
    with open(hub, "w", encoding="utf-8", newline="\n") as f:
        f.write(h)
    print("Uebersicht aktualisiert:", len(eintraege), "Karten")
    fachseiten_aktualisieren(eintraege)


def fachseiten_aktualisieren(eintraege):
    """Auf jeder Fachseite einen Block 'Aktuell aus der Branche' mit den bis zu drei neuesten Beitraegen, die auf sie verweisen."""
    for s in FACHSEITEN:
        pfad = os.path.join(WURZEL, s, "index.html")
        if not os.path.isfile(pfad):
            continue
        passend = [n for n in eintraege if s in n.get("verwandt", [])][:3]
        h = open(pfad, encoding="utf-8").read()
        if passend:
            zeilen = "\n".join(f'      <li style="margin:6px 0"><a href="/wissen/{n["slug"]}/" style="color:var(--coral-deep);text-decoration:underline;text-underline-offset:2px">{e(n["titel"])}</a> <span style="color:var(--muted);font-size:13px">({deutsch(n["datum"])})</span></li>' for n in passend)
            block = ('<!--NEWS-LINKS-START-->\n'
                     '  <section style="max-width:40em;margin:40px 0 0;padding-top:22px;border-top:1px solid var(--line)">\n'
                     '    <p class="mono">Aktuell aus der Branche</p>\n'
                     f'    <ul style="list-style:none;padding:0;margin:10px 0 0">\n{zeilen}\n    </ul>\n'
                     '    <p style="margin-top:10px;font-size:14px"><a href="/wissen/" style="color:var(--muted)">Alle Beiträge im Fachwissen →</a></p>\n'
                     '  </section>\n  <!--NEWS-LINKS-ENDE-->')
        else:
            block = ""
        if "<!--NEWS-LINKS-START-->" in h:
            neu = re.sub(r"<!--NEWS-LINKS-START-->.*?<!--NEWS-LINKS-ENDE-->", lambda m: block, h, flags=re.S)
        elif block:
            marke = '  <div class="abschluss">'
            if marke not in h:
                print("Einfuegestelle fehlt in", s)
                continue
            neu = h.replace(marke, "  " + block + "\n\n" + marke, 1)
        else:
            continue
        if neu != h:
            with open(pfad, "w", encoding="utf-8", newline="\n") as f:
                f.write(neu)
            print("Fachseite aktualisiert:", s, len(passend), "Beitraege")


if __name__ == "__main__":
    main()
