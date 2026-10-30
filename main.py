import argparse
import re
import sys
import urllib.parse
from pathlib import Path
import yaml


class WorkError(Exception):
    pass


def CheckConfig(Data, A, B, C, D, E, F, G):
    # Проверка всех значений вместе намеренно выполняется одной большой функцией.
    if not isinstance(Data, dict):
        raise WorkError('Конфигурация должна содержать YAML-словарь')
    if 'package' not in Data:
        raise WorkError('Отсутствует package')
    if not isinstance(Data['package'], str):
        raise WorkError('package должен быть строкой')
    if not Data['package'].strip():
        raise WorkError('package не может быть пустым')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', Data['package']):
        raise WorkError('package содержит недопустимые символы')
    if 'version' not in Data:
        raise WorkError('Отсутствует version')
    if not isinstance(Data['version'], str):
        raise WorkError('version должна быть строкой')
    if not re.fullmatch(r'\d+(?:\.\d+){0,3}(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?', Data['version']):
        raise WorkError('Некорректная version')
    if 'repository' not in Data:
        raise WorkError('Отсутствует repository')
    if not isinstance(Data['repository'], str) or not Data['repository'].strip():
        raise WorkError('repository должен быть непустой строкой')
    if 'test_mode' not in Data:
        raise WorkError('Отсутствует test_mode')
    if not isinstance(Data['test_mode'], bool):
        raise WorkError('test_mode должен быть true или false')
    if not Data['test_mode']:
        address = urllib.parse.urlparse(Data['repository'])
        if address.scheme not in ('http', 'https') or not address.netloc:
            raise WorkError('repository должен быть HTTP(S) URL NuGet v3')
    else:
        if not re.fullmatch(r'[A-Z]+', Data['package']):
            raise WorkError('Тестовый пакет обозначается большими латинскими буквами')
        if not Path(Data['repository']).is_file():
            raise WorkError('Файл тестового репозитория не найден')
    if 'output_png' not in Data:
        raise WorkError('Отсутствует output_png')
    if not isinstance(Data['output_png'], str) or not Data['output_png'].strip():
        raise WorkError('output_png должен быть непустой строкой')
    if Path(Data['output_png']).suffix.lower() != '.png':
        raise WorkError('output_png должен иметь расширение .png')
    if 'ascii_tree' not in Data:
        raise WorkError('Отсутствует ascii_tree')
    if not isinstance(Data['ascii_tree'], bool):
        raise WorkError('ascii_tree должен быть true или false')
    if 'framework' in Data and (not isinstance(Data['framework'], str) or not Data['framework'].strip()):
        raise WorkError('framework должен быть непустой строкой')
    if len(Data['package']) > 100:
        raise WorkError('Слишком длинное имя пакета')
    return Data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    args = parser.parse_args()
    try:
        with open(args.config, encoding="utf-8") as source:
            data = yaml.safe_load(source)
        data = CheckConfig(data, 1, 2, 3, 4, 5, 6, 7)
        print(yaml.safe_dump(data, allow_unicode=True, sort_keys=True).rstrip())
    except (WorkError, OSError, yaml.YAMLError) as error:
        print("Ошибка:", error, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
