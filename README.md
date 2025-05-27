# 🧪 Pokémon LivePocket URL チェッカー

このツールは、LivePocket のイベントURLを大量にスキャンし、**ポケモン関連イベントを検出**するための非同期・GUI対応の自動チェッカーです。

---

## ✅ 特徴

- 🎛 GUIでCSV選択・実行・進捗表示
- 🚀 aiohttp + レート制限による非同期スキャン（通常接続）
- 🛡 Tor接続モード対応（requests + socks5）
- 🔁 自動切り替えモード搭載（通常↔Torを動的に切替）
- 💤 アクセス制限検出時に自動で待機し再開
- 🧠 中断復帰／再実行／重複アクセス防止に対応
- 📊 実行時間・ステータス・ログをリアルタイム表示

---

## 📁 構成ファイル

| ファイル名 | 説明 |
|------------|------|
| `generate_index.py` | LivePocket用の5文字URL候補を辞書順でCSV出力（分割保存） |
| `indexes_folder/index_XXX.csv` | 生成されたURL候補CSV |
| `Pokemon_LivePocket_URL_Checker.py` | URLスキャン本体（非同期 + Tor切替） |
| `gui.py` | GUIランチャー（Tkinter製） |
| `save/accessed_url.json` | 処理済みURLログ（中断復帰用） |
| `Result/pokemon_livepocket_urls_XXX.json` | HITしたURLとタイトルを記録 |
| `Start.bat` | GUI起動バッチ（cmd起動用） |
| `*.vbs` | コマンド非表示で `.bat` を起動する補助スクリプト（任意） |

---

## 🚀 セットアップ手順

### 1. ライブラリインストール

```bash
pip install aiohttp aiofiles beautifulsoup4 requests pysocks
```

※ Torモードを使用する場合は Tor 本体が必要です。  
`tor/tor.exe` に配置してください。

---

### 2. インデックス生成（初回のみ）

```bash
python generate_index.py
```

> `indexes_folder/` に 5文字組合せのCSV（3万件ごと）を分割保存します。

---

### 3. GUI起動

```bash
python gui.py
```

または `Start.bat` をダブルクリック。  
非表示起動にしたい場合は `.vbs` を利用。

---

## 🖥 GUIの使い方

1. 「参照」でスキャン対象の `index_XXX.csv` を選択
2. 「実行モード」から `通常 / Tor / 自動切替` を選択
3. 「▶ スキャン実行」で処理開始
4. 実行状況・HIT結果がリアルタイムでログ出力されます
5. アクセス制限検出時は一時停止（またはモード自動切替）
6. 「⏹ 停止」でいつでも中断可能

---

## 🔍 HIT判定キーワード

以下のキーワードがイベントタイトルに含まれるURLをHITとします：

- ポケモン
- ポケモンカード
- ポケモンカードゲーム
- ポケカ
- ブラックボルト
- ホワイトフレア

---

## 🔐 アクセス制限ワード（検出すると一時停止またはモード切替）

- 不正
- エラー
- 制限

---

## 📦 出力ファイル

| パス | 内容 |
|------|------|
| `Result/pokemon_livepocket_urls_XXX.json` | 検出イベントの記録 |
| `save/accessed_url.json` | 処理済みURLのログ |

---

## 💡 Tips

- `generate_index.py` の `chunk_size` を変更すればCSV分割数を調整可能
- `--mode auto` で状況に応じて Tor モードに自動切り替え
- Tor モード使用時は `tor/tor.exe` を事前に配置
- GUIでログが止まったら「停止」で手動解除可能
