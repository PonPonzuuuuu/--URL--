import random
import string
import requests
from bs4 import BeautifulSoup
import json
import time

# 使用する文字セット
chars = string.ascii_lowercase + string.digits + '-_'

# 判定に使うキーワード
keywords = ['ポケモン', 'ポケモンカード', 'ポケモンカードゲーム', 'ポケカ', 'ブラックボルト', 'ホワイトフレア']

# URLプレフィックス
base_url = "https://t.livepocket.jp/e/"

# 結果保存用
results = []

# ブラウザの振りをする
headers = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Referer': 'https://www.google.com/'
}


# ランダムURLを生成・確認する件数
num_checks = 10000  # 必要に応じて変更可

for _ in range(num_checks):
    # ランダムな5文字を生成
    random_code = ''.join(random.choices(chars, k=5))
    full_url = base_url + random_code

    try:
        response = requests.get(full_url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string if soup.title else ''

            # タイトルに指定されたキーワードが含まれているかを確認
            if any(keyword in title for keyword in keywords):
                results.append({
                    'url': full_url,
                    'title': title.strip()
                })
    except requests.RequestException as e:
        # タイムアウトや接続エラーは無視して続行
        print(f"Error accessing {full_url}: {e}")

    # アクセス間隔を開ける（サーバーへの負荷を下げるため）
    #time.sleep(0.5)

# JSONファイルに保存
with open('pokemon_urls.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("完了しました。見つかったURLは以下のとおりです：")
for entry in results:
    print(f"{entry['title']} - {entry['url']}")
