# LivePocket URL チェッカー（並列非同期処理 + モード切替対応）
# モード: normal / tor / auto
# normal: aiohttp 並列非同期（アクセス制限検出時は5分待機）
# tor: requests + PySocks 逐次（アクセス制限検出時は5分待機）
# auto: 状況に応じて normal ↔ tor を自動切り替え（待機なし、切替時にログ表示）

import argparse
import asyncio
import csv
import json
import os
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup
import aiohttp
import aiofiles
import requests
from requests.exceptions import RequestException
import subprocess
import psutil
import random

# ログ出力関数（flush=True により即時反映される）
def log(*args, **kwargs):
    safe_args = []
    for arg in args:
        if isinstance(arg, str):
            safe_args.append(arg.encode('cp932', errors='replace').decode('cp932'))
        else:
            safe_args.append(arg)
    print(*safe_args, **kwargs, flush=True)

# 使用可能プロキシサーバ一覧読み込み関数
def load_proxies(path='available_proxies.txt'):
    with open(path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


# 引数処理（--csv と --mode を受け取る）
parser = argparse.ArgumentParser(description="LivePocket URL Checker")
parser.add_argument('--csv', type=str, default='index.csv', help='CSVファイル名（例: index_000.csv）')
parser.add_argument('--mode', type=str, choices=['normal', 'tor', 'auto'], default='normal', help='実行モード: normal / tor / auto')
args = parser.parse_args()
csv_file = args.csv
mode = args.mode

# 非同期HTTPクライアントの最大同時リクエスト数
CONCURRENT_REQUESTS = 20

# 保存ディレクトリ設定
SAVE_DIR = 'save'  # アクセス済みURLのログ
RESULT_DIR = 'Result'  # HITしたURL情報の保存先
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# 結果ファイル名の構築（ファイル名のサフィックス取得）
base_name = os.path.basename(csv_file)
match = re.search(r'_(\d{3})\.csv$', base_name)
suffix = match.group(1) if match else 'default'
RESULT_FILE = os.path.join(RESULT_DIR, f'pokemon_livepocket_urls_{suffix}.json')
ACCESSED_FILE = os.path.join(SAVE_DIR, 'accessed_url.json')

# チェック対象のURL基本パスとキーワード
BASE_URL = 'https://t.livepocket.jp/e/'
keywords = ['ポケモン', 'ポケモンカード', 'ポケモンカードゲーム', 'ポケカ', 'ブラックボルト', 'ホワイトフレア']
block_keywords = ['不正', 'エラー', '制限']

# HTTPリクエスト用ヘッダー（User-Agent 偽装）
headers = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    )
}

# Tor経由アクセス用のプロキシ設定
TOR_PROXY = {
    'http': 'socks5h://127.0.0.1:9050',
    'https': 'socks5h://127.0.0.1:9050'
}
    
# 通常アクセス用のプロキシ設定
PROXY = load_proxies()

# CSVインデックス読み込み関数
def load_indexs(path):
    # index列をすべて読み込んでリストで返す
    with open(path, 'r', encoding='utf-8') as f:
        return [row['index'] for row in csv.DictReader(f)]

# JSONファイル読み込み関数
def load_json(path):
    # ファイルが存在する場合、JSONデータを読み込んで返す
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

# JSONファイル保存関数（非同期）
async def save_json(path, data):
    # JSONをファイルに保存する
    async with aiofiles.open(path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=2))

# Tor経由で単一URLにアクセスする処理（同期）
def process_tor(index, auto_mode=False, timeout=30):
    url = BASE_URL + index
    log(f"アクセス中 (Tor): {url}")
    try:
        response = requests.get(url, headers=headers, proxies=TOR_PROXY, timeout=timeout)
        if response.status_code == 200:
            # 明示的にUTF-8でデコードして文字化け防止
            html = response.content.decode('utf-8', errors='ignore')
            # タイトル待機ループ（最大60秒）
            soup = BeautifulSoup(html, 'html.parser')
            title = ''
            max_wait = 60
            elapsed = 0
            while not soup.title and elapsed < max_wait:
                time.sleep(1)
                elapsed += 1
                soup = BeautifulSoup(html, 'html.parser')

            if soup.title:
                title = soup.title.get_text(strip=True)
                
            log(f"Tor : アクセス先 {url} \n タイトル : {title}")  # デバッグ用
            # アクセス制限ワードを含むかチェック
            if any(b in title for b in block_keywords):
                log(f"アクセス制限検出: {url}")
                if not auto_mode:
                    log("[GUI_WAIT_300]")
                    time.sleep(300)
                return False, title
            # HITワードが含まれていた場合は成功として返す
            if any(k in title for k in keywords):
                log("HIT", title, url)
                return True, title
    except RequestException as e:
        log(f"[警告] Tor接続エラー: {e}")
    return True, None

