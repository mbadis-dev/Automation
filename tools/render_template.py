#!/usr/bin/env python3
"""Render a sample Reel (MP4), cover and Story slides: Docker Compose health checks."""
import os, re, subprocess, sys
from functools import lru_cache

import yaml
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

FD = "/usr/share/fonts/truetype/dejavu/"
BOLD, SANS = "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"
MONO = "DejaVuSansMono.ttf"
MONOB = "DejaVuSansMono-Bold.ttf" if os.path.exists(FD + "DejaVuSansMono-Bold.ttf") else MONO


@lru_cache(None)
def font(name, size):
    return ImageFont.truetype(FD + name, size)


WHITE = (240, 246, 252)
MUTED = (139, 148, 158)
BLUE = (121, 192, 255)
GREEN = (126, 231, 135)
ORANGE = (255, 166, 87)
RED = (255, 123, 114)
PURPLE = (210, 168, 255)
PANEL = (13, 17, 23)
BORDER = (48, 54, 61)
HL_RED = (110, 30, 36)
HL_GREEN = (22, 80, 40)

# ---------------------------------------------------------------- content
BAD = [
    "services:",
    "  db:",
    "    image: postgres:16",
    "  app:",
    "    build: .",
    "    depends_on:",
    "      - db",
]
GOOD = [
    "db:",
    "  healthcheck:",
    '    test: ["CMD-SHELL",',
    '      "pg_isready -U postgres"]',
    "    interval: 5s",
    "    retries: 5",
    "app:",
    "  depends_on:",
    "    db:",
    "      condition: service_healthy",
]


def validate_yaml():
    """Make sure the snippets shown in the video are valid Compose YAML."""
    bad = yaml.safe_load("\n".join(BAD))
    assert bad["services"]["app"]["depends_on"] == ["db"]
    full = "services:\n  db:\n    image: postgres:16\n" + "\n".join(
        "  " + l for l in GOOD[1:6]
    ) + "\n  app:\n    build: .\n" + "\n".join("  " + l for l in GOOD[7:]) + "\n"
    doc = yaml.safe_load(full)
    hc = doc["services"]["db"]["healthcheck"]
    assert hc["test"] == ["CMD-SHELL", "pg_isready -U postgres"], hc
    assert doc["services"]["app"]["depends_on"]["db"]["condition"] == "service_healthy"
    print("YAML snippets valid")


# ---------------------------------------------------------------- background
def make_bg():
    g = Image.linear_gradient("L").resize((W, H))
    top, bot = (13, 17, 23), (20, 26, 46)
    bg = Image.merge(
        "RGB",
        [g.point(lambda v, a=a, b=b: int(a + (b - a) * v / 255)) for a, b in zip(top, bot)],
    ).convert("RGBA")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((560, -200, 1260, 500), fill=(56, 139, 253, 70))
    gd.ellipse((-300, 1300, 400, 2000), fill=(163, 113, 247, 55))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    bg.alpha_composite(glow)
    return bg


BG = make_bg()


# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def appear(t, t0, dur=0.35):
    return ease((t - t0) / dur)


def new_layer():
    l = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    return l, ImageDraw.Draw(l)


def rgba(c, p=1.0):
    return (c[0], c[1], c[2], int(255 * clamp(p)))


