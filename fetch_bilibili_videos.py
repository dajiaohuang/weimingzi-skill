"""
获取B站UP主全部视频列表（通过空间 API + WBI 签名）
用法: uv run fetch_bilibili_videos.py <UID> [输出文件]

B站空间API能拿到UP主全部投稿（包括已删除/私密的除外），远比搜索API完整。
"""
import sys
import json
import time
import hashlib
import urllib.request
import urllib.parse
import re
from pathlib import Path
from functools import lru_cache

PROJECT_ROOT = Path(__file__).parent
COOKIE_FILE = PROJECT_ROOT / "cookies.txt"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://space.bilibili.com/',
}

# WBI 混肴密钥的固定索引表（B站官方，2024年起）
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 52, 44, 34,
]


def load_cookies():
    cookie_str = ""
    if COOKIE_FILE.exists():
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    if cookie_str:
                        cookie_str += "; "
                    cookie_str += f"{parts[5]}={parts[6]}"
    return cookie_str


@lru_cache(maxsize=1)
def get_wbi_keys(cookie_str: str) -> tuple[str, str]:
    """获取 WBI 签名的 img_key 和 sub_key"""
    url = "https://api.bilibili.com/x/web-interface/nav"
    headers = {**HEADERS}
    if cookie_str:
        headers['Cookie'] = cookie_str

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"获取 WBI 密钥失败: {e}")
        return "", ""

    wbi_img = data.get('data', {}).get('wbi_img', {})
    img_url = wbi_img.get('img_url', '')
    sub_url = wbi_img.get('sub_url', '')

    # 从 URL 中提取文件名（不含扩展名）
    img_key = Path(img_url).stem if img_url else ""
    sub_key = Path(sub_url).stem if sub_url else ""

    return img_key, sub_key


def get_mixin_key(img_key: str, sub_key: str) -> str:
    """计算最终的混肴密钥"""
    raw = img_key + sub_key
    return ''.join(raw[i] for i in MIXIN_KEY_ENC_TAB if i < len(raw))[:32]


def sign_params(params: dict, cookie_str: str) -> dict:
    """对请求参数进行 WBI 签名"""
    img_key, sub_key = get_wbi_keys(cookie_str)
    if not img_key or not sub_key:
        return params  # 签名失败，裸发（可能被拒）

    mixin_key = get_mixin_key(img_key, sub_key)

    # 添加当前时间戳
    params['wts'] = int(time.time())

    # 按 key 排序
    sorted_params = sorted(params.items(), key=lambda x: x[0])

    # 构建 query string + mixin_key，计算 MD5
    query = urllib.parse.urlencode(sorted_params)
    sign_str = query + mixin_key
    w_rid = hashlib.md5(sign_str.encode()).hexdigest()

    params['w_rid'] = w_rid
    return params


def fetch_all_videos(mid: str, cookie_str: str, page_size: int = 50) -> list[dict]:
    """通过空间 API 获取 UP 主全部视频"""
    videos = []
    seen_bvids = set()
    page = 1
    total_expected = None

    while True:
        params = {
            'mid': mid,
            'ps': page_size,
            'pn': page,
            'order': 'pubdate',
        }
        params = sign_params(params, cookie_str)

        url = f"https://api.bilibili.com/x/space/wbi/arc/search?{urllib.parse.urlencode(params)}"
        headers = {**HEADERS}
        if cookie_str:
            headers['Cookie'] = cookie_str

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            print(f"  第{page}页请求失败: {e}")
            time.sleep(2)
            page += 1
            if page > 10:  # 连续失败太多就停
                break
            continue

        if data.get('code') != 0:
            print(f"  API错误: {data.get('message')} (code={data.get('code')})")
            break

        page_data = data.get('data', {})
        vlist = page_data.get('list', {}).get('vlist', [])

        if total_expected is None:
            total_expected = page_data.get('page', {}).get('count', 0)
            print(f"UP 主全部视频数: {total_expected}")

        if not vlist:
            break

        page_count = 0
        for v in vlist:
            bvid = v.get('bvid', '')
            if bvid in seen_bvids:
                continue
            seen_bvids.add(bvid)

            play = v.get('play', 0)
            if isinstance(play, str):
                try:
                    play = int(play)
                except ValueError:
                    play = 0

            videos.append({
                'bvid': bvid,
                'aid': v.get('aid', ''),
                'title': v.get('title', ''),
                'play': play,
                'duration': v.get('length', ''),
                'author': v.get('author', ''),
                'mid': v.get('mid', ''),
                'description': v.get('description', ''),
                'created': v.get('created', ''),
                'comment': v.get('comment', 0),
            })
            page_count += 1

        print(f"  第{page}页: {page_count} 个 (累计 {len(videos)} / {total_expected})")

        # 判断是否还有下一页
        if len(vlist) < page_size:
            break

        page += 1
        time.sleep(0.5)  # 控制频率

    return videos


def main():
    if len(sys.argv) < 2:
        print("用法: fetch_bilibili_videos.py <UID> [输出文件]")
        print("示例: fetch_bilibili_videos.py 23191782")
        print("示例: fetch_bilibili_videos.py 23191782 video_list_full.json")
        sys.exit(1)

    mid = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "video_list_full.json"

    print(f"正在通过空间 API 获取 UP 主 (UID: {mid}) 的全部视频...")
    cookie_str = load_cookies()
    print(f"Cookies: {'已加载' if cookie_str else '未找到'}")

    videos = fetch_all_videos(mid, cookie_str)

    print(f"\n共获取到 {len(videos)} 个视频")

    # 按播放量排序
    videos_sorted = sorted(videos, key=lambda x: x.get('play', 0), reverse=True)

    # 保存为 JSON
    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(videos_sorted, f, ensure_ascii=False, indent=2)

    print(f"已保存到: {out_path}")

    # 打印 TOP 30
    print("\n=== 播放量 TOP 30 ===")
    for i, v in enumerate(videos_sorted[:30], 1):
        play = v.get('play', 0)
        play_str = f"{play/10000:.1f}万" if play >= 10000 else str(play)
        print(f"  {i:2d}. [{v['bvid']}] {v['title'][:45]}  ({play_str}播放)")


if __name__ == "__main__":
    main()
