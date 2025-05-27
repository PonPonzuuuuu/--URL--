import asyncio
import aiohttp
from aiohttp import ClientTimeout
import time
import os

SERVERLIST_FILE = "serverlist.txt"
AVAILABLE_FILE = "available_proxies.txt"
TEST_URL = "https://t.livepocket.jp/"
TIMEOUT = 20

available = []
unavailable = []

# ファイルからプロキシ読み込み
def load_proxies(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

# プロキシを非同期で検査
async def check_proxy(session, proxy):
    proxy_url = f"http://{proxy}"
    try:
        async with session.get(TEST_URL, proxy=proxy_url, timeout=ClientTimeout(total=TIMEOUT)) as response:
            if response.status == 200:
                print(f"[OK]    {proxy}")
                available.append(proxy)
            else:
                print(f"[NG]    {proxy} - status {response.status}")
                unavailable.append(proxy)
    except Exception as e:
        print(f"[FAIL]  {proxy} - {e}")
        unavailable.append(proxy)

# メイン処理
async def main():
    # serverlist.txt + available_proxies.txt を統合し重複除去
    serverlist_proxies = load_proxies(SERVERLIST_FILE)
    existing_proxies = load_proxies(AVAILABLE_FILE)
    combined = sorted(set(serverlist_proxies + existing_proxies))

    print(f"チェック対象: {len(combined)} 件")
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_proxy(session, proxy) for proxy in combined]
        await asyncio.gather(*tasks)

    # 結果保存（重複除去・ソートして保存）
    merged = sorted(set(available))
    with open(AVAILABLE_FILE, "w", encoding="utf-8") as f:
        for proxy in merged:
            f.write(proxy + "\n")

    print(f"\n✅ 完了！使用可能: {len(available)}, 使用不可: {len(unavailable)}")
    print(f"📄 保存済み: {AVAILABLE_FILE}（合計 {len(merged)} 件）")

if __name__ == "__main__":
    start = time.time()
    asyncio.run(main())
    print(f"🕒 処理時間: {time.time() - start:.2f} 秒")
