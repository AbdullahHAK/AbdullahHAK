"""Generates the SVG artwork used by the profile README.

GitHub renders README images in a sandbox that blocks web fonts, so every
piece of text is converted to vector outlines here. Each asset is written
twice, once per GitHub theme: assets/<name>-dark.svg and assets/<name>-light.svg.

The activity card pulls live numbers (GitHub contributions, WakaTime hours);
.github/workflows/activity.yml re-runs this script daily to keep it current.
If those sources can't be reached, the existing activity card is left as is.

    pip install -r design/requirements.txt
    python design/build.py
"""

import re
import urllib.request
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "design" / "fonts"
OUT = ROOT / "assets"

W = 1000  # every asset shares this width so they line up in the README

THEMES = {
    "dark": dict(
        bg="#0F0B15", surface="#16101E", tile="#1E1729", ink="#F3EEF8",
        muted="#A99EC0", faint="#6E6383", border="#2A2235", accent="#A47FE0",
        accent_ink="#0F0B15", glow="#7C4FD8", glow_op="0.30",
        heat=["#1E1729", "#3B2A5C", "#5A3F8F", "#7C4FD8", "#A47FE0"],
    ),
    "light": dict(
        bg="#FBF9FC", surface="#F7F3FB", tile="#EFE8F7", ink="#1B1625",
        muted="#6B6275", faint="#A39BB0", border="#E6E0ED", accent="#8C5FC4",
        accent_ink="#FFFFFF", glow="#C9AEE8", glow_op="0.45",
        heat=["#EFE8F7", "#DCCBF0", "#C0A2E6", "#A07BD6", "#7C4FD8"],
    ),
}

GITHUB_USER = "AbdullahHAK"
WAKATIME_BADGE = "https://wakatime.com/badge/user/ef6eb41e-c5f0-4384-a364-29faef911fe6.svg"


def fmt(v):
    return ("%.1f" % v).rstrip("0").rstrip(".")


def fmt3(v):
    return ("%.4f" % v).rstrip("0").rstrip(".")


DEFS = {}  # glyph outlines used by the file currently being built, keyed by id


