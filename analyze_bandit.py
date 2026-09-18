import json
import pandas as pd


# загрузил json
with open('bandit-report.json', 'r', encoding='utf-8') as f:
    report = json.load(f)

df = pd.DataFrame(report['results'])


# очистил ненужное
df_clean = df[[
    'filename', 'line_number', 'test_id', 'test_name',
    'issue_severity', 'issue_confidence', 'issue_text'
]].copy()

df_clean['cwe_id'] = df['issue_cwe'].apply(
    lambda x: x.get('id') if isinstance(x, dict) else None
)
df_clean['filename'] = df_clean['filename'].str.replace('./', '', regex=False)
# print(df_clean)

# перевел в csv и excel формат
df_clean.to_csv('bandit_dataset.csv', index=False, encoding='utf-8-sig')
df_clean.to_excel('bandit_dataset.xlsx', index=False)
print("    CSV и Excel сохранены")

