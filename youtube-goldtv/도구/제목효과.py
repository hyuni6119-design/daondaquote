# -*- coding: utf-8 -*-
r"""곡 제목 효과(황금 가루 등장 + 닦아내기 반복)를 캡컷 참고판에서 배워 새 제목에 입힙니다.

참고판: 캡컷에서 검정/흰 바탕으로 내보낸 「내 등을 켜 두겠습니다」 (ref_중_*.npy)
배우는 것
  - 글자가 드러나는 시각  t_rev(x)  (왼쪽 → 오른쪽)
  - 드러난 뒤 글자·빛번짐 세기  A(나이) · K(나이)   (나이 = t − t_rev(x))
  - 황금 가루 알갱이  = 참고판 − 글자 모형  (드러나는 끝을 따라 옮겨 씀)
  - 닦아내기 5초 반복  = 회색 번짐 세기 Kl(t, 가로 비율)
새 제목은 같은 글꼴로 그리고, 위 값을 글자 폭에 맞춰 늘려 입힙니다.

    python 제목효과.py 배우기 --채널 불심명언
    python 제목효과.py 만들기 "귀한 줄 알고 키우겠습니다" 나갈폴더 --채널 불심명언

채널마다 제목 모양이 다릅니다.
  불심명언   흰 글씨 + 검은 테두리, 황금 가루 등장(12.6초) → 닦아내기 5초 반복
  황금주파수 흰 기울임 글씨 + 검은 번짐 그림자, 닦아내기 5초 반복만
"""
import io, json, os, subprocess, sys
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

여기 = os.path.dirname(os.path.abspath(__file__))
글꼴 = "C:/Users/PC/AppData/Local/Microsoft/Windows/Fonts/BMEULJIRO.otf"
가운데 = (1489.0, 798.5)          # 캡컷 transform x 0.55 · y −0.4878
Y0, Y1, X0, X1 = 660, 980, 700, 1920   # 다루는 영역 (참고판의 600~1020 줄 기준)
FPS = 30
반복 = 150                       # 5초 (닦아내기)
채널들 = {
    # 판폴더: 캡컷에서 내보낸 제목판(검정/흰)이 있는 곳 · 참고글: 그 판 25초부터 나오는 제목
    "불심명언": dict(판폴더="D:/불심명언/_효과판", 판="제목판불심", 참고글="내 등을 켜 두겠습니다",
                 글자크기=76, 테두리=6, 굵기=0, 기울임=0.0, 등장=378),      # 황금 가루 12.566초
    "황금주파수": dict(판폴더="D:/골드TV/_효과판", 판="제목판황금", 참고글="같이 건너가자 하시더라",
                  글자크기=76, 테두리=0, 굵기=1, 기울임=0.16, 등장=0),
}
설정 = 채널들["불심명언"]
글자크기, 테두리, 등장, 참고글 = 설정["글자크기"], 설정["테두리"], 설정["등장"], 설정["참고글"]


def 채널맞추기(이름):
    global 설정, 글자크기, 테두리, 등장, 참고글
    설정 = 채널들[이름]
    글자크기, 테두리, 등장, 참고글 = 설정["글자크기"], 설정["테두리"], 설정["등장"], 설정["참고글"]