def text_c(d, y, s, size, fill, p=1.0, name=BOLD, stroke=0, x=W // 2, rise=36):
    d.text(
        (x, y + (1 - p) * rise),
        s,
        font=font(name, size),
        fill=rgba(fill, p),
        anchor="ma",
        stroke_width=stroke,
        stroke_fill=(0, 0, 0, int(255 * clamp(p))),
    )


def brand(d, y=230, p=1.0):
    text_c(d, y, "@med_bedis_guesmi", 38, MUTED, p, name=SANS, rise=0)


def pill(d, cx, y, s, size, fg, bg_c, p=1.0, pad=30):
    f = font(BOLD, size)
    w = f.getlength(s)
    x0, x1 = cx - w / 2 - pad, cx + w / 2 + pad
    d.rounded_rectangle((x0, y, x1, y + size + 36), radius=(size + 36) // 2, fill=rgba(bg_c, p))
    d.text((cx, y + 18), s, font=f, fill=rgba(fg, p), anchor="ma")


def colorize(line):
    segs = []
    ind, rest = re.match(r"^(\s*)(.*)$", line).groups()
    if ind:
        segs.append((ind, WHITE))
    if rest.startswith("- "):
        segs.append(("- ", PURPLE))
        rest = rest[2:]
    m = re.match(r"^([A-Za-z_][\w-]*)(:)(.*)$", rest)
    if m:
        k, c, v = m.groups()
        segs += [(k, BLUE), (c, WHITE)]
        if v:
            vs = v.lstrip()
            sp = v[: len(v) - len(vs)]
            if sp:
                segs.append((sp, WHITE))
            segs.append((vs, GREEN if vs[:1] in '"[' else ORANGE))
    elif rest:
        segs.append((rest, GREEN if rest[:1] == '"' else WHITE))
    return segs


def trunc(segs, n):
    out = []
    for s, c in segs:
        if n <= 0:
            break
        out.append((s[:n], c))
        n -= len(s)
    return out


def panel(d, x, y, w, title, vis_lines, total_lines, size=44, hl=None, hl_col=None, cursor=None, p=1.0):
    lh = int(size * 1.5)
    h = 84 + total_lines * lh + 36
    d.rounded_rectangle((x, y, x + w, y + h), radius=28, fill=rgba(PANEL, 0.96 * p), outline=rgba(BORDER, p), width=3)
    for i, col in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        d.ellipse((x + 30 + i * 40, y + 28, x + 50 + i * 40, y + 48), fill=rgba(col, p))
    d.text((x + w - 36, y + 24), title, font=font(SANS, 28), fill=rgba(MUTED, p), anchor="ra")
    f = font(MONOB, size)
    cw = f.getlength("M")
    last = None
    for i, segs in enumerate(vis_lines):
        ly = y + 84 + i * lh
        if hl is not None and i == hl:
            d.rounded_rectangle((x + 14, ly - 4, x + w - 14, ly + lh - 8), radius=12, fill=rgba(hl_col, p))
        cx = x + 36
        for s, c in segs:
            d.text((cx, ly), s, font=f, fill=rgba(c, p))
            cx += cw * len(s)
        last = (cx, ly)
    if cursor and last:
        d.rectangle((last[0] + 2, last[1] + 4, last[0] + cw * 0.9, last[1] + size + 4), fill=rgba(WHITE, 0.85 * p))
    return y + h


def code_vis(lines, n):
    vis = []
    for ln in lines:
        if n <= 0:
            break
        vis.append(trunc(colorize(ln), n))
        n -= len(ln)
    return vis


# ---------------------------------------------------------------- reel scenes
TERM_OUT = [
    [("NAME    STATUS", MUTED)],
    [("db      ", WHITE), ("Up 2 seconds", GREEN)],
    [("app     ", WHITE), ("Exited (1)", RED)],
]
BAD_N = sum(len(l) for l in BAD)
GOOD_N = sum(len(l) for l in GOOD)


def scene_hook(t):
    l, d = new_layer()
    brand(d)
    lines = [("Your Docker", WHITE), ("container", WHITE), ("might be", WHITE), ("LYING", RED), ("to you.", WHITE)]
    for i, (s, c) in enumerate(lines):
        text_c(d, 430 + i * 150, s, 120 if s == "LYING" else 112, c, appear(t, 0.1 + i * 0.22), stroke=2)
    pulse = 0.75 + 0.25 * abs(((t * 1.4) % 2) - 1)
    pill(d, W // 2, 1250, "app  ●  Up 3 minutes", 46, (10, 40, 18), GREEN, appear(t, 1.3) * pulse)
    return l


def scene_problem(t):
    l, d = new_layer()
    brand(d)
    text_c(d, 310, "Up ≠ healthy", 112, WHITE, appear(t, 0.0), stroke=2)
    cmd = "$ docker compose ps"
    typed = int(clamp((t - 0.5) * 22, 0, len(cmd)))
    vis = [[(cmd[:typed], WHITE)]] if typed else []
    for i, tt in enumerate((1.7, 2.2, 2.7)):
        if t >= tt:
            vis.append(TERM_OUT[i])
    blink = typed < len(cmd) or int(t * 2) % 2 == 0
    panel(d, 60, 560, 960, "terminal (example)", vis, 4, size=42, cursor=blink)
    text_c(d, 1130, "Compose started the database,", 52, WHITE, appear(t, 3.4), stroke=2)
    text_c(d, 1200, "but Postgres wasn't ready yet.", 52, ORANGE, appear(t, 3.9), stroke=2)
    return l


def scene_mistake(t):
    l, d = new_layer()
    brand(d)
    text_c(d, 320, "The common mistake", 68, RED, appear(t, 0.0), stroke=2)
    n = int(clamp((t - 0.4) * 40, 0, BAD_N))
    vis = code_vis(BAD, n)
    hl = 6 if n >= BAD_N else None
    bottom = panel(d, 60, 480, 960, "docker-compose.yml", vis, len(BAD), size=44, hl=hl, hl_col=HL_RED, cursor=n < BAD_N)
    text_c(d, bottom + 60, "depends_on only waits", 54, WHITE, appear(t, 3.0), stroke=2)
    text_c(d, bottom + 130, "for the container to START.", 54, RED, appear(t, 3.4), stroke=2)
    return l


def scene_fix(t):
    l, d = new_layer()
    brand(d)
    text_c(d, 310, "The fix", 100, GREEN, appear(t, 0.0), stroke=2)
    n = int(clamp((t - 0.4) * 40, 0, GOOD_N))
    vis = code_vis(GOOD, n)
    hl = 9 if n >= GOOD_N else None
    bottom = panel(d, 60, 480, 960, "docker-compose.yml", vis, len(GOOD), size=44, hl=hl, hl_col=HL_GREEN, cursor=n < GOOD_N)
    text_c(d, bottom + 50, "Now the app waits until", 54, WHITE, appear(t, 4.6), stroke=2)
    text_c(d, bottom + 120, "the health check passes.", 54, GREEN, appear(t, 5.0), stroke=2)
    return l


def scene_takeaway(t):
    l, d = new_layer()
    brand(d)
    text_c(d, 520, "Started", 130, WHITE, appear(t, 0.1), stroke=2)
    text_c(d, 670, "≠", 150, MUTED, appear(t, 0.5), stroke=2)
    text_c(d, 840, "ready.", 150, WHITE, appear(t, 0.9), stroke=2)
    text_c(d, 1130, "Wait for", 64, MUTED, appear(t, 1.8), stroke=2)
    text_c(d, 1215, "service_healthy", 78, GREEN, appear(t, 2.1), name=MONOB, stroke=2)
    return l


def scene_cta(t):
    l, d = new_layer()
    brand(d)
    text_c(d, 560, "Save this", 120, WHITE, appear(t, 0.1), stroke=2)
    text_c(d, 700, "for your next project", 70, WHITE, appear(t, 0.4), stroke=2)
    pill(d, W // 2, 940, "Follow for daily dev tips", 56, (13, 17, 23), BLUE, appear(t, 1.0))
    text_c(d, 1160, "Which topic should I cover next?", 48, MUTED, appear(t, 1.8), name=SANS, rise=20)
    return l


SCENES = [
    (scene_hook, 3.2),
    (scene_problem, 6.3),
    (scene_mistake, 6.0),
    (scene_fix, 9.0),
    (scene_takeaway, 4.2),
    (scene_cta, 3.8),
]
TOTAL = sum(d for _, d in SCENES)


def fade(t, dur, first=False, last=False):
    a = 1.0 if first else clamp(t / 0.3)
    b = clamp((dur - t) / 0.3)
    return min(a, b)


def render_reel(path):
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", f"{TOTAL:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-shortest", path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nframes = int(round(TOTAL * FPS))
    starts, acc = [], 0.0
    for fn, dur in SCENES:
        starts.append((acc, fn, dur))
        acc += dur
    for i in range(nframes):
        t = i / FPS
        idx = max(k for k, (s, _, _) in enumerate(starts) if s <= t + 1e-9)
        s0, fn, dur = starts[idx]
        lt = t - s0
        layer = fn(lt)
        g = fade(lt, dur, first=(idx == 0))
        if g < 1.0:
            layer.putalpha(layer.getchannel("A").point(lambda v: int(v * g)))
        frame = BG.copy()
        frame.alpha_composite(layer)
        proc.stdin.write(frame.convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg failed")


# ---------------------------------------------------------------- stills
def save_still(layer, path):
    f = BG.copy()
    f.alpha_composite(layer)
    f.convert("RGB").save(path, optimize=True)


def cover(path):
    l, d = new_layer()
    text_c(d, 470, "Docker says:", 70, MUTED, rise=0)
    text_c(d, 560, "Up.", 230, GREEN, stroke=3, rise=0)
    text_c(d, 880, "Your app:", 70, MUTED, rise=0)
    text_c(d, 970, "Crashed.", 190, RED, stroke=3, rise=0)
    pill(d, W // 2, 1260, "Docker Compose health checks", 44, WHITE, (33, 38, 45))
    text_c(d, 1400, "@med_bedis_guesmi", 38, MUTED, name=SANS, rise=0)
    save_still(l, path)


def story1(path):
    l, d = new_layer()
    brand(d, 300)
    pill(d, W // 2, 400, "QUICK QUIZ", 44, (13, 17, 23), BLUE)
    for i, (s, c, sz) in enumerate([("Your container", WHITE, 84), ("shows", WHITE, 84), ("Up.", GREEN, 190)]):
        text_c(d, 560 + i * (110 if i < 2 else 110), s, sz, c, stroke=2, rise=0)
    text_c(d, 1000, "Does that mean your", 64, WHITE, stroke=2, rise=0)
    text_c(d, 1080, "app is healthy?", 64, WHITE, stroke=2, rise=0)
    for cx, label, col in ((310, "A  Yes", GREEN), (770, "B  No", RED)):
        d.rounded_rectangle((cx - 190, 1230, cx + 190, 1360), radius=36, fill=rgba(PANEL), outline=rgba(col), width=5)
        d.text((cx, 1262), label, font=font(BOLD, 62), fill=rgba(col), anchor="ma")
    text_c(d, 1440, "Reply with your answer", 40, MUTED, name=SANS, rise=0)
    save_still(l, path)


def story2(path):
    l, d = new_layer()
    brand(d, 300)
    text_c(d, 380, "Compose health check", 70, WHITE, stroke=2, rise=0)
    vis = code_vis(GOOD, GOOD_N)
    bottom = panel(d, 60, 520, 960, "docker-compose.yml", vis, len(GOOD), size=44, hl=9, hl_col=HL_GREEN)
    text_c(d, bottom + 70, "Wait for healthy,", 62, WHITE, stroke=2, rise=0)
    text_c(d, bottom + 150, "not just started.", 62, GREEN, stroke=2, rise=0)
    save_still(l, path)


def story3(path):
    l, d = new_layer()
    brand(d, 300)
    text_c(d, 560, "Started", 120, WHITE, stroke=2, rise=0)
    text_c(d, 700, "≠", 140, MUTED, stroke=2, rise=0)
    text_c(d, 860, "ready.", 140, WHITE, stroke=2, rise=0)
    text_c(d, 1140, "Full breakdown in", 54, MUTED, rise=0)
    text_c(d, 1215, "today's Reel", 70, BLUE, rise=0)
    save_still(l, path)


def make_story_video(out_dir, seg=4.5, fade_d=0.5):
    """Join story-1..3.png into one 13.5 s 1080x1920 H.264/AAC Story video (story.mp4)."""
    slides = [os.path.join(out_dir, f"story-{i}.png") for i in (1, 2, 3)]
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for s in slides:
        cmd += ["-loop", "1", "-t", str(seg), "-framerate", str(FPS), "-i", s]
    cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    fc = (
        f"[0:v]fade=t=out:st={seg - fade_d}:d={fade_d}[v0];"
        f"[1:v]fade=t=in:st=0:d={fade_d},fade=t=out:st={seg - fade_d}:d={fade_d}[v1];"
        f"[2:v]fade=t=in:st=0:d={fade_d}[v2];"
        "[v0][v1][v2]concat=n=3:v=1:a=0,format=yuv420p[v]"
    )
    cmd += [
        "-filter_complex", fc, "-map", "[v]", "-map", "3:a", "-t", f"{seg * 3:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high",
        "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        "-shortest", os.path.join(out_dir, "story.mp4"),
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    # TEMPLATE: to make a new post, edit the content blocks (BAD / GOOD code, TERM_OUT,
    # scene texts, cover and story1-3 texts), keep the layout/safe-area helpers, then run:
    #   python3 render_template.py <output_dir>
    # Outputs: reel.mp4, cover.png, story-1..3.png, story.mp4
    validate_yaml()  # replace with a check for the new snippet (or remove if no code is shown)
    cover(os.path.join(OUT, "cover.png"))
    story1(os.path.join(OUT, "story-1.png"))
    story2(os.path.join(OUT, "story-2.png"))
    story3(os.path.join(OUT, "story-3.png"))
    print("stills done; rendering reel", TOTAL, "s")
    render_reel(os.path.join(OUT, "reel.mp4"))
    make_story_video(OUT)
    print("done")