class Font:
    def __init__(self, filename, key):
        self.key = key
        woff = TTFont(FONTS / filename)
        woff.flavor = None
        buf = BytesIO()
        woff.save(buf)
        data = buf.getvalue()
        self.tt = TTFont(BytesIO(data))
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.upem = self.tt["head"].unitsPerEm
        self.hb = hb.Font(hb.Face(data))

    def _shape(self, text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": True})
        return [(self.order[i.codepoint], p.x_advance, p.x_offset, p.y_offset)
                for i, p in zip(buf.glyph_infos, buf.glyph_positions)]

    def width(self, text, size, tracking=0):
        run = self._shape(text)
        return sum(a for _, a, _, _ in run) * size / self.upem + tracking * max(len(run) - 1, 0)

    def glyph_paths(self, text, size, x, y, tracking=0, anchor="start"):
        if anchor != "start":
            w = self.width(text, size, tracking)
            x -= w if anchor == "end" else w / 2
        s = size / self.upem
        paths = []
        for name, adv, dx, dy in self._shape(text):
            pen = SVGPathPen(self.glyphs, ntos=fmt)
            self.glyphs[name].draw(TransformPen(pen, (s, 0, 0, -s, x + dx * s, y - dy * s)))
            d = pen.getCommands()
            if d:
                paths.append(d)
            x += adv * s + tracking
        return paths

    def text(self, text, size, x, y, fill, tracking=0, anchor="start"):
        """Text as <use> references to glyphs defined once per file (see DEFS)."""
        if anchor != "start":
            w = self.width(text, size, tracking)
            x -= w if anchor == "end" else w / 2
        # positions are in font units inside one scaled, y-flipped group per run
        s = size / self.upem
        pen_x, uses = 0.0, []
        for name, adv, dx, dy in self._shape(text):
            gid = self._define(name)
            if gid:
                pos = f' x="{round(pen_x + dx)}"' if round(pen_x + dx) else ""
                pos += f' y="{-dy}"' if dy else ""
                uses.append(f'<use href="#{gid}"{pos}/>')
            pen_x += adv + tracking / s
        return (f'<g fill="{fill}" transform="matrix({fmt3(s)} 0 0 {fmt3(-s)} {fmt(x)} {fmt(y)})">'
                f'{"".join(uses)}</g>')

    def _define(self, name):
        gid = f"{self.key}-{self.order.index(name)}"
        if gid not in DEFS:
            pen = SVGPathPen(self.glyphs, ntos=lambda v: str(round(v)))
            self.glyphs[name].draw(pen)
            d = pen.getCommands()
            DEFS[gid] = f'<path id="{gid}" d="{d}"/>' if d else ""
        return gid if DEFS[gid] else None


SERIF = Font("fraunces-latin-500-normal.woff2", "s")
SERIF_REG = Font("fraunces-latin-400-normal.woff2", "r")
ITALIC = Font("fraunces-latin-400-italic.woff2", "i")
SANS = Font("inter-latin-400-normal.woff2", "a")
SANS_MED = Font("inter-latin-500-normal.woff2", "m")
SANS_BOLD = Font("inter-latin-600-normal.woff2", "b")


def label(text, x, y, fill, anchor="start", size=12.5):
    """Small uppercase eyebrow text."""
    return SANS_BOLD.text(text.upper(), size, x, y, fill, tracking=2.2, anchor=anchor)


def arrow_ne(x, y, size, color, width=1.6):
    """A north-east arrow; (x, y) is its bottom-left point."""
    return (f'<path d="M{fmt(x)} {fmt(y)}L{fmt(x + size)} {fmt(y - size)}'
            f'M{fmt(x + size * 0.3)} {fmt(y - size)}H{fmt(x + size)}V{fmt(y - size * 0.7)}" '
            f'fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')


def arrow_right(x, y, length, color, width=1.6):
    return (f'<path d="M{fmt(x)} {fmt(y)}H{fmt(x + length)}M{fmt(x + length - 5)} {fmt(y - 5)}'
            f'L{fmt(x + length)} {fmt(y)}L{fmt(x + length - 5)} {fmt(y + 5)}" fill="none" '
            f'stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')


def check(cx, cy, size, color, width=2):
    return (f'<path d="M{fmt(cx - size * 0.5)} {fmt(cy)}L{fmt(cx - size * 0.15)} {fmt(cy + size * 0.35)}'
            f'L{fmt(cx + size * 0.5)} {fmt(cy - size * 0.35)}" fill="none" stroke="{color}" '
            f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')


def chip(text, x, y, t, font=None, size=13.5):
    """A pill with text; returns (svg, width). y is the pill's top edge."""
    font = font or SANS_MED
    w = font.width(text, size) + 26
    svg = (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="30" rx="15" '
           f'fill="{t["tile"]}" stroke="{t["border"]}"/>'
           + font.text(text, size, x + 13, y + 19.6, t["muted"]))
    return svg, w


def chips(items, x, y, t, max_x, gap=8, row_gap=10):
    out, cx, cy = [], x, y
    for item in items:
        w = SANS_MED.width(item, 13.5) + 26
        if cx + w > max_x:
            cx, cy = x, cy + 30 + row_gap
        svg, w = chip(item, cx, cy, t)
        out.append(svg)
        cx += w + gap
    return "".join(out)


def defs():
    """Emits the glyphs collected so far and starts a fresh set for the next file."""
    out = "<defs>" + "".join(DEFS.values()) + "</defs>"
    DEFS.clear()
    return out


REDUCED_MOTION = ("@media (prefers-reduced-motion: reduce){*{animation:none!important}}")


def svg(height, body, t, css="", card=True, title=""):
    frame = ""
    if card:
        frame = (f'<rect x="0.5" y="0.5" width="{W - 1}" height="{height - 1}" rx="22" '
                 f'fill="{t["bg"]}" stroke="{t["border"]}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" '
            f'viewBox="0 0 {W} {height}" role="img" aria-label="{title}">'
            f'<title>{title}</title>'
            f'<style>{css}{REDUCED_MOTION}</style>{defs()}{frame}{body}</svg>')


def glow(t, cx, cy, r, gid, cls="glow"):
    return (f'<defs><radialGradient id="{gid}"><stop offset="0" stop-color="{t["glow"]}" '
            f'stop-opacity="{t["glow_op"]}"/><stop offset="1" stop-color="{t["glow"]}" stop-opacity="0"/>'
            f'</radialGradient></defs><circle class="{cls}" cx="{cx}" cy="{cy}" r="{r}" fill="url(#{gid})"/>')


# ---------------------------------------------------------------- header

def header(t):
    h = 470
    css = (
        ".glow{animation:drift 14s ease-in-out infinite alternate}"
        "@keyframes drift{from{transform:translate(0,0)}to{transform:translate(-90px,40px)}}"
        ".g{stroke:" + t["accent"] + ";stroke-width:1.4;stroke-dasharray:1;stroke-dashoffset:0;"
        "fill-opacity:1;stroke-opacity:0;animation:draw 2.4s cubic-bezier(.65,0,.35,1) both,"
        "fillin 1s ease-out both}"
        "@keyframes draw{0%{stroke-dashoffset:1;stroke-opacity:1}80%{stroke-dashoffset:0;stroke-opacity:1}"
        "100%{stroke-dashoffset:0;stroke-opacity:0}}"
        "@keyframes fillin{from{fill-opacity:0}to{fill-opacity:1}}"
        ".up{animation:up 1.1s cubic-bezier(.16,1,.3,1) both}"
        "@keyframes up{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}"
        ".pulse{transform-origin:center;transform-box:fill-box;animation:pulse 2.4s ease-out infinite}"
        "@keyframes pulse{0%{transform:scale(1);opacity:.6}100%{transform:scale(3.2);opacity:0}}"
    )
    b = [glow(t, 820, 120, 420, "hg")]

    # orbit motif, top right
    b.append(f'<g stroke-opacity=".55"><ellipse cx="850" cy="196" rx="104" ry="40" fill="none" '
             f'stroke="{t["faint"]}"/>'
             f'<circle cx="850" cy="196" r="70" fill="none" stroke="{t["faint"]}" stroke-dasharray="2 6"/>'
             f'<circle r="4" fill="{t["accent"]}"><animateMotion dur="16s" repeatCount="indefinite" '
             f'path="M746 196a104 40 0 1 0 208 0a104 40 0 1 0 -208 0"/></circle>'
             f'<circle cx="850" cy="196" r="3" fill="{t["ink"]}"/></g>')

    # top row
    b.append(f'<circle cx="62" cy="58" r="4" fill="{t["accent"]}"/>'
             f'<circle class="pulse" cx="62" cy="58" r="4" fill="{t["accent"]}"/>')
    b.append(label("Open to projects & roles", 78, 62.5, t["muted"]))
    b.append(label("Pakistan  ·  UTC+5  ·  Remote", W - 56, 62.5, t["muted"], anchor="end"))

    # name, drawn stroke by stroke
    for i, d in enumerate(SERIF.glyph_paths("Abdullah", 150, 52, 238, tracking=-3)):
        b.append(f'<path class="g" pathLength="1" style="animation-delay:{i * 0.12:.2f}s,{1.5 + i * 0.12:.2f}s" '
                 f'fill="{t["ink"]}" d="{d}"/>')

    b.append(f'<g class="up" style="animation-delay:1.2s">'
             + ITALIC.text("Software Engineer", 40, 58, 296, t["accent"]) + "</g>")
    b.append(f'<g class="up" style="animation-delay:1.45s">'
             + SANS.text("I take products from an empty repo to paying customers,", 21, 58, 346, t["muted"])
             + SANS.text("and I keep them running long after launch.", 21, 58, 376, t["muted"]) + "</g>")

    # bottom rule
    b.append(f'<path d="M56 412H{W - 56}" stroke="{t["border"]}"/>')
    disciplines = ["Backend", "AI systems", "Cloud & DevOps", "Full-stack product"]
    x = 56
    for i, d in enumerate(disciplines):
        b.append(label(d, x, 443, t["ink"] if i == 0 else t["muted"]))
        x += SANS_BOLD.width(d.upper(), 12.5, 2.2) + 22
        if i < len(disciplines) - 1:
            b.append(f'<circle cx="{fmt(x - 11)}" cy="438.5" r="1.6" fill="{t["faint"]}"/>')
    b.append(label("Sole engineer of yopapi.com", W - 80, 443, t["accent"], anchor="end"))
    b.append(arrow_ne(W - 70, 444, 9, t["accent"]))
    return svg(h, "".join(b), t, css, title="Abdullah, Software Engineer")


# ---------------------------------------------------------------- proof strip

PROOF = [
    ("20", "paying customers on a", "SaaS I built solo"),
    ("42", "companies scraped daily", "into one job board"),
    ("100%", "retrieval hit@6 on my", "insurance RAG eval"),
    ("2 yrs", "of freelance automation", "for paying clients"),
]


def proof(t):
    h = 150
    css = (".up{animation:up 1s cubic-bezier(.16,1,.3,1) both}"
           "@keyframes up{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}")
    b = []
    col = W / 4
    for i, (num, l1, l2) in enumerate(PROOF):
        x = i * col + (6 if i == 0 else 30)
        if i:
            b.append(f'<path d="M{fmt(i * col)} 26V124" stroke="{t["border"]}"/>')
        b.append(f'<g class="up" style="animation-delay:{0.15 * i:.2f}s">'
                 + SERIF.text(num, 54, x, 76, t["ink"], tracking=-1)
                 + SANS.text(l1, 15.5, x, 106, t["muted"])
                 + SANS.text(l2, 15.5, x, 127, t["muted"]) + "</g>")
    return svg(h, "".join(b), t, css, card=False,
               title="20 paying customers. 42 companies scraped daily. 100% retrieval hit@6. 2 years of freelance automation.")


# ---------------------------------------------------------------- section titles

def section(t, num, title):
    h = 84
    b = [label(num, 2, 52, t["accent"]),
         SERIF_REG.text(title, 34, 46, 56, t["ink"], tracking=-0.4)]
    x = 46 + SERIF_REG.width(title, 34, -0.4) + 24
    b.append(f'<path d="M{fmt(x)} 45H{W - 2}" stroke="{t["border"]}"/>')
    return svg(h, "".join(b), t, card=False, title=title)


# ---------------------------------------------------------------- flagship

def flagship(t):
    h = 540
    css = (
        ".glow{animation:drift 16s ease-in-out infinite alternate}"
        "@keyframes drift{from{transform:translate(0,0)}to{transform:translate(-60px,50px)}}"
        ".tile{animation:pub 12s linear infinite both}"
        "@keyframes pub{0%,8%{fill:" + t["tile"] + ";stroke:" + t["border"] + "}"
        "12%,100%{fill:" + t["accent"] + ";stroke:" + t["accent"] + "}}"
        ".tick{animation:tick 12s linear infinite both}"
        "@keyframes tick{0%,9%{opacity:0}13%,100%{opacity:1}}"
        ".bar{transform-box:fill-box;transform-origin:left;animation:bar 4s cubic-bezier(.65,0,.35,1) infinite}"
        "@keyframes bar{0%{transform:scaleX(0)}70%,100%{transform:scaleX(1)}}"
    )
    b = [f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="22" fill="{t["surface"]}" stroke="{t["border"]}"/>',
         glow(t, 900, 60, 360, "fg")]

    lx = 48
    b.append(f'<circle cx="{lx + 4}" cy="57" r="4" fill="{t["accent"]}"/>')
    b.append(label("Flagship  ·  Live SaaS  ·  20 paying customers", lx + 18, 61.5, t["accent"]))
    b.append(SERIF.text("yopapi.com", 60, lx - 3, 136, t["ink"], tracking=-1.5))
    b.append(ITALIC.text("An AI social media team, in a box.", 25, lx, 176, t["muted"]))
    body = ["Businesses describe their brand once. The platform then designs",
            "on-brand images and captions with OpenAI and publishes them to",
            "Instagram and Facebook every week, checking that each post actually",
            "went live. I built it solo for a Moroccan client and I still run it."]
    for i, line in enumerate(body):
        b.append(SANS.text(line, 16.5, lx, 222 + i * 26, t["muted"]))

    stats = [("Solo", "idea to production"), ("EN · FR · AR", "with full RTL layout"),
             ("Multi-tenant", "one codebase, two brands")]
    x = lx
    for big, small in stats:
        b.append(SERIF.text(big, 24, x, 358, t["ink"], tracking=-0.3))
        b.append(SANS.text(small, 13.5, x, 382, t["muted"]))
        x += max(SERIF.width(big, 24), SANS.width(small, 13.5)) + 40

    b.append(chips(["Next.js 16", "TypeScript", "Prisma", "PostgreSQL · Neon", "Node worker · Railway",
                    "OpenAI", "Meta Graph API", "Stripe", "Cloudflare R2", "Vercel"],
                   lx, 412, t, 600))

    # content calendar illustration
    gx, gy, cell, gap = 612, 104, 38, 9
    panel_w = 7 * cell + 6 * gap + 40
    b.append(f'<rect x="{gx - 20}" y="{gy - 56}" width="{panel_w}" height="350" rx="16" '
             f'fill="{t["bg"]}" stroke="{t["border"]}"/>')
    b.append(label("Publishing calendar", gx, gy - 28, t["muted"], size=11))
    b.append(f'<circle cx="{gx + panel_w - 46}" cy="{gy - 32}" r="3.5" fill="{t["accent"]}"/>')
    b.append(SANS_MED.text("Live", 11.5, gx + panel_w - 38, gy - 28, t["accent"]))
    for i, d in enumerate("MTWTFSS"):
        b.append(SANS_MED.text(d, 11.5, gx + i * (cell + gap) + cell / 2, gy - 4, t["faint"], anchor="middle"))
    posts = {(0, 0), (2, 0), (4, 0), (6, 0), (1, 1), (3, 1), (5, 1), (0, 2), (2, 2), (4, 2), (6, 2)}
    order = sorted(posts, key=lambda p: (p[1], p[0]))
    for r in range(3):
        for c in range(7):
            x, y = gx + c * (cell + gap), gy + 8 + r * (cell + gap)
            if (c, r) in posts:
                delay = order.index((c, r)) * 0.9
                b.append(f'<rect class="tile" style="animation-delay:{delay:.1f}s" x="{x}" y="{y}" '
                         f'width="{cell}" height="{cell}" rx="9" fill="{t["accent"]}" stroke="{t["accent"]}"/>')
                b.append(f'<g class="tick" style="animation-delay:{delay:.1f}s">'
                         + check(x + cell / 2, y + cell / 2, 13, t["accent_ink"]) + "</g>")
            else:
                b.append(f'<rect x="{x + 0.5}" y="{y + 0.5}" width="{cell - 1}" height="{cell - 1}" rx="9" '
                         f'fill="none" stroke="{t["border"]}" stroke-dasharray="3 4"/>')
    # next-post card
    py = gy + 8 + 3 * (cell + gap) + 12
    pw = 7 * cell + 6 * gap
    b.append(f'<rect x="{gx}" y="{py}" width="{pw}" height="98" rx="12" fill="{t["tile"]}" stroke="{t["border"]}"/>')
    b.append(f'<defs><linearGradient id="img" x1="0" y1="0" x2="1" y2="1">'
             f'<stop offset="0" stop-color="{t["accent"]}"/><stop offset="1" stop-color="{t["glow"]}"/>'
             f'</linearGradient></defs>')
    b.append(f'<rect x="{gx + 14}" y="{py + 14}" width="70" height="70" rx="9" fill="url(#img)"/>')
    b.append(SANS_BOLD.text("Next post", 13, gx + 98, py + 32, t["ink"]))
    b.append(SANS.text("Generated 5 min before it's due", 12.5, gx + 98, py + 52, t["muted"]))
    b.append(f'<rect x="{gx + 98}" y="{py + 66}" width="{pw - 112}" height="5" rx="2.5" fill="{t["border"]}"/>')
    b.append(f'<rect class="bar" x="{gx + 98}" y="{py + 66}" width="{pw - 112}" height="5" rx="2.5" fill="{t["accent"]}"/>')

    b.append(SANS_MED.text("Visit yopapi.com", 14, W - 66, h - 40, t["accent"], anchor="end"))
    b.append(arrow_ne(W - 58, h - 39, 9, t["accent"]))
    return svg(h, "".join(b), t, css, card=False,
               title="yopapi.com: an AI social media SaaS with 20 paying customers, built solo")


# ---------------------------------------------------------------- project cards

PROJECTS = {
    "jobless": dict(
        eyebrow="Live  ·  Data platform", title="Jobless",
        tagline="Every tech job in Pakistan, in one place.",
        body=["Scrapes 42 company career pages every day into",
              "PostgreSQL and ships a free static job board, with",
              "per-company failure isolation and an interview-prep hub."],
        stack="Python · PostgreSQL · Docker · Helm · ArgoCD · Actions",
        metric="254 commits"),
    "covered": dict(
        eyebrow="AI  ·  Retrieval-augmented generation", title="Am I Covered?",
        tagline="Ask your insurance policy. Get the clause.",
        body=["Hybrid search (dense + BM25, reranked) over a policy",
              "and federal rules. Every quote is verified against the",
              "source, and plain Python, not the LLM, does the math."],
        stack="FastAPI · Qdrant · Claude · React · TypeScript",
        metric="100% hit@6"),
    "mirror": dict(
        eyebrow="Android  ·  Computer vision", title="Fitting Mirror",
        tagline="Try clothes on without touching them.",
        body=["A camera mirror that tracks the body with MediaPipe",
              "Pose and warps garments onto it live, driven from a",
              "tablet app. Fully offline, over the store's own Wi-Fi."],
        stack="Kotlin · Jetpack Compose · MediaPipe · Local HTTP",
        metric="On-device"),
    "batman": dict(
        eyebrow="Creative  ·  Interactive web", title="Why Do We Fall?",
        tagline="A scroll-driven Batman tribute.",
        body=["Four films, four falls, one rise. Canvas rain and",
              "bats, sound design and scroll choreography,",
              "built from scratch with GSAP and Lenis."],
        stack="Vite · GSAP · Lenis · Canvas · Web Audio",
        metric="Live"),
}

CW = 490  # card width; two cards sit side by side in the README


def card(t, p):
    h = 330
    b = [f'<rect x="0.5" y="0.5" width="{CW - 1}" height="{h - 1}" rx="20" fill="{t["surface"]}" stroke="{t["border"]}"/>']
    b.append(label(p["eyebrow"], 34, 52, t["accent"], size=11.5))
    b.append(f'<circle cx="{CW - 50}" cy="48" r="17" fill="none" stroke="{t["border"]}"/>')
    b.append(arrow_ne(CW - 55, 53, 9, t["ink"], 1.5))
    b.append(SERIF.text(p["title"], 38, 32, 112, t["ink"], tracking=-0.8))
    b.append(ITALIC.text(p["tagline"], 18.5, 34, 146, t["muted"]))
    for i, line in enumerate(p["body"]):
        b.append(SANS.text(line, 14.5, 34, 190 + i * 23, t["muted"]))
    b.append(f'<path d="M34 268H{CW - 34}" stroke="{t["border"]}"/>')
    b.append(SANS_MED.text(p["stack"], 12.5, 34, 298, t["faint"]))
    b.append(SANS_BOLD.text(p["metric"], 12.5, CW - 34, 298, t["accent"], anchor="end"))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{CW}" height="{h}" viewBox="0 0 {CW} {h}" '
            f'role="img" aria-label="{p["title"]}"><title>{p["title"]}</title>{defs()}{"".join(b)}</svg>')


# ---------------------------------------------------------------- currently

NOW = [
    ("WhatsApp AI agent for yopapi customers",
     "Answers customer questions around the clock. Meta WhatsApp Cloud API, n8n, Hetzner VPS.", "Building"),
    ("yopapi.com  ·  Meta app review",
     "Submitted for Meta's platform review, which typically takes 3 to 4 weeks.", "In review"),
    ("Jobless  ·  from 42 to 100 companies",
     "One scraper plugin per company, with the company reviews API up next.", "Growing"),
]


def currently(t):
    row = 92
    h = 40 + row * len(NOW)
    css = (".pulse{transform-origin:center;transform-box:fill-box;animation:pulse 2.4s ease-out infinite}"
           "@keyframes pulse{0%{transform:scale(1);opacity:.6}100%{transform:scale(3.2);opacity:0}}")
    b = [f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="22" fill="{t["surface"]}" stroke="{t["border"]}"/>']
    for i, (title, desc, status) in enumerate(NOW):
        y = 20 + i * row
        if i:
            b.append(f'<path d="M40 {y}H{W - 40}" stroke="{t["border"]}"/>')
        b.append(f'<circle cx="52" cy="{y + 40}" r="4.5" fill="{t["accent"]}"/>')
        b.append(f'<circle class="pulse" style="animation-delay:{i * 0.8:.1f}s" cx="52" cy="{y + 40}" r="4.5" fill="{t["accent"]}"/>')
        b.append(SERIF.text(title, 22, 76, y + 47, t["ink"], tracking=-0.2))
        b.append(SANS.text(desc, 14.5, 76, y + 72, t["muted"]))
        sw = SANS_BOLD.width(status.upper(), 11, 2) + 28
        b.append(f'<rect x="{fmt(W - 40 - sw)}" y="{y + 27}" width="{fmt(sw)}" height="28" rx="14" '
                 f'fill="none" stroke="{t["accent"]}"/>')
        b.append(SANS_BOLD.text(status.upper(), 11, W - 40 - sw / 2, y + 45, t["accent"], tracking=2, anchor="middle"))
    return svg(h, "".join(b), t, css, card=False, title="What I am building right now")


# ---------------------------------------------------------------- toolkit

TOOLKIT = [
    ("Languages", "TypeScript · Python · Go · Kotlin · SQL · Bash"),
    ("Backend", "Node.js · Next.js · FastAPI · Django · PostgreSQL · Prisma · MongoDB"),
    ("AI", "OpenAI · Claude · RAG · Qdrant · Hugging Face · LLM fine-tuning"),
    ("Cloud & DevOps", "AWS · Docker · Kubernetes · Helm · ArgoCD · Terraform · Ansible"),
    ("Platforms", "Vercel · Railway · Neon · Cloudflare R2 · Hetzner · Stripe · n8n"),
    ("Automation", "Playwright · Selenium · Chrome extensions · Meta Graph API"),
]


def toolkit(t):
    row = 52
    h = 28 + row * len(TOOLKIT)
    b = [f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="22" fill="{t["surface"]}" stroke="{t["border"]}"/>']
    for i, (cat, items) in enumerate(TOOLKIT):
        y = 14 + i * row
        if i:
            b.append(f'<path d="M40 {y}H{W - 40}" stroke="{t["border"]}"/>')
        b.append(label(cat, 40, y + 31, t["accent"], size=11.5))
        b.append(SANS.text(items, 16, 230, y + 32, t["ink"]))
    return svg(h, "".join(b), t, card=False, title="Toolkit")


# ---------------------------------------------------------------- activity

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 profile-readme-build"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def fetch_activity():
    """Last year of GitHub contributions plus the WakaTime all-time total, or None."""
    try:
        page = fetch(f"https://github.com/users/{GITHUB_USER}/contributions")
        tips = dict(re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]+)</tool-tip>', page))
        days = []
        for cell in re.findall(r"<td[^>]*data-date=[^>]*>", page):
            d = re.search(r'data-date="([^"]+)"', cell).group(1)
            level = int(re.search(r'data-level="(\d)"', cell).group(1))
            n = re.match(r"(\d+)", tips.get(re.search(r'id="([^"]+)"', cell).group(1), ""))
            days.append((date.fromisoformat(d), int(n.group(1)) if n else 0, level))
        days.sort()
        if len(days) < 300:
            return None
    except Exception as e:  # network or markup change: keep the last good card
        print("activity: github fetch failed:", e)
        return None
    hours = None
    try:
        texts = re.findall(r">([^<>]+)</text>", fetch(WAKATIME_BADGE))
        hours = next((x.strip() for x in texts if "hr" in x), None)
    except Exception as e:
        print("activity: wakatime fetch failed:", e)
    return days, hours


def streaks(days):
    counts = [n for _, n, _ in days]
    longest = run = 0
    for n in counts:
        run = run + 1 if n else 0
        longest = max(longest, run)
    current, i = 0, len(counts) - 1
    if counts and counts[i] == 0:  # today isn't over yet
        i -= 1
    while i >= 0 and counts[i]:
        current, i = current + 1, i - 1
    return current, longest


def activity(t, data):
    days, hours = data
    h = 360
    css = (".col{animation:up .7s cubic-bezier(.16,1,.3,1) both}"
           "@keyframes up{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}")
    b = [f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="22" fill="{t["surface"]}" stroke="{t["border"]}"/>']

    total = sum(n for _, n, _ in days)
    current, longest = streaks(days)
    stats = [(f"{total:,}", "contributions in", "the last year"),
             (f"{current} day{'s' if current != 1 else ''}", "current streak", "and counting"),
             (f"{longest} days", "longest streak", "this year")]
    if hours:
        stats.append((hours.split(" hr")[0] + " hrs", "of tracked coding", "on WakaTime"))
    col = (W - 80) / len(stats)
    for i, (num, l1, l2) in enumerate(stats):
        x = 40 + i * col
        if i:
            b.append(f'<path d="M{fmt(x - 20)} 40V128" stroke="{t["border"]}"/>')
        b.append(SERIF.text(num, 40, x, 82, t["ink"], tracking=-0.8))
        b.append(SANS.text(l1, 14, x, 108, t["muted"]))
        b.append(SANS.text(l2, 14, x, 127, t["muted"]))

    # heatmap: one column per week, Sunday on top, like GitHub's own graph
    cell, gap, top = 13.6, 3.7, 186
    start = days[0][0] - timedelta(days=(days[0][0].weekday() + 1) % 7)
    weeks = (days[-1][0] - start).days // 7 + 1
    left = (W - (weeks * cell + (weeks - 1) * gap)) / 2
    by_week = {}
    for d, n, level in days:
        by_week.setdefault((d - start).days // 7, []).append((d, level))
    for wk in range(weeks):
        x = left + wk * (cell + gap)
        cells = by_week.get(wk, [])
        first = next((d for d, _ in cells if d.day == 1), None)
        if first and wk < weeks - 2:
            b.append(SANS_MED.text(first.strftime("%b"), 11.5, x, top - 12, t["faint"]))
        rects = "".join(
            f'<rect x="{fmt(x)}" y="{fmt(top + ((d.weekday() + 1) % 7) * (cell + gap))}" '
            f'width="{cell}" height="{cell}" rx="3.2" fill="{t["heat"][level]}"/>' for d, level in cells)
        b.append(f'<g class="col" style="animation-delay:{wk * 0.014:.3f}s">{rects}</g>')

    fy = top + 7 * (cell + gap) + 30
    b.append(SANS.text("Less", 12, left, fy, t["faint"]))
    lx = left + SANS.width("Less", 12) + 8
    for i, c in enumerate(t["heat"]):
        b.append(f'<rect x="{fmt(lx + i * 15)}" y="{fy - 10}" width="11" height="11" rx="2.5" fill="{c}"/>')
    b.append(SANS.text("More", 12, lx + 5 * 15 + 4, fy, t["faint"]))
    updated = f"{days[-1][0]:%b} {days[-1][0].day}, {days[-1][0].year}"
    b.append(SANS.text(f"Updated daily  ·  {updated}", 12, W - left, fy, t["faint"], anchor="end"))
    return svg(h, "".join(b), t, css, card=False,
               title=f"{total} GitHub contributions in the last year. Current streak {current} days, longest {longest} days.")


# ---------------------------------------------------------------- contact

def contact(t):
    h = 330
    css = (".glow{animation:drift 14s ease-in-out infinite alternate}"
           "@keyframes drift{from{transform:translate(0,0)}to{transform:translate(80px,-30px)}}")
    b = [glow(t, 180, 330, 380, "cg")]
    b.append(label("Let's work together", W / 2, 74, t["accent"], anchor="middle"))
    b.append(SERIF_REG.text("Have something that needs building?", 46, W / 2, 140, t["ink"], tracking=-1, anchor="middle"))
    b.append(ITALIC.text("A product, an AI feature, or the infrastructure behind it.", 22, W / 2, 182, t["muted"], anchor="middle"))
    b.append(SANS_MED.text("abdullah.compscientist@gmail.com", 21, W / 2, 250, t["accent"], anchor="middle"))
    ew = SANS_MED.width("abdullah.compscientist@gmail.com", 21)
    b.append(f'<path d="M{fmt(W / 2 - ew / 2)} 262H{fmt(W / 2 + ew / 2)}" stroke="{t["accent"]}" stroke-opacity=".4"/>')
    b.append(SANS.text("I usually reply within a day.", 14, W / 2, 294, t["faint"], anchor="middle"))
    return svg(h, "".join(b), t, css, title="Have something that needs building? Email abdullah.compscientist@gmail.com")


def button(t, text):
    h = 48
    tw = SANS_MED.width(text, 14.5)
    w = int(tw + 64)
    b = (f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="24" fill="{t["surface"]}" stroke="{t["border"]}"/>'
         + SANS_MED.text(text, 14.5, 24, 29.5, t["ink"]) + arrow_ne(w - 31, 29, 8, t["accent"], 1.5))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{text}"><title>{text}</title>{defs()}{b}</svg>')


BUTTONS = {"email": "Email", "linkedin": "LinkedIn", "yopapi": "yopapi.com", "portfolio": "Portfolio"}


def main():
    OUT.mkdir(exist_ok=True)
    data = fetch_activity()
    for name, t in THEMES.items():
        if data:
            (OUT / f"activity-{name}.svg").write_text(activity(t, data), encoding="utf-8")
        assets = {
            "header": header(t),
            "proof": proof(t),
            "flagship": flagship(t),
            "currently": currently(t),
            "toolkit": toolkit(t),
            "contact": contact(t),
            "section-work": section(t, "01", "Selected work"),
            "section-now": section(t, "02", "Currently building"),
            "section-toolkit": section(t, "03", "Toolkit"),
            "section-activity": section(t, "04", "Activity"),
        }
        assets.update({f"card-{key}": card(t, p) for key, p in PROJECTS.items()})
        assets.update({f"btn-{key}": button(t, text) for key, text in BUTTONS.items()})
        for asset, content in assets.items():
            (OUT / f"{asset}-{name}.svg").write_text(content, encoding="utf-8")
    print(f"wrote {len(list(OUT.glob('*.svg')))} files to {OUT}")


if __name__ == "__main__":
    main()