def 글자판(글):
    """흰 글씨 + 검은 테두리, 알파와 미리곱한 색을 돌려줌 (영역 크기)"""
    f = ImageFont.truetype(글꼴, 글자크기)
    W, H = 1800, 260
    알 = Image.new("L", (W, H), 0)
    ImageDraw.Draw(알).text((W / 2, H / 2), 글, font=f, fill=255, anchor="mm",
                           stroke_width=테두리 + 설정["굵기"], stroke_fill=255)
    흰 = Image.new("L", (W, H), 0)
    ImageDraw.Draw(흰).text((W / 2, H / 2), 글, font=f, fill=255, anchor="mm",
                           stroke_width=설정["굵기"], stroke_fill=255)
    a = np.array(알, np.float32) / 255
    w = np.array(흰, np.float32) / 255
    if 설정["기울임"]:
        sh = 설정["기울임"]
        M = np.float32([[1, -sh, sh * H / 2], [0, 1, 0]])
        a = cv2.warpAffine(a, M, (W, H), flags=cv2.INTER_LINEAR)
        w = cv2.warpAffine(w, M, (W, H), flags=cv2.INTER_LINEAR)
    ys, xs = np.where(a > 0.5)
    bx, by = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    ox, oy = int(round(가운데[0] - X0 - bx)), int(round(가운데[1] - Y0 - by))
    h, wd = Y1 - Y0, X1 - X0
    A = np.zeros((h, wd), np.float32); C = np.zeros((h, wd), np.float32)
    for 판, src in ((A, a), (C, w)):
        y0, x0 = max(0, oy), max(0, ox); y1, x1 = min(h, oy + src.shape[0]), min(wd, ox + src.shape[1])
        판[y0:y1, x0:x1] = src[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
    xs2 = np.where(A.max(0) > 0.5)[0]
    return A, C, (int(xs2.min()), int(xs2.max()))   # C = 흰 부분(미리곱한 밝기, 회색조)


def 번짐(A, s):
    return cv2.GaussianBlur(A, (0, 0), s)


def 바탕들(S, Sw, 반복용=False):
    테 = np.clip(S - Sw, 0, 1)
    b = [Sw, 테, 번짐(S, 3), 번짐(S, 10), 번짐(S, 25)]
    if 반복용:
        return [Sw, 테, 번짐(S, 6)]      # 반복(닦아내기)은 단순하게: 글씨·테두리·회색 번짐
    return b


def 더하기(XtX, XtY, ai, X, Y, NB):
    P = X.shape[1]
    for p in range(P):
        for q in range(p, P):
            w = np.bincount(ai, X[:, p] * X[:, q], NB)
            XtX[:, p, q] += w
            if q != p:
                XtX[:, q, p] += w
        for ch in range(Y.shape[1]):
            XtY[:, p, ch] += np.bincount(ai, X[:, p] * Y[:, ch], NB)


def 풀기(XtX, XtY):
    NB, P, _ = XtX.shape
    out = np.zeros((NB, P, XtY.shape[2]), np.float32)
    have = [b for b in range(NB) if XtX[b].trace() > 1e-3]
    for b in have:
        out[b] = np.linalg.solve(XtX[b] + 1e-4 * np.eye(P), XtY[b])
    # 빈 칸은 가까운 칸 값으로
    for b in range(NB):
        if b not in have and have:
            out[b] = out[min(have, key=lambda x: abs(x - b))]
    return out


def 모형만들기(B, AK, age):
    """age: 기둥마다 (프레임 − 드러난 시각)"""
    ai = np.clip(age + 30, 0, AK.shape[0] - 1).astype(int)
    ak = AK[ai]                                     # (W,P,4)
    m = sum(B[p][..., None] * ak[None, :, p, :] for p in range(len(B)))
    return np.where((age >= -30)[None, :, None], m, 0)


def 배우기():
    def 읽기(f):
        w, h = X1 - X0, Y1 - Y0
        b = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", "25", "-t", str((등장 + 반복) / FPS), "-i",
                            os.path.join(설정["판폴더"], f), "-vf", f"crop={w}:{h}:{X0}:{Y0}", "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        return np.frombuffer(b, np.uint8).reshape(-1, h, w, 3)
    Bk, Wh = 읽기(설정["판"] + "검정.mp4"), 읽기(설정["판"] + "흰.mp4")
    n = min(len(Bk), len(Wh))

    class 판:
        """프레임을 꺼낼 때만 실수로 바꿈 (메모리 아끼기)"""
        def __init__(s, f): s.f = f
        def __getitem__(s, i):
            if isinstance(i, tuple):
                return s.f(i[0])[i[1:]]
            return s.f(i)
    a = 판(lambda i: 1 - (Wh[i].astype(np.float32) - Bk[i]).mean(-1) / 255)
    c = 판(lambda i: Bk[i].astype(np.float32) / 255)
    S, Sw, (lx, rx) = 글자판(참고글)
    core = S > 0.9
    xs = np.arange(S.shape[1])
    near = 번짐((S > 0.05).astype(np.float32), 25) > 0.02
    if 등장:
        # 드러나는 시각: 글자 기둥별로 글자 안 알파가 0.5 를 처음 넘는 순간
        t_rev = np.full(S.shape[1], np.nan, np.float32)
        for x in range(lx, rx + 1):
            m = core[:, x]
            if m.sum() < 3:
                continue
            v = 1 - (Wh[:등장, :, x][:, m].astype(np.float32) - Bk[:등장, :, x][:, m]).mean((1, 2)) / 255
            k = np.where(v > 0.5)[0]
            if len(k):
                t_rev[x] = k[0]
        ok = ~np.isnan(t_rev)
        t_rev = np.interp(xs, xs[ok], t_rev[ok])
        u = np.clip((xs - lx) / (rx - lx), 0, 1)
        곡선 = np.maximum.accumulate(np.interp(np.linspace(0, 1, 101), u[lx:rx + 1], t_rev[lx:rx + 1]))
        # 바탕 그림들: 흰 글씨 · 검은 테두리 · 빛번짐 — 나이(t − t_rev)마다 색 3채널 + 알파 계수
        NB = 등장 + 반복
        B_in = 바탕들(S, Sw)
        P = len(B_in)
        XtX = np.zeros((NB, P, P)); XtY = np.zeros((NB, P, 4))
        Xall = np.stack([b[near] for b in B_in], 1)
        for i in range(등장):
            age = (i - t_rev[None, :]).repeat(S.shape[0], 0)[near]
            ok = (age >= -30) & (age < 등장)
            ai = np.clip(age[ok] + 30, 0, NB - 1).astype(int)
            Y = np.concatenate([c[i][near][ok], a[i][near][ok][:, None]], 1)
            더하기(XtX, XtY, ai, Xall[ok], Y, NB)
        AK = 풀기(XtX, XtY)
        # 알갱이 = 참고판 − 글자 모형 (캡컷·우리 글자 모양 2px 둘레는 비움: 참고 글자가 새 제목에 비치지 않게)
        캡 = np.load(os.path.join(설정["판폴더"], "static_a.npy"))[Y0 - 600:Y1 - 600, X0:X1] > 0.05
        막 = cv2.dilate(((S > 0.05) | 캡).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        알갱이 = np.zeros((등장, S.shape[0], S.shape[1], 4), np.uint8)
        끝 = np.zeros(등장, np.float32)
        for i in range(등장):
            r = np.clip(np.concatenate([c[i], a[i][..., None]], -1) - 모형만들기(B_in, AK, i - t_rev), 0, 1)
            r[막] = 0
            r[..., :3] = np.minimum(r[..., :3], r[..., 3:4] + 0.02)
            알갱이[i] = (r * 255 + 0.5).astype(np.uint8)
            끝[i] = lx + np.interp(i, 곡선, np.linspace(0, 1, 101)) * (rx - lx)
    else:
        곡선 = np.zeros(101, np.float32); AK = np.zeros((1, 1, 4), np.float32)
        알갱이 = np.zeros((0, 1, 1, 4), np.uint8); 끝 = np.zeros(0, np.float32)
    # 닦아내기 5초 반복 (등장 뒤, 등장이 없으면 제목 시작부터)
    # ① 가만히 있는 모양: 흰 글씨(+검은 테두리)는 그대로, 글자 밖 검은 그림자 세기만 맞춤
    #    반복 구간에서 화소마다 가장 옅은 알파 = 지나가는 빛이 없을 때의 모양
    amin = np.min([a[min(등장 + k, n - 1)] for k in range(0, 반복, 3)], axis=0)
    밖 = near & (S < 0.3)
    G = np.stack([b[밖] for b in 그림자바탕(S)], 1)
    정 = np.maximum(np.linalg.lstsq(G, amin[밖] - S[밖], rcond=None)[0], 0).astype(np.float32)
    고정 = 고정모양(S, Sw, 정)
    # ② 지나가는 빛(닦아내기): (프레임, 가로 비율 칸)마다 번짐 세기 — 더하기만
    bins = 24
    g6 = 번짐(S, 6)
    u_ = np.clip((xs - lx) / (rx - lx), 0, 1)
    bidx = np.clip((u_ * bins).astype(int), 0, bins - 1)[None, :].repeat(S.shape[0], 0)[near]
    gn = g6[near]
    Kl = np.zeros((반복, bins, 4), np.float32)
    for k in range(반복):
        i = min(등장 + k, n - 1)
        Y = np.concatenate([c[i][near], a[i][near][:, None]], 1) - 고정[near]
        den = np.bincount(bidx, gn * gn, bins) + 1e-6
        for ch in range(4):
            Kl[k, :, ch] = np.maximum(np.bincount(bidx, gn * Y[:, ch], bins) / den, 0)
    np.savez_compressed(배움파일(), 곡선=곡선, AK=AK, 알갱이=알갱이, 끝=끝, Kl=Kl, 정=정, lx=lx, rx=rx)
    print("그림자 세기", np.round(정, 3))
    print("배움 저장", 배움파일(), "· 드러남", round(float(곡선[0]) / FPS, 2), "~", round(float(곡선[-1]) / FPS, 2), "초")


def 그림자바탕(S):
    return [번짐(S, 4), 번짐(S, 10), 번짐(S, 20)]


def 고정모양(S, Sw, 정):
    """미리곱한 RGBA: 흰 글씨 + 검은 테두리 + 검은 번짐 그림자 (정 = 그림자 세기 3개)"""
    그 = np.clip(sum(k * b for k, b in zip(정, 그림자바탕(S))), 0, 1)
    알 = S + (1 - S) * 그
    return np.concatenate([np.repeat(Sw[..., None], 3, -1), 알[..., None]], -1)


def 배움파일():
    return os.path.join(설정["판폴더"], "제목효과_배움.npz")


def 만들기(글, 나갈):
    os.makedirs(나갈, exist_ok=True)
    z = np.load(배움파일())
    곡선, AK, 알갱이, 끝ref, Kl, 정 = z["곡선"], z["AK"], z["알갱이"], z["끝"], z["Kl"], z["정"]
    S, Sw, (lx, rx) = 글자판(글)
    B_in = 바탕들(S, Sw)
    xs = np.arange(S.shape[1])
    u = np.clip((xs - lx) / max(rx - lx, 1), 0, 1)
    t_rev = np.interp(u, np.linspace(0, 1, 101), 곡선)
    t_rev = np.where(xs < lx, 곡선[0], np.where(xs > rx, 곡선[-1], t_rev))
    h, w = S.shape
    bins = Kl.shape[1]
    bidx = np.clip((u * bins).astype(int), 0, bins - 1)

    def 내보내기(이름, frames):
        p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
                              "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-", "-c:v", "qtrle",
                              os.path.join(나갈, 이름)], stdin=subprocess.PIPE)
        for f in frames:
            p.stdin.write(f.tobytes())
        p.stdin.close(); p.wait()

    def 등장판():
        for i in range(등장):
            m = 모형만들기(B_in, AK, i - t_rev)
            # 알갱이: 참고판의 끝 위치에서 새 제목의 끝 위치로 옮김
            e_new = lx + np.interp(i, 곡선, np.linspace(0, 1, 101)) * (rx - lx)
            dx = int(round(e_new - 끝ref[i]))
            p = np.roll(알갱이[i].astype(np.float32) / 255, dx, axis=1)
            if dx > 0: p[:, :dx] = 0
            elif dx < 0: p[:, dx:] = 0
            out = np.clip(m + p * (1 - np.clip(m[..., 3:4], 0, 1)), 0, 1)
            yield 펴기(out)

    def 반복판():
        고정 = 고정모양(S, Sw, 정)
        g6 = 번짐(S, 6)
        for k in range(반복):
            kl = Kl[k][bidx]                         # (W,4)
            yield 펴기(np.clip(고정 + g6[..., None] * kl[None], 0, 1))

    def 펴기(pm):
        a = np.clip(pm[..., 3:4], 1e-4, 1)
        rgb = np.clip(pm[..., :3] / a, 0, 1)
        return (np.concatenate([rgb, pm[..., 3:4]], -1) * 255 + 0.5).astype(np.uint8)

    if 등장:
        내보내기("등장.mov", 등장판())
    내보내기("반복.mov", 반복판())
    json.dump({"글": 글, "x": X0, "y": Y0, "등장초": 등장 / FPS, "반복초": 반복 / FPS},
              io.open(os.path.join(나갈, "자리.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("[완료]", 글, "→", 나갈)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    인자 = sys.argv[1:]
    채널 = "불심명언"
    if "--채널" in 인자:
        j = 인자.index("--채널"); 채널 = 인자[j + 1]; del 인자[j:j + 2]
    채널맞추기(채널)
    if 인자[0] == "배우기":
        배우기()
    else:
        만들기(인자[1], 인자[2])
