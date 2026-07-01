"""
两阶段：1) Player API 快扫 AI 字幕  2) 剩余跑 Whisper
断点续传：已有 text 的 BV 自动跳过
"""
import json, time, hashlib, urllib.request, urllib.parse, re, subprocess, sys, os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
TEXT_DIR = PROJECT_ROOT / "raw" / "texts"
AUDIO_DIR = PROJECT_ROOT / "audio"
COOKIE_FILE = PROJECT_ROOT / "cookies.txt"

MIXIN_KEY_ENC_TAB = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,52,44,34]

def load_cookies():
    cookie_str = ""
    if COOKIE_FILE.exists():
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    if cookie_str: cookie_str += "; "
                    cookie_str += f"{parts[5]}={parts[6]}"
    return cookie_str

def get_mixin_key(cookie_str):
    url = "https://api.bilibili.com/x/web-interface/nav"
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bilibili.com/', 'Cookie': cookie_str}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    wbi_img = data.get('data', {}).get('wbi_img', {})
    img_key = Path(wbi_img.get('img_url', '')).stem
    sub_key = Path(wbi_img.get('sub_url', '')).stem
    raw_key = img_key + sub_key
    return ''.join(raw_key[i] for i in MIXIN_KEY_ENC_TAB if i < len(raw_key))[:32]

def sign_params(params, mixin_key):
    params['wts'] = int(time.time())
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    query = urllib.parse.urlencode(sorted_params)
    w_rid = hashlib.md5((query + mixin_key).encode()).hexdigest()
    params['w_rid'] = w_rid
    return params

def save_text(bv, title, text):
    safe_title = re.sub(r'[\\/:*?"<>|]', '', title)[:60]
    txt_path = TEXT_DIR / f"{bv}_{safe_title}.txt"
    txt_path.write_text(text, encoding='utf-8')
    return txt_path

def download_audio(bv):
    """Download audio, return audio file path or None"""
    url = f"https://www.bilibili.com/video/{bv}"
    cmd = [sys.executable, "-m", "yt_dlp", "-x", "--audio-format", "mp3", "--audio-quality", "0",
           url, "--cookies", str(COOKIE_FILE), "-o", str(AUDIO_DIR / "%(id)s.%(ext)s"),
           "--no-playlist", "--socket-timeout", "30"]
    subprocess.run(cmd, capture_output=True, timeout=120, encoding='utf-8', errors='replace')
    for ext in ['.m4a', '.mp3', '.webm', '.opus']:
        p = AUDIO_DIR / f"{bv}{ext}"
        if p.exists():
            return str(p)
    return None


