import aiohttp
import asyncio
import aiofiles
import csv
import json
from bs4 import BeautifulSoup
import os
import time
import argparse
from datetime import datetime
import os
import re

# 引数処理
parser = argparse.ArgumentParser(description="LivePocket URL Checker")
parser.add_argument('--csv', type=str, default='index.csv', help='CSVファイル名（例: index_000.csv）')
args = parser.parse_args()
csv_file = args.csv

# 出力フォルダ指定
SAVE_DIR = 'save'
RESULT_DIR = 'Result'
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# CSVファイル名から番号だけ抽出して出力ファイル名に反映
base_name = os.path.basename(csv_file)
match = re.search(r'_(\d{3})\.csv$', base_name)
suffix = match.group(1) if match else 'default'
RESULT_FILE = os.path.join(RESULT_DIR, f'pokemon_livepocket_urls_{suffix}.json')

# 巡回済みURL置き場
ACCESSED_FILE = os.path.join(SAVE_DIR, 'accessed_url.json')

# LivePokectのURL
BASE_URL = 'https://t.livepocket.jp/e/'

# アクセス設定
CONCURRENT_REQUESTS = 10 # タスク数
RATE_LIMIT_PER_SEC = 5 # 通常モードは1秒に"RATE_LIMIT_PER_SEC"件まで
BURST_INTERVAL_SEC = 100000 # バーストモード発動までのインターバル秒数(バーストモードいらなくね？)
BURST_SIZE = 10 # バーストモード時の最大アクセス数

keywords = ['ポケモン', 'ポケモンカード', 'ポケモンカードゲーム', 'ポケカ', 'ブラックボルト', 'ホワイトフレア'] # 監視ワード
block_keywords = ['不正', 'エラー', '制限'] # アクセス制限監視ワード

# ブラウザのふりをしとかないと403でアクセス不可
headers = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    )
}

# ログ出力関数
def log(*args, **kwargs):
    print(*args, **kwargs, flush=True)

class RateLimiter:
    def __init__(self, rate_per_sec, burst_interval_sec, burst_size):
        self._interval = 1.0 / rate_per_sec
        self._last_request_time = time.monotonic()
        self._last_burst_time = 0
        self._burst_interval = burst_interval_sec
        self._burst_size = burst_size
        self._burst_remaining = 0

    async def wait(self):
        now = time.monotonic()
        if now - self._last_burst_time >= self._burst_interval:
            self._last_burst_time = now
            self._burst_remaining = self._burst_size
            # log(f"バーストモード")

        if self._burst_remaining > 0:
            self._burst_remaining -= 1
            return

        wait_time = self._last_request_time + self._interval - now
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        self._last_request_time = time.monotonic()

# 辞書ロード
def load_indexs(csv_file):
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [row['index'] for row in reader]


# Jsonのロード　例えばアクセス済みJson(中断用)
def load_json(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

#Json保存
async def save_json(path, data):
    async with aiofiles.open(path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=2))

# アクセス処理
async def process_index(session, index, results, accessed, limiter, is_waiting):
    await is_waiting.wait()  # 待機中なら全タスクここでブロックされる
    await limiter.wait()
    url = BASE_URL + index
    log(f"アクセス中: ", url)
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                title = soup.title.get_text(strip=True) if soup.title else ''

                # アクセス制限検知
                if any(block_word in title for block_word in block_keywords):
                    is_waiting.clear()
                    log(f"アクセス制限検出: ", url)
                    log(f"5分間待機します...")
                    log("[GUI_WAIT_300]")
                    await asyncio.sleep(300)
                    is_waiting.set()  # 復帰
                    return False  # 処理失敗（accessedに入れない）

                # HITしたURL
                if any(keyword in title for keyword in keywords):
                    results.append({'url': url, 'title': title})
                    log("HIT", title , url)

    except:
        pass  # 通信失敗などは無視

    accessed.add(index)  # 無条件で記録
    return True

# メイン処理
async def main():

    is_waiting = asyncio.Event()
    is_waiting.set()  # 通常時はアクセス許可

    start_time = datetime.now()

    indexs = load_indexs(csv_file)

    accessed = set(load_json(ACCESSED_FILE))
    results = load_json(RESULT_FILE)
    pending = [index for index in indexs if index not in accessed]
    limiter = RateLimiter(RATE_LIMIT_PER_SEC, BURST_INTERVAL_SEC, BURST_SIZE)
    # cancel_event = asyncio.Event()

    log(f"未処理: {len(pending):,} 件を処理開始")

    async with aiohttp.ClientSession() as session:
        async def runner(index):
            success = await process_index(session, index, results, accessed, limiter, is_waiting)
            return (index, success)

        try:
            tasks = [runner(index) for index in pending]
            while pending:
                chunk = [pending.pop(0) for _ in range(min(CONCURRENT_REQUESTS, len(pending)))]
                results_chunk = await asyncio.gather(*[runner(index) for index in chunk])

                retry_indices = [index for index, success in results_chunk if not success]
                if retry_indices:
                    log(f"アクセス制限されたURLをキューの最後尾に追加：{retry_indices}")
                    pending.extend(retry_indices)

                await save_json(ACCESSED_FILE, list(accessed))
                if results:
                    await save_json(RESULT_FILE, results)

        except Exception as e:
            log(f"致命的エラー: {e}")

    log(f"完了!")
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    total_checked = len(accessed)
    total_hits = len(results)

    log(f"\n==============実行統計==============")
    log(f"開始時刻: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"終了時刻: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"処理時間: {duration:.2f} 秒（約 {duration / 60:.1f} 分）")
    # log(f"処理件数: {total_checked:,} 件")
    log(f"HIT件数: {total_hits:,} 件")
    # if duration > 0:
        # log(f"平均処理速度: {total_checked / duration:.2f} 件/秒")


if __name__ == '__main__':
    asyncio.run(main())
