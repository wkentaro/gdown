import json
from collections import Counter
import os
import sys
import subprocess

def open_file(path):
    if sys.platform == 'win32':
        os.startfile(path)  # Windows
    elif sys.platform == 'darwin':
        subprocess.run(['open', path])  # macOS
    else:
        subprocess.run(['xdg-open', path])  # Linux



with open('bandit-report.json', 'r', encoding='utf-8') as f:
    report = json.load(f)
# print(type(report))

results = report['results']
count_severity = Counter(r['issue_severity'] for r in results)
print(count_severity)
with open('output_bandit_reports.txt', 'w', encoding='utf-8') as f:
    f.write(f'Всего уязвимостей: {len(results)}\nТипы уязвимостей:\n\t'
          f'Высокий риск: {count_severity["HIGH"]}\t'
          f'Средний риск: {count_severity["MEDIUM"]}\t'
          f'Незначительный риск: {count_severity["LOW"]}\n')

    f.write(f'{"="*10}Критичные уязвимости:{"="*10}\n')
    for r in results:
        if r['issue_severity'] == 'HIGH':
            f.write(f"  [{r['test_id']}] {r['filename']}:{r['line_number']}\n")
            f.write(f"    {r['issue_text']}\n")
    f.write("="*40+"\n")

    f.write('='*8+'Экспертное мнение'+'='*8+'\n')
    f.write('Обнаружено 4 уязвимости высокого уровня с тестом B202 в файле ./gdown/extractall.py.\n'
          'Функция tarfile.extractall() используется без параметра filter или с непроверенными members. \n'
          'Это означает, что при распаковке tar-архива имена файлов внутри архива не валидируются.\n'
          'Злоумышленник может создать архив с именами вида ../../etc/passwd,'
          'и при распаковке файл будет записан за пределами целевой директории.\n '
          'Что опасно для пользователя, который использует данную библиотеку\n'
          'Если пользователь запустит gdown с sudo — последствия опасны для системы(запись в /etc, /usr, /root).\n')
    f.write('='*8+'Рекомендации:'+'='*8+'\n')
    f.write('Для python3.12+: Использовать функцию .extracall() c аргументом filter="data"\n'
          'Для старых версий Python: Использовать проверку, что итоговый путь остаётся внутри целевой директории')
open_file("output_bandit_reports.txt")