def main():
    cookie_str = load_cookies()
    mixin_key = get_mixin_key(cookie_str)
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bilibili.com/', 'Cookie': cookie_str}
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # Load BV lists
    all_bvs = []
    for fname in ["missing_main.txt", "missing_clip.txt"]:
        fpath = PROJECT_ROOT / "references" / fname
        if fpath.exists():
            all_bvs.extend(l.strip() for l in fpath.read_text().strip().split('\n') if l.strip())

    # Filter already-done
    existing = set()
    for f in TEXT_DIR.glob("*.txt"):
        m = re.match(r'(BV[0-9a-zA-Z]+)', f.name)
        if m: existing.add(m.group(1))
    todo = [bv for bv in all_bvs if bv not in existing]

    print(f"待处理: {len(todo)}\n")

    # ======== Phase 1: Player API (fast) ========
    print("=" * 50)
    print("Phase 1: Player API 抓 AI 字幕")
    print("=" * 50)
    need_whisper = []
    api_ok = 0
    for i, bv in enumerate(todo):
        print(f"\r[{i+1}/{len(todo)}] {bv}: ", end='', flush=True)

        # Player API
        view_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv}"
        try:
            req = urllib.request.Request(view_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                view_data = json.loads(resp.read().decode('utf-8'))
        except:
            need_whisper.append(bv)
            print("view_fail", end='')
            time.sleep(0.2)
            continue

        if view_data.get('code') != 0:
            need_whisper.append(bv)
            print(f"api_err", end='')
            time.sleep(0.2)
            continue

        vdata = view_data['data']
        cid = vdata.get('cid', 0)
        title = vdata.get('title', bv)

        params = sign_params({'bvid': bv, 'cid': cid, 'fnval': 4048}, mixin_key)
        player_url = f"https://api.bilibili.com/x/player/wbi/v2?{urllib.parse.urlencode(params)}"
        try:
            req = urllib.request.Request(player_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                player_data = json.loads(resp.read().decode('utf-8'))
        except:
            need_whisper.append(bv)
            print("player_fail", end='')
            time.sleep(0.2)
            continue

        sub_list = player_data.get('data', {}).get('subtitle', {}).get('subtitles', [])
        if not sub_list:
            need_whisper.append(bv)
            print("no_sub", end='')
            time.sleep(0.2)
            continue

        # Download subtitle
        got_text = False
        for s in sub_list:
            sub_url = s.get('subtitle_url', '')
            if not sub_url: continue
            if sub_url.startswith('//'): sub_url = 'https:' + sub_url
            try:
                req = urllib.request.Request(sub_url, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    content = json.loads(resp.read().decode('utf-8'))
                texts = [item.get('content', '') for item in content.get('body', [])]
                text = '\n'.join(t for t in texts if t)
                if text:
                    save_text(bv, title, text)
                    api_ok += 1
                    got_text = True
                    print(f"OK({len(text)}字)", end='')
                    break
            except:
                continue

        if not got_text:
            need_whisper.append(bv)
            print("empty", end='')

        time.sleep(0.2)

    print(f"\n\nPhase 1 done: AI字幕={api_ok}, 需Whisper={len(need_whisper)}\n")

    if not need_whisper:
        print("全部完成！")
        return

    # ======== Phase 2: Whisper (slow, GPU) ========
    print("=" * 50)
    print(f"Phase 2: Whisper 转写 ({len(need_whisper)} 个)")
    print("=" * 50)

    # Load model ONCE
    os.add_dll_directory(str(PROJECT_ROOT / ".venv" / "Lib" / "site-packages" / "nvidia" / "cublas" / "bin"))
    from faster_whisper import WhisperModel
    model_path = str(PROJECT_ROOT / "models" / "faster-whisper-medium")
    print("Loading Whisper model...")
    model = WhisperModel(model_path, device='cuda', compute_type='int8')
    print("Model loaded.\n")

    whisper_ok = fail = 0
    for i, bv in enumerate(need_whisper):
        print(f"[{i+1}/{len(need_whisper)}] {bv}: ", end='', flush=True)

        # Download audio
        audio_path = download_audio(bv)
        if not audio_path:
            fail += 1
            print("download_fail")
            continue

        # Transcribe
        try:
            segments, info = model.transcribe(audio_path, language='zh', vad_filter=True, beam_size=5)
            texts = [seg.text.strip() for seg in segments if seg.text.strip()]
            text = '\n'.join(texts)

            # Get title
            view_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv}"
            req = urllib.request.Request(view_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                view_data = json.loads(resp.read().decode('utf-8'))
            title = view_data.get('data', {}).get('title', bv)

            save_text(bv, title, text)
            whisper_ok += 1
            print(f"OK({len(text)}字)")
        except Exception as e:
            fail += 1
            print(f"err:{e}")

        # Cleanup audio to save disk
        try:
            os.remove(audio_path)
        except:
            pass

        # Progress
        if (i+1) % 10 == 0:
            print(f"  --- Whisper:{whisper_ok} 失败:{fail} ---")

    print(f"\n全部完成! Whisper:{whisper_ok} 失败:{fail}")


if __name__ == "__main__":
    main()
