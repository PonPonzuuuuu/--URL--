# LivePocket URL チェッカー（非同期・レート制限・バースト対応）

このスクリプトは、指定された LivePocket の URL インデックスリスト（`index.csv`）をもとに、  
該当イベントページに特定のキーワード（例：ポケモン関連）が含まれているかをチェックします。

- Python の非同期機能 `asyncio` + `aiohttp` を使用
- サーバー負荷を避けるために **レート制限（1秒5件）** を実装
- **5分ごとにバーストモード**（最大10件即送信）を許可
- アクセス制限っぽいページ（例：不正、エラー、制限）が検出されたら **即座に中断＆保存**
- 処理済みとヒット結果は JSON に保存され、**中断後も再開可能**

---

## ファイル構成

| ファイル名                      | 説明                                       |
|---------------------------------|--------------------------------------------|
| `index.csv`                     | チェック対象のコードリスト（例：`abc12`）  |
| `pokemon_livepocket_urls.json`  | HIT（キーワード一致）したURLとタイトル一覧 |
| `accessed_url.json`             | 処理済みのコード一覧（中断復帰用）         |
| `main.py`（このスクリプト）     | メインロジック                             |

---

## 実行方法

1. 必要なライブラリをインストール

```bash
pip install aiohttp aiofiles beautifulsoup4

2. index.csv の準備
generate_index.pyを実行または
https://drive.google.com/file/d/1LwdYIVn2h4y02Ebz3KfwvqYia8y8UI75/view?usp=sharing
から辞書をダウンロードし、Random-URL-Poke.pyと同じファイル階層に配置

階層
|
|-- Random-URL-Poke.py
|-- index.csv
|-- generate_index.py

3. スクリプトを実行
python main.py