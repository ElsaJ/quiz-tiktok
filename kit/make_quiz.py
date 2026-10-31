#!/usr/bin/env python3
"""Génère une vidéo quiz TikTok au format de la chaîne rvise.tes.cours2026.
Usage: python3 make_quiz.py quiz.json sortie.mp4
quiz.json: {"matiere","niveau","fond","questions":[{"q","options":[3],"bonne":idx}x7],"bonus","fin"}
"""
import json, os, subprocess, sys, math, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

KIT = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(KIT, "fonts")
FONDS = os.path.join(KIT, "fonds")
W, H, FPS, SR = 576, 1024, 30, 44100
VOICE = "fr-FR-HenriNeural"

QS = ImageFont.truetype(os.path.join(FONTS, "Quicksand-700.ttf"), 28)
OP = ImageFont.truetype(os.path.join(FONTS, "Quicksand-700.ttf"), 28)
TIM = ImageFont.truetype(os.path.join(FONTS, "Quicksand-600.ttf"), 64)
END = ImageFont.truetype(os.path.join(FONTS, "Quicksand-700.ttf"), 31)
PB = os.path.join(FONTS, "Poppins-Bold.ttf")
PR = os.path.join(FONTS, "Poppins-Regular.ttf")

BOX = (80, 198, 494, 422)
OPTS = [(80, 466, 494, 538), (80, 577, 494, 649), (80, 688, 494, 760)]
REV = (80, 466, 494, 545)
TC = (288, 868)


def tts(text, path):
    key = os.environ["AZURE_TTS_KEY"].strip()
    esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    ssml = f"<speak version='1.0' xml:lang='fr-FR'><voice name='{VOICE}'>{esc}</voice></speak>"
    mp3 = path + ".mp3"
    subprocess.run(["curl", "-sS", "-f", "--max-time", "60", "-o", mp3, "-X", "POST",
                    "-H", f"Ocp-Apim-Subscription-Key: {key}",
                    "-H", "Content-Type: application/ssml+xml; charset=utf-8",
                    "-H", "X-Microsoft-OutputFormat: audio-24khz-96kbitrate-mono-mp3",
                    "-H", "User-Agent: quiz", "--data-binary", ssml.encode().decode(),
                    "https://francecentral.tts.speech.microsoft.com/cognitiveservices/v1"], check=True)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp3, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def wrap(text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.getlength(t) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    # éviter un "?" ou ":" orphelin seul
    return lines


def fit(text, size, maxw, maxlines, path=os.path.join(FONTS, "Quicksand-700.ttf")):
    while size > 14:
        f = ImageFont.truetype(path, size)
        lines = wrap(text, f, maxw)
        if len(lines) <= maxlines:
            return f, lines
        size -= 1
    return f, lines


def card(rect, text, font_size, fill=(255, 255, 255), fg=(0, 0, 0), maxlines=2):
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    im = Image.new("RGBA", (w + 4, h + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((2, 6, w + 1, h + 5), fill=(0, 0, 0, 255))          # ombre
    d.rectangle((0, 0, w - 1, h - 1), fill=fill + (255,), outline=(0, 0, 0, 255), width=2)
    f, lines = fit(text, font_size, w - 40, maxlines)
    lh = f.size * 1.32
    ty = (h - lh * len(lines)) / 2
    for i, l in enumerate(lines):
        d.text((w / 2, ty + i * lh + lh / 2), l, font=f, fill=fg, anchor="mm")
    return im


def timer_img(num, frac):
    S = 160
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    n, r0, r1 = 40, 50, 62
    c = S / 2
    for i in range(n):
        a0 = -90 + i * 360 / n
        p = i / n
        if p < 1 - frac:                      # écoulé
            col = (255, 214, 208, 255)
        else:
            k = (p - (1 - frac)) / max(frac, 1e-3)
            col = (int(232 + 18 * (1 - k)), int(52 + 110 * (1 - k)), int(44 + 100 * (1 - k)), 255)
        d.pieslice((c - r1, c - r1, c + r1, c + r1), a0, a0 + 360 / n, fill=col)
        a = math.radians(a0)
        d.line((c + r0 * math.cos(a), c + r0 * math.sin(a), c + r1 * math.cos(a), c + r1 * math.sin(a)),
               fill=(20, 15, 20, 255), width=2)
    d.ellipse((c - r0, c - r0, c + r0, c + r0), fill=(0, 0, 0, 0))
    hole = Image.new("L", (S, S), 255)
    ImageDraw.Draw(hole).ellipse((c - r0, c - r0, c + r0, c + r0), fill=0)
    im.putalpha(Image.fromarray(np.minimum(np.asarray(im.getchannel("A")), np.asarray(hole))))
    d = ImageDraw.Draw(im)
    d.text((c, c - 4), str(num), font=TIM, fill=(240, 80, 70, 255), anchor="mm")
    return im


COULEURS_FIN = {  # texte de fin adapté au fond : rouge sur fond clair, jaune sur fond sombre
    "rouge": ((190, 22, 28), (255, 248, 235)),
    "jaune": ((255, 238, 150), (60, 45, 40)),
}
FOND_COULEUR = {"francais.png": "rouge", "histoire-geo.png": "rouge", "ses.png": "rouge", "svt.png": "rouge",
                "maths.png": "rouge", "philo.png": "jaune", "physique-chimie.png": "jaune",
                "enseignement-scientifique.png": "jaune"}


# couleur du bandeau "bonne réponse" par matière (relevée sur les vidéos d'Elsa) : (fond, texte)
REVEAL = {"francais.png": ((89, 13, 13), (255, 255, 255)), "philo.png": ((87, 13, 11), (255, 255, 255)),
          "svt.png": ((112, 17, 28), (255, 255, 255)), "physique-chimie.png": ((112, 17, 28), (255, 255, 255)),
          "histoire-geo.png": ((198, 118, 40), (0, 0, 0)), "ses.png": ((233, 146, 61), (0, 0, 0)),
          "maths.png": ((235, 178, 45), (0, 0, 0)), "enseignement-scientifique.png": ((228, 164, 55), (0, 0, 0))}


def outlined_text(text, font, maxw, couleur="jaune"):
    fill, stroke = COULEURS_FIN[couleur]
    lines = wrap(text, font, maxw)
    lh = font.size * 1.15
    im = Image.new("RGBA", (W, int(lh * len(lines) + 20)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        d.text((W / 2, 10 + i * lh + lh / 2), l, font=font, fill=fill + (255,), anchor="mm",
               stroke_width=2, stroke_fill=stroke + (255,))
    return im


def cover(bg, matiere, niveau):
    im = bg.copy()
    d = ImageDraw.Draw(im)
    big = len(matiere) > 16
    y0, y1 = (405, 583) if not big else (390, 640)
    d.rectangle((0, y0 - 10, 555, y1 - 10), fill=(37, 244, 238))
    d.rectangle((20, y0 + 10, 576, y1 + 10), fill=(254, 44, 85))
    d.rectangle((10, y0, 566, y1), fill=(0, 0, 0))
    fq, fm, fn = ImageFont.truetype(PB, 34), ImageFont.truetype(PB, 42), ImageFont.truetype(PR, 34)
    d.text((288, y0 + 28), "QUIZ", font=fq, fill="white", anchor="mm")
    if big:
        mf, ml = fit(matiere, 42, 520, 2, PB)
        for i, l in enumerate(ml):
            d.text((288, y0 + 84 + i * 52), l, font=mf, fill="white", anchor="mm")
        d.text((288, y1 - 28), niveau, font=fn, fill="white", anchor="mm")
    else:
        mf, _ = fit(matiere, 42, 520, 1, PB)
        d.text((288, y0 + 92), matiere, font=mf, fill="white", anchor="mm")
        d.text((288, y0 + 152), niveau, font=fn, fill="white", anchor="mm")
    return im


MUSIQUES = {
    # 1 : pop légère (celle validée sur la vidéo test)
    1: dict(bpm=104, prog=[[261.63, 329.63, 392.0], [196.0, 246.94, 293.66], [220.0, 261.63, 329.63], [174.61, 220.0, 261.63]],
            motif=[0, 1, 2, 1], harm=(0.3, 0.0), decay=9),
    # 2 : marimba plus rapide
    2: dict(bpm=118, prog=[[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [261.63, 329.63, 392.0], [196.0, 246.94, 293.66]],
            motif=[0, 2, 1, 2], harm=(0.0, 0.25), decay=14),
    # 3 : clochettes plus calmes
    3: dict(bpm=94, prog=[[293.66, 369.99, 440.0], [246.94, 293.66, 369.99], [196.0, 246.94, 293.66], [220.0, 277.18, 329.63]],
            motif=[0, 1, 2, 0], harm=(0.15, 0.2), decay=6),
}


def synth_music(dur, variant=1):
    M = MUSIQUES[variant]
    t = np.arange(int(dur * SR)) / SR
    bpm = M["bpm"]; beat = 60 / bpm
    prog = M["prog"]
    out = np.zeros_like(t)
    nsteps = int(dur / (beat / 2)) + 1
    for s in range(nsteps):
        st = s * beat / 2
        chord = prog[int(st / (beat * 4)) % 4]
        f = chord[M["motif"][s % 4]] * 2
        i0 = int(st * SR); L = int(0.35 * SR)
        seg = t[:L]
        env = np.exp(-seg * M["decay"])
        h2, h3 = M["harm"]
        tone = (np.sin(2 * np.pi * f * seg) + h2 * np.sin(4 * np.pi * f * seg) + h3 * np.sin(6 * np.pi * f * seg)) * env * 0.16
        out[i0:i0 + L] += tone[:len(out[i0:i0 + L])]
        if s % 2 == 0:  # kick doux
            Lk = int(0.18 * SR); sk = t[:Lk]
            k = np.sin(2 * np.pi * (55 + 90 * np.exp(-sk * 30)) * sk) * np.exp(-sk * 18) * 0.35
            out[i0:i0 + Lk] += k[:len(out[i0:i0 + Lk])]
        else:  # charleston
            Lh = int(0.05 * SR)
            hh = np.random.default_rng(s).standard_normal(Lh) * np.exp(-np.arange(Lh) / SR * 80) * 0.05
            out[i0:i0 + Lh] += hh[:len(out[i0:i0 + Lh])]
    # nappe
    for c in range(int(dur / (beat * 4)) + 1):
        chord = prog[c % 4]; i0 = int(c * beat * 4 * SR); L = int(beat * 4 * SR)
        seg = t[:L]
        pad = sum(np.sin(2 * np.pi * f * seg) for f in chord) * 0.03 * np.minimum(1, seg * 4) * np.minimum(1, (seg[-1] - seg) * 4 + 0.01)
        out[i0:i0 + L] += pad[:len(out[i0:i0 + L])]
    return out


def sfx_tick():
    t = np.arange(int(0.06 * SR)) / SR
    return np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 90) * 0.35


def sfx_ding():
    t = np.arange(int(0.9 * SR)) / SR
    return (np.sin(2 * np.pi * 1318.5 * t) + 0.6 * np.sin(2 * np.pi * 1975.5 * t)) * np.exp(-t * 5) * 0.22


def ease(x):
    x = min(max(x, 0), 1); return 1 - (1 - x) ** 3


def main(qpath, outpath):
    Q = json.load(open(qpath))
    bg = Image.open(os.path.join(FONDS, Q["fond"])).convert("RGBA").resize((W, H))
    tmp = tempfile.mkdtemp()
    # --- voix
    voice = []
    timeline = []  # (start, audio)
    T = 0.1
    cycles = []
    for k, q in enumerate(Q["questions"]):
        qa = tts(q["q"], f"{tmp}/q{k}")
        aa = tts(q["options"][q["bonne"]], f"{tmp}/a{k}")
        extra = max(0.0, len(qa) / SR + 0.2 - 5.6)
        cycles.append(dict(T=T, q=q, extra=extra))
        timeline += [(T + 0.2, qa), (T + 6.3 + extra, aa)]
        T += 9.0 + extra
    E = T
    qb = tts("Question bonus !", f"{tmp}/qbonus")
    timeline.append((E + 0.1, qb))
    ba = tts(Q["bonus"], f"{tmp}/bonus")
    fa = tts(Q["fin"], f"{tmp}/fin")
    bonus_start = E + 1.5
    bonus_end = bonus_start + max(3.0, len(ba) / SR + 0.6)
    fin_start = bonus_end + 1.0
    fin_end = fin_start + max(3.0, len(fa) / SR + 0.6)
    total = fin_end + 1.0
    timeline += [(bonus_start + 0.1, ba), (fin_start + 0.1, fa)]

    # --- audio mix
    n = int(total * SR) + SR
    vtrack = np.zeros(n)
    for st, a in timeline:
        i = int(st * SR); vtrack[i:i + len(a)] += a[:len(vtrack[i:i + len(a)])]
    fx = np.zeros(n)
    for c in cycles:
        for s in range(4):
            tk = sfx_tick(); i = int((c["T"] + 1.2 + s) * SR); fx[i:i + len(tk)] += tk
        dg = sfx_ding(); i = int((c["T"] + 6.1 + c["extra"]) * SR); fx[i:i + len(dg)] += dg[:len(fx[i:i + len(dg)])]
    music = synth_music(n / SR, Q.get("musique", 1))[:n]
    music = np.pad(music, (0, max(0, n - len(music))))  # arrondi flottant : garantir n échantillons
    env = np.abs(vtrack)
    k = int(0.25 * SR)
    duck = np.convolve(env > 0.01, np.ones(k) / k, mode="same")
    music *= 0.32 * (1 - 0.5 * np.clip(duck * 3, 0, 1))
    fade = np.ones(n); fl = int(1.0 * SR); fade[int(total * SR) - fl:int(total * SR)] = np.linspace(1, 0, fl); fade[int(total * SR):] = 0
    mix = (vtrack * 0.95 + fx + music * fade)[:int(total * SR)]
    mix = mix / max(1.0, np.abs(mix).max() / 0.95)
    wav = f"{tmp}/mix.wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())

    # --- éléments graphiques pré-rendus
    for c in cycles:
        q = c["q"]
        c["box"] = card(BOX, q["q"], 28, maxlines=5)
        c["opts"] = [card(r, o, 28, maxlines=2) for r, o in zip(OPTS, q["options"])]
        rf, rt = REVEAL.get(Q["fond"], ((89, 13, 13), (255, 255, 255)))
        c["rev"] = card(REV, q["options"][q["bonne"]], 28, fill=rf, fg=rt)
    sticker = Image.open(os.path.join(KIT, "sticker.png"))
    coul = Q.get("couleur_fin", FOND_COULEUR.get(Q["fond"], "jaune"))
    btxt = outlined_text(Q["bonus"], END, 470, coul)
    ftxt = outlined_text(Q["fin"], END, 470, coul)
    cov = cover(bg, Q["matiere"].upper(), Q["niveau"].upper())
    timers = {}

    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
                             outpath], stdin=subprocess.PIPE)
    nf = int(total * FPS)
    for fi in range(nf):
        t = fi / FPS
        if fi < 3:
            proc.stdin.write(cov.convert("RGB").tobytes()); continue
        fr = bg.copy()

        def put(img, x, y, alpha=1.0, scale=1.0):
            if alpha <= 0: return
            im = img
            if scale != 1.0:
                im = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))))
                x += (img.width - im.width) // 2; y += (img.height - im.height) // 2
            if alpha < 1:
                a = im.getchannel("A").point(lambda v: int(v * alpha)); im = im.copy(); im.putalpha(a)
            fr.alpha_composite(im, (int(x), int(y)))

        for c in cycles:
            lt = t - c["T"]; ex = c["extra"]
            if lt < 0 or lt >= 9.0 + ex: continue
            if lt < 6.1 + ex:
                put(c["box"], BOX[0], BOX[1], ease(lt / 0.45))
                for i, o in enumerate(c["opts"]):
                    put(o, OPTS[i][0], OPTS[i][1], ease((lt - 0.45 - 0.12 * i) / 0.3))
                tt = lt - 1.2
                if 0 <= tt < 4.0:
                    num = 3 - int(tt)
                    frac = 1 - tt / 4.0
                    key = (num, round(frac, 2))
                    if key not in timers: timers[key] = timer_img(num, frac)
                    put(timers[key], TC[0] - 80, TC[1] - 80, ease(tt / 0.2))
                elif 4.0 <= tt < 4.35:
                    p = (tt - 4.0) / 0.35
                    disc = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
                    ImageDraw.Draw(disc).ellipse((10, 10, 150, 150), fill=(150, 175, 190, 255), outline=(60, 80, 95, 255), width=6)
                    put(disc, TC[0] - 80, TC[1] - 80, 1 - p, 0.7 + 0.5 * p)
            else:
                put(c["rev"], REV[0], REV[1], ease((lt - 6.1 - ex) / 0.45))
        if E <= t < E + 1.5:
            p = t - E
            put(sticker, (W - sticker.width) / 2, 325, min(1, p / 0.15) * (1 if p < 1.3 else (1.5 - p) / 0.2), 0.6 + 0.4 * ease(p / 0.25))
        if bonus_start <= t < bonus_end:
            put(btxt, 0, 470 - btxt.height / 2, ease((t - bonus_start) / 0.3))
        if fin_start <= t < fin_end:
            put(ftxt, 0, 500 - ftxt.height / 2, ease((t - fin_start) / 0.3))
        proc.stdin.write(fr.convert("RGB").tobytes())
    proc.stdin.close(); proc.wait()
    print(outpath, round(total, 1), "s")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