# aiohttpで非同期にアクセスする処理
async def process_http(index, session, semaphore, auto_mode):
    url = BASE_URL + index
    async with semaphore:
        log(f"アクセス中 (通常): {url}")
        try:
            # プロキシサーバをランダムで選びそれで大量にアクセスすることによって制限をかかりにくくする
            proxy = random.choice(PROXY)
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30), proxy=f"http://{proxy}") as response:
                if response.status == 200:
                    html = await response.text(errors='ignore')
                    # タイトル待機ループ（最大30秒）
                    soup = BeautifulSoup(html, 'html.parser')
                    title = ''
                    max_wait = 30
                    elapsed = 0
                    while not soup.title and elapsed < max_wait:
                        time.sleep(1)
                        elapsed += 1
                        soup = BeautifulSoup(html, 'html.parser')

                    if soup.title:
                        title = soup.title.get_text(strip=True)
                        
                    log(f"{proxy} : アクセス先 {url} \n タイトル : {title}")  # デバッグ用
                    if any(b in title for b in block_keywords):
                        log(f"アクセス制限検出: {url}")
                        if not auto_mode:
                            log("[GUI_WAIT_300]")
                            await asyncio.sleep(300)
                        return index, False, title
                    if any(k in title for k in keywords):
                        log("HIT", title, url)
                        return index, True, title
        except Exception as e:
            log(f"[警告] {proxy} 通常接続エラー: {e}")
            # 警告が出たproxyは除外
            if proxy in PROXY:
                PROXY.remove(proxy)
                log(f"アドレス : {proxy}を除外しました")
            #警告がでたので仕方がないのでプロキシなしで再度実行
            try:
                log(f"通常接続エラーが出たので、プロキシなしで再試行します")
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        html = await response.text(errors='ignore')
                        # タイトル待機ループ（最大30秒）
                        soup = BeautifulSoup(html, 'html.parser')
                        title = ''
                        max_wait = 30
                        elapsed = 0
                        while not soup.title and elapsed < max_wait:
                            time.sleep(1)
                            elapsed += 1
                            soup = BeautifulSoup(html, 'html.parser')

                        if soup.title:
                            title = soup.title.get_text(strip=True)
                            
                        log(f"再試行アクセス → {url} \n タイトル : {title}")  # デバッグ用
                        if any(b in title for b in block_keywords):
                            log(f"アクセス制限検出: {url}")
                            if not auto_mode:
                                log("[GUI_WAIT_300]")
                                await asyncio.sleep(300)
                            return index, False, title
                        if any(k in title for k in keywords):
                            log("HIT", title, url)
                            return index, True, title
            except Exception as e:
                #ここのエラーもうは知らん
                log(f"もう知らない.....")

    return index, True, None

