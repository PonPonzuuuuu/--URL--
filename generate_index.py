import itertools
import csv
import os

# 使用する文字セット
chars = list('abcdefghijklmnopqrstuvwxyz0123456789-_')

# 出力制限（None = 全件）
limit = None

# 出力先フォルダ（なければ作成）
output_dir = 'indexes_folder'
os.makedirs(output_dir, exist_ok=True)

# 1ファイルに書き込む件数
chunk_size = 100000

# 全組み合わせを辞書順で生成
combinations = itertools.product(chars, repeat=5)

file_index = 0
row_count = 0
total_count = 0

writer = None
f = None

try:
    for combo in combinations:
        if row_count == 0:
            if f:
                f.close()
            filename = os.path.join(output_dir, f'index_{file_index:03d}.csv')
            f = open(filename, 'w', newline='', encoding='utf-8')
            writer = csv.writer(f)
            writer.writerow(['index'])  # ヘッダー
            print(f'新規ファイル: {filename}')

        code = ''.join(combo)
        writer.writerow([code])
        row_count += 1
        total_count += 1

        if row_count >= chunk_size:
            row_count = 0
            file_index += 1

        if limit and total_count >= limit:
            break

finally:
    if f:
        f.close()

print(f"完了: {total_count:,} 件を {file_index + 1} ファイルに分割して '{output_dir}/' に保存しました。")

