"""
搜索未明子直播切片/录播视频
"""
import urllib.request
import urllib.parse
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
COOKIE_FILE = PROJECT_ROOT / "cookies.txt"


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


def search_videos(keyword, max_pages=5):
    """搜索视频"""
    videos = []
    seen_bvids = set()
    cookie_str = load_cookies()

    for page in range(1, max_pages + 1):
        params = urllib.parse.urlencode({
            'search_type': 'video',
            'keyword': keyword,
            'order': 'click',
            'page': page,
            'duration': 0,  # 全部时长
        })
        url = f'https://api.bilibili.com/x/web-interface/search/type?{params}'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://search.bilibili.com/',
        }
        if cookie_str:
            headers['Cookie'] = cookie_str

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            print(f"  第{page}页失败: {e}")
            break

        if data.get('code') != 0:
            print(f"  第{page}页错误: {data.get('message')}")
            break

        results = data.get('data', {}).get('result', [])
        if not results:
            break

        for v in results:
            bvid = v.get('bvid', '')
            if bvid in seen_bvids:
                continue
            seen_bvids.add(bvid)

            title = v.get('title', '').replace('<em class="keyword">', '').replace('</em>', '')
            play = v.get('play', 0)
            if isinstance(play, str):
                if '万' in play:
                    try:
                        play = int(float(play.replace('万', '')) * 10000)
                    except:
                        play = 0
                else:
                    try:
                        play = int(play.replace(',', ''))
                    except:
                        play = 0

            videos.append({
                'bvid': bvid,
                'title': title,
                'play': play,
                'author': v.get('author', ''),
                'mid': v.get('mid', ''),
                'duration': v.get('duration', ''),
            })

        num_results = data.get('data', {}).get('numResults', 0)
        if page * 20 >= num_results:
            break
        time.sleep(1)

    return videos


def main():
    keywords = [
        "未明子 直播切片",
        "未明子 直播录播",
        "未明子 直播完整",
        "未明子 录播",
        "未明子 直播",
    ]

    all_videos = {}
    for kw in keywords:
        print(f"\n搜索: {kw}")
        videos = search_videos(kw, max_pages=5)
        print(f"  找到 {len(videos)} 个视频")
        for v in videos:
            if v['bvid'] not in all_videos:
                all_videos[v['bvid']] = v

    # 按播放量排序
    sorted_videos = sorted(all_videos.values(), key=lambda x: x.get('play', 0), reverse=True)

    print(f"\n=== 共找到 {len(sorted_videos)} 个直播相关视频 ===")
    for i, v in enumerate(sorted_videos[:50], 1):
        play = v.get('play', 0)
        play_str = f"{play/10000:.1f}万" if play >= 10000 else str(play)
        print(f"  {i:2d}. [{v['bvid']}] {v['title'][:50]}  ({play_str} | UP: {v['author']})")

    # 保存结果
    out_path = PROJECT_ROOT / "weimingzi-perspective" / "references" / "livestream_clips.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(sorted_videos, f, ensure_ascii=False, indent=2)
    print(f"\n已保存到: {out_path}")

    # 保存BV列表
    bv_path = PROJECT_ROOT / "weimingzi-perspective" / "references" / "livestream_bv_list.txt"
    with open(bv_path, 'w', encoding='utf-8') as f:
        for v in sorted_videos:
            f.write(f"{v['bvid']}\n")
    print(f"BV列表已保存到: {bv_path}")


if __name__ == "__main__":
    main()