# メイン関数
async def main():
    # 処理の開始時刻を記録（統計出力用）
    start_time = datetime.now()

    # Torモードの初回起動フラグとプロセス保持
    tor_started = False
    tor_process = None

    # インデックスCSVからURL識別子を取得
    indexs = load_indexs(csv_file)

    # 過去にアクセスしたURL一覧とHIT結果を読み込む
    accessed = set(load_json(ACCESSED_FILE))
    results = load_json(RESULT_FILE)

    # 未アクセスのインデックスのみ抽出
    pending = [idx for idx in indexs if idx not in accessed]

    log(f"未処理: {len(pending):,} 件を処理開始")

    tor_mode = (mode == 'tor')  # Tor専用モードか？
    auto_mode = (mode == 'auto')  # 自動切替モードか？
    use_tor = tor_mode  # 現在の接続モード（初期は引数に従う）
    tor_start_time = None  # Torモードに切り替えた時刻を記録

    try:
        # Torモードの初回時または自動モードの初回時に Tor を起動
        if (tor_mode or auto_mode) and not tor_started:
            tor_exe_path = os.path.join('tor', 'tor', 'tor.exe')
            if os.path.exists(tor_exe_path):
                log("Torプロセスを起動中...")
                tor_process = subprocess.Popen([tor_exe_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                tor_started = True
                time.sleep(20)  # Tor が起動して接続するのを待つ
                log("Torプロセス起動しました！")
            else:
                log("[警告] Tor 実行ファイルが見つかりません: tor/tor/tor.exe")

        if tor_mode:
            for idx in pending:
                success, title = process_tor(idx, auto_mode, timeout=30)
                accessed.add(idx)
                if title and any(k in title for k in keywords):
                    results.append({'url': BASE_URL + idx, 'title': title})
                with open(ACCESSED_FILE, 'w', encoding='utf-8') as f:
                    json.dump(list(accessed), f, ensure_ascii=False, indent=2)
                if results and results:
                    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
                        json.dump(results, f, ensure_ascii=False, indent=2)

        else:
            semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
            async with aiohttp.ClientSession() as session:
                i = 0
                while i < len(pending):
                    chunk = pending[i:i + CONCURRENT_REQUESTS]
                    results_batch = []
                    switch_mode = False  # モード切替のフラグ
                    retry_queue = []  # 再試行対象

                    if auto_mode and use_tor and tor_start_time:
                        if (datetime.now() - tor_start_time).total_seconds() > 300:
                            log("[自動切替] Torモード5分経過 → 通常モードに戻ります")
                            use_tor = False
                            tor_start_time = None

                    if auto_mode and use_tor:
                        for idx in chunk:
                            success, title = process_tor(idx, auto_mode, timeout=30)
                            if title and any(k in title for k in keywords):
                                results.append({'url': BASE_URL + idx, 'title': title})
                            if success:
                                accessed.add(idx)
                            else:
                                retry_queue.append(idx)
                                use_tor = False
                                switch_mode = True
                                tor_start_time = None
                    else:
                        tasks = [process_http(idx, session, semaphore, auto_mode) for idx in chunk]
                        results_batch = await asyncio.gather(*tasks)
                        for idx, success, title in results_batch:
                            if title and any(k in title for k in keywords):
                                results.append({'url': BASE_URL + idx, 'title': title})
                            if success:
                                accessed.add(idx)
                            elif auto_mode:
                                retry_queue.append(idx)
                                use_tor = True
                                tor_start_time = datetime.now()
                                switch_mode = True

                    await save_json(ACCESSED_FILE, list(accessed))
                    if results and results:
                        await save_json(RESULT_FILE, results)

                    if auto_mode and switch_mode and retry_queue:
                        log("切り替え後、再試行を実行中...")
                        for retry_index in retry_queue:
                            if use_tor:
                                success, title = process_tor(retry_index, auto_mode, timeout=30)
                            else:
                                retry_result = await process_http(retry_index, session, semaphore, auto_mode)
                                retry_index, success, title = retry_result
                            if title and any(k in title for k in keywords):
                                results.append({'url': BASE_URL + retry_index, 'title': title})
                            if success:
                                accessed.add(retry_index)
                        await save_json(ACCESSED_FILE, list(accessed))
                        await save_json(RESULT_FILE, results)
                        retry_queue.clear()

                    i += CONCURRENT_REQUESTS

        # 統計出力
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        total_hits = len(results)

        log("\n==============実行統計==============")
        log(f"開始時刻: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        log(f"終了時刻: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        log(f"処理時間: {duration:.2f} 秒（約 {duration / 60:.1f} 分）")
        log(f"HIT件数: {total_hits:,} 件")
        log("完了!")

    finally:
        # プログラム終了時に Tor プロセスをすべて強制終了
        try:
            #log("Torプロセスを終了します")
            for proc in psutil.process_iter(attrs=['pid', 'name']):
                if proc.info['name'] and 'tor.exe' in proc.info['name'].lower():
                    proc.kill()
                    log(f"Torプロセス (PID: {proc.info['pid']}) を強制終了しました")
        except Exception as e:
            log(f"Torプロセス終了エラー: {e}")

# Pythonスクリプトとして直接実行された場合にmain()を呼び出す
if __name__ == '__main__':
    asyncio.run(main())

