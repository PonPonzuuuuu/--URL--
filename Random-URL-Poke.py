import aiohttp
import asyncio
import aiofiles
import csv
import json
from bs4 import BeautifulSoup
import os
import time

CSV_FILE = 'index.csv'
RESULT_FILE = 'pokemon_livepocket_urls.json'
ACCESSED_FILE = 'accessed_url.json'
BASE_URL = 'https://t.livepocket.jp/e/'

CONCURRENT_REQUESTS = 10 # タスク数
RATE_LIMIT_PER_SEC = 5 # 通常モードは1秒に"RATE_LIMIT_PER_SEC"件まで
BURST_INTERVAL_SEC = 300 # バーストモード発動までのインターバル秒数
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
            print(f"バーストモード")

        if self._burst_remaining > 0:
            self._burst_remaining -= 1
            return

        wait_time = self._last_request_time + self._interval - now
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        self._last_request_time = time.monotonic()
# 辞書ロード
def load_indexs():
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
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
async def process_index(session, index, results, accessed, limiter):
    await limiter.wait()
    url = BASE_URL + index
    print(f"アクセス中: {url}")
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                title = soup.title.get_text(strip=True) if soup.title else ''

                # アクセス制限チェック
                if any(block_word in title for block_word in block_keywords):
                    print("アクセス制限されました")
                    await save_json(ACCESSED_FILE, list(accessed))
                    await save_json(RESULT_FILE, results)
                    raise asyncio.CancelledError()

                if any(keyword in title for keyword in keywords):
                    results.append({'url': url, 'title': title})
                    print(f"HIT - {title} - {url}")
    except:
        pass
    accessed.add(index)

# メイン処理
async def main():
    indexs = load_indexs()
    accessed = set(load_json(ACCESSED_FILE))
    results = load_json(RESULT_FILE)
    pending = [index for index in indexs if index not in accessed]
    limiter = RateLimiter(RATE_LIMIT_PER_SEC, BURST_INTERVAL_SEC, BURST_SIZE)

    print(f"未処理: {len(pending):,} 件を処理開始")

    try:
        async with aiohttp.ClientSession() as session:
            async def runner(index):
                await process_index(session, index, results, accessed, limiter)

            tasks = [runner(index) for index in pending]
            for i in range(0, len(tasks), CONCURRENT_REQUESTS):
                await asyncio.gather(*tasks[i:i + CONCURRENT_REQUESTS])
                await save_json(ACCESSED_FILE, list(accessed))
                await save_json(RESULT_FILE, results)

    except asyncio.CancelledError:
        print("アクセス制限なので処理を中断")

    print("完了!")

if __name__ == '__main__':
    asyncio.run(main())
