"""
获取B站UP主视频列表（通过搜索API）
用法: uv run fetch_bilibili_videos.py <UID> <UP主名称> [输出文件]
"""
import sys
import json
import time
import urllib.request
import urllib.parse
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


def _fetch_page(keyword, mid, page, order, cookie_str, seen_bvids, videos):
    """获取单页搜索结果"""
    params = urllib.parse.urlencode({
        'search_type': 'video',
        'keyword': keyword,
        'order': order,
        'page': page,
    })
    url = f'https://api.bilibili.com/x/web-interface/search/type?{params}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://search.bilibili.com/',
    }
    if cookie_str:
        headers['Cookie'] = cookie_str

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"  获取失败: {e}")
        return False, 0, 0

    if data.get('code') != 0:
        print(f"  API错误: {data.get('message')}")
        return False, 0, 0

    results = data.get('data', {}).get('result', [])
    page_count = 0
    for v in results:
        bvid = v.get('bvid', '')
        if str(v.get('mid', '')) != str(mid):
            continue
        if bvid in seen_bvids:
            continue
        seen_bvids.add(bvid)

        title = v.get('title', '').replace('<em class="keyword">', '').replace('</em>', '')
        play = v.get('play', 0)
        if isinstance(play, str):
            play_str = play
            if '万' in play_str:
                try:
                    play = int(float(play_str.replace('万', '')) * 10000)
                except:
                    play = 0
            else:
                try:
                    play = int(play_str.replace(',', ''))
                except:
                    play = 0

        videos.append({
            'bvid': bvid,
            'aid': v.get('aid', ''),
            'title': title,
            'play': play,
            'duration': v.get('duration', ''),
            'author': v.get('author', ''),
            'mid': v.get('mid', ''),
            'description': v.get('description', ''),
        })
        page_count += 1

    num_results = data.get('data', {}).get('numResults', 0)
    has_more = page * 20 < num_results and len(results) > 0
    return has_more, page_count, num_results


def fetch_videos_by_search(keyword, mid, max_pages=50):
    """通过搜索API获取UP主的视频，使用多种排序方式提高覆盖率"""
    videos = []
    seen_bvids = set()
    cookie_str = load_cookies()

    # 按播放量排序（获取热门视频）
    print("按播放量排序获取中...")
    for page in range(1, max_pages + 1):
        has_more, page_count, _ = _fetch_page(keyword, mid, page, 'click', cookie_str, seen_bvids, videos)
        print(f"  第{page}页: 新增 {page_count} 个 (累计 {len(videos)})")
        if not has_more or page_count == 0 and page > 5:
            break
        time.sleep(1)

    # 按发布时间排序（获取更多视频）
    print(f"\n按发布时间排序获取中... (当前已有 {len(videos)} 个)")
    for page in range(1, max_pages + 1):
        has_more, page_count, _ = _fetch_page(keyword, mid, page, 'pubdate', cookie_str, seen_bvids, videos)
        print(f"  第{page}页: 新增 {page_count} 个 (累计 {len(videos)})")
        if not has_more or page_count == 0 and page > 5:
            break
        time.sleep(1)

    return videos


def main():
    if len(sys.argv) < 3:
        print("用法: fetch_bilibili_videos.py <UID> <UP主名称> [输出文件]")
        print("示例: fetch_bilibili_videos.py 588138582 未明子 video_list_full.json")
        sys.exit(1)

    mid = sys.argv[1]
    keyword = sys.argv[2]
    output_file = sys.argv[3] if len(sys.argv) > 3 else "video_list_full.json"

    print(f"正在通过搜索获取 UP 主「{keyword}」(UID: {mid}) 的视频列表...")
    videos = fetch_videos_by_search(keyword, mid)

    print(f"\n共获取到 {len(videos)} 个视频")

    # 按播放量排序
    videos_sorted = sorted(videos, key=lambda x: x.get('play', 0), reverse=True)

    # 保存为 JSON
    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(videos_sorted, f, ensure_ascii=False, indent=2)

    print(f"已保存到: {out_path}")

    # 打印前30个最高播放量的视频
    print("\n=== 播放量 TOP 30 ===")
    for i, v in enumerate(videos_sorted[:30], 1):
        play = v.get('play', 0)
        play_str = f"{play/10000:.1f}万" if play >= 10000 else str(play)
        print(f"  {i:2d}. [{v['bvid']}] {v['title'][:45]}  ({play_str}播放)")


if __name__ == "__main__":
    main()
