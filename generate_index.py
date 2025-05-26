import itertools
import csv

# 使用する文字セット（明示順）
chars = list('abcdefghijklmnopqrstuvwxyz0123456789-_')

# 出力件数
limit = None  # Noneで全件、100なら最初の100件だけ

# 出力ファイル名
output_csv = 'index.csv'

# 全組み合わせを辞書生成
combinations = itertools.product(chars, repeat=5)

with open(output_csv, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['index'])

    count = 0
    for combo in combinations:
        code = ''.join(combo)
        writer.writerow([code])
        count += 1
        if limit and count >= limit:
            break

print(f"完了。{count:,} 件の文字列を '{output_csv}' に保存済")