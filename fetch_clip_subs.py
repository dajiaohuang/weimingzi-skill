"""
从任意B站视频获取AI字幕（通过player API + WBI签名），适用于切片号等非主账号内容。
用法: uv run fetch_clip_subs.py <BV或BV列表文件>
      uv run fetch_clip_subs.py --mid <UID>  获取某UP主全部视频的字幕
"""
import sys, json, time, hashlib, urllib.request, urllib.parse, re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
TEXT_DIR = PROJECT_ROOT / "raw" / "texts"
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

def fetch_sub_for_bv(bv, cookie_str, mixin_key, headers):
    """获取单个视频的AI字幕文本"""
    # Get video info + cid
    view_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv}"
    req = urllib.request.Request(view_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            view_data = json.loads(resp.read().decode('utf-8'))
    except:
        return None, "view_fail"

    if view_data.get('code') != 0:
        return None, f"api_error:{view_data.get('message')}"

    vdata = view_data['data']
    cid = vdata.get('cid', 0)
    title = vdata.get('title', bv)
    owner = vdata.get('owner', {}).get('name', '?')

    # Player API for subtitles
    params = sign_params({'bvid': bv, 'cid': cid, 'fnval': 4048}, mixin_key)
    player_url = f"https://api.bilibili.com/x/player/wbi/v2?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(player_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            player_data = json.loads(resp.read().decode('utf-8'))
    except:
        return None, "player_fail"

    sub_list = player_data.get('data', {}).get('subtitle', {}).get('subtitles', [])
    if not sub_list:
        return None, "no_subtitle"

    # Download first Chinese subtitle
    for s in sub_list:
        sub_url = s.get('subtitle_url', '')
        if not sub_url:
            continue
        if sub_url.startswith('//'):
            sub_url = 'https:' + sub_url

        try:
            req = urllib.request.Request(sub_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = json.loads(resp.read().decode('utf-8'))
        except:
            continue

        texts = [item.get('content', '') for item in content.get('body', [])]
        text = '\n'.join(t for t in texts if t)
        if text:
            return (text, title, owner), "ok"

    return None, "empty_sub"


def get_all_bvs_for_mid(mid, cookie_str, mixin_key, headers):
    """获取某UP主全部视频BV列表"""
    all_bvs = []
    for page in range(1, 20):
        params = sign_params({'mid': mid, 'ps': 50, 'pn': page, 'order': 'pubdate'}, mixin_key)
        url = f"https://api.bilibili.com/x/space/wbi/arc/search?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        vlist = data.get('data', {}).get('list', {}).get('vlist', [])
        if not vlist:
            break
        all_bvs.extend(v['bvid'] for v in vlist)
        time.sleep(0.3)
    return all_bvs


def main():
    cookie_str = load_cookies()
    mixin_key = get_mixin_key(cookie_str)
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bilibili.com/', 'Cookie': cookie_str}
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    bvs_to_process = []

    if len(sys.argv) >= 2:
        if sys.argv[1] == '--mid':
            mid = sys.argv[2]
            print(f"获取 UP {mid} 的全部视频...")
            bvs_to_process = get_all_bvs_for_mid(mid, cookie_str, mixin_key, headers)
            print(f"共 {len(bvs_to_process)} 个视频")
        elif sys.argv[1].endswith('.txt'):
            bvs_to_process = [l.strip() for l in Path(sys.argv[1]).read_text().strip().split('\n') if l.strip()]
            print(f"从文件加载 {len(bvs_to_process)} 个 BV")
        else:
            bvs_to_process = [sys.argv[1]]
    else:
        print("用法: fetch_clip_subs.py <BV> | --mid <UID> | <bv_list.txt>")
        return

    # Check existing
    existing = set()
    for f in TEXT_DIR.glob("*.txt"):
        m = re.match(r'(BV[0-9a-zA-Z]+)', f.name)
        if m:
            existing.add(m.group(1))

    new = [bv for bv in bvs_to_process if bv not in existing]
    print(f"已有: {len(bvs_to_process) - len(new)}, 需下载: {len(new)}")

    ok = skip = fail = 0
    for i, bv in enumerate(new):
        result, status = fetch_sub_for_bv(bv, cookie_str, mixin_key, headers)

        if status == "ok":
            text, title, owner = result
            safe_title = re.sub(r'[\\/:*?"<>|]', '', title)[:60]
            txt_path = TEXT_DIR / f"{bv}_{safe_title}.txt"
            txt_path.write_text(text, encoding='utf-8')
            ok += 1
            print(f"[{i+1}/{len(new)}] {bv}: OK ({len(text)}字) - {owner}")
        elif status == "no_subtitle":
            skip += 1
            print(f"[{i+1}/{len(new)}] {bv}: 无字幕")
        else:
            fail += 1
            print(f"[{i+1}/{len(new)}] {bv}: {status}")

        time.sleep(0.3)

    print(f"\n完成: OK={ok}, 无字幕={skip}, 失败={fail}")


if __name__ == "__main__":
    main()
