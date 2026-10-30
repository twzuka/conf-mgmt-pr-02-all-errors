#!/usr/bin/env python3
# Практическая работа: все модули общаются по JSON, программа запускается из этой папки.
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import deque
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


def invoke(name, payload):
    # Каждая команда принимает один JSON из stdin и возвращает один JSON в stdout.
    env_name = 'COMPONENT_' + name.upper()
    defaults = {
        'csharp': 'dotnet bin/Release/net8.0/Resolver.dll',
        'go': './graph_validator',
        'rust': './target/release/graph_analyzer',
        'kotlin': 'java -cp picture.jar:. PictureKt',
        'javascript': 'node render_graph.js',
        'java': 'java -cp . ascii_bad',
    }
    command = shlex.split(os.environ.get(env_name, defaults[name]))
    try:
        p = subprocess.run(command, input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True, check=False, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as ex:
        raise WorkError(f'Не удалось запустить компонент {name}: {ex}') from ex
    if p.returncode != 0:
        raise WorkError(f'Компонент {name} завершился с ошибкой: {p.stderr.strip()}')
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError as ex:
        raise WorkError(f'Компонент {name} вернул не JSON: {p.stdout[:200]}') from ex


def choose(versions, constraint):
    key = 'ranges' if isinstance(constraint, list) else 'range'
    data = invoke('csharp', {'versions': versions, key: constraint})
    result = data.get('version')
    if result not in versions:
        raise WorkError(f'Не найдена версия, подходящая под ограничение {constraint}')
    return result


def get_bytes(url):
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'dependency-graph-coursework/1.0', 'Accept': 'application/json, application/xml, */*'})
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except (OSError, urllib.error.HTTPError, urllib.error.URLError) as ex:
        raise WorkError(f'Ошибка чтения {url}: {ex}') from ex


def get_json(url):
    try:
        return json.loads(get_bytes(url))
    except (ValueError, UnicodeError) as ex:
        raise WorkError(f'Некорректный JSON {url}: {ex}') from ex


def flat_address(repository):
    index = get_json(repository)
    for resource in index.get('resources', []):
        kinds = resource.get('@type', [])
        if isinstance(kinds, str):
            kinds = [kinds]
        if any(k.startswith('PackageBaseAddress/') for k in kinds):
            return resource['@id'].rstrip('/') + '/'
    raise WorkError('В NuGet v3 service index нет PackageBaseAddress')


def framework_key(value):
    lowered = value.strip().lower()
    # NuGet.Frameworks распознаёт .NETFramework5.0 и выше как современные net5.0+ TFM.
    match = re.fullmatch(r'\.?netframework(\d+)\.(\d+)(?:\.(\d+))?', lowered)
    if match and int(match.group(1)) >= 5 and (match.group(3) is None or int(match.group(3)) == 0):
        return 'net' + match.group(1) + match.group(2)
    return re.sub(r'[^a-z0-9]', '', lowered).replace('netcoreapp', 'net')


def framework_rank(candidate, target):
    # Поддерживаем обычные net5+ и netstandard-группы; остальные случаи явно отклоняем.
    c = framework_key(candidate)
    t = framework_key(target)
    if not c:
        return (0, 0)
    if c == t:
        return (4, 0)
    target_match = re.fullmatch(r'net(\d+)', t)
    if not target_match:
        return None
    target_digits = target_match.group(1)
    target_major = int(target_digits[:-1]) if len(target_digits) > 1 else int(target_digits)
    if target_major < 5:
        return None
    net_match = re.fullmatch(r'net(\d+)', c)
    if net_match:
        digits = net_match.group(1)
        major = int(digits[:-1]) if len(digits) > 1 else int(digits)
        minor = int(digits[-1]) if len(digits) > 1 else 0
        if 5 <= major <= target_major and (major < target_major or minor <= int(target_digits[-1])):
            return (3, major * 10 + minor)
        # netcoreapp compatibility is limited to 3.1 or earlier.
        if major in (1, 2, 3) and major * 10 + minor <= 31:
            return (2, major * 10 + minor)
    standard = re.fullmatch(r'netstandard(\d+)', c)
    if standard:
        digits = standard.group(1)
        value = int(digits)
        if value <= 21:
            return (1, value)
    return None


def read_nuspec_dependencies(nuspec, framework):
    try:
        root = ET.fromstring(nuspec)
    except ET.ParseError as ex:
        raise WorkError(f'Некорректный nuspec: {ex}') from ex
    tag = lambda element: element.tag.rsplit('}', 1)[-1]
    deps = next((x for x in root.iter() if tag(x) == 'dependencies'), None)
    if deps is None:
        return []
    result = [(x.attrib.get('id'), x.attrib.get('version', '')) for x in deps if tag(x) == 'dependency']
    groups = [x for x in deps if tag(x) == 'group']
    if groups:
        # Выбираем только одну совместимую группу, не объединяя разные TFM.
        ranked = [(framework_rank(x.attrib.get('targetFramework', ''), framework), x) for x in groups]
        ranked = [(rank, group) for rank, group in ranked if rank is not None]
        if not ranked:
            names = ', '.join(x.attrib.get('targetFramework', '<any>') for x in groups)
            raise WorkError(f'Нет поддерживаемой совместимой группы для framework={framework}. Доступны: {names}')
        group = max(ranked, key=lambda item: item[0])[1]
        result.extend((x.attrib.get('id'), x.attrib.get('version', '')) for x in group if tag(x) == 'dependency')
    if any(not item[0] for item in result):
        raise WorkError('nuspec содержит зависимость без имени')
    return result


def load_test_graph(path, root_only=None):
    try:
        with open(path, encoding='utf-8') as source:
            graph = yaml.safe_load(source)
    except (OSError, yaml.YAMLError) as ex:
        raise WorkError(f'Ошибка тестового репозитория: {ex}') from ex
    if not isinstance(graph, dict):
        raise WorkError('Тестовый репозиторий должен содержать словарь')
    graph = graph.get('graph', graph)
    if not isinstance(graph, dict):
        raise WorkError('Поле graph должно содержать словарь')
    if root_only is not None:
        if root_only not in graph:
            raise WorkError(f'Тестовый пакет {root_only} отсутствует')
        graph = {root_only: graph[root_only]}
    for package, links in graph.items():
        if not isinstance(package, str) or not re.fullmatch(r'[A-Z]+', package):
            raise WorkError('Имена тестовых пакетов должны состоять из больших латинских букв')
        if not isinstance(links, list) or any(not isinstance(x, str) or not re.fullmatch(r'[A-Z]+', x) for x in links):
            raise WorkError(f'Зависимости {package} должны быть списком имён из больших латинских букв')
    if root_only is None:
        for links in graph.values():
            for item in links:
                if item not in graph:
                    raise WorkError(f'Тестовый пакет {item} отсутствует в репозитории')
    return graph


def breadth_first(root, version, fetch, enforce_unique_versions=False):
    # Помечаем узел при постановке в очередь и сохраняем все рёбра, включая циклы и общие зависимости.
    root_id = root if not version else root + '@' + version
    pending = deque([(root, version, root_id)])
    visited = {root_id.lower(): root_id}
    chosen_versions = {root.lower(): version}
    nodes, edges = [], []
    while pending:
        package, current_version, current_id = pending.popleft()
        nodes.append({'id': current_id, 'version': current_version or ''})
        for child, child_version in fetch(package, current_version):
            if enforce_unique_versions and child.lower() in chosen_versions and chosen_versions[child.lower()].lower() != child_version.lower():
                raise WorkError(f'Конфликт версий {child}: {chosen_versions[child.lower()]} и {child_version}; глобальное разрешение конфликтов NuGet пока не поддерживается')
            chosen_versions[child.lower()] = child_version
            target = child if not child_version else child + '@' + child_version
            if target.lower() not in visited:
                visited[target.lower()] = target
                pending.append((child, child_version, target))
            edges.append({'from': current_id, 'to': visited[target.lower()]})
    return {'root': root_id, 'nodes': nodes, 'edges': edges}


def resolve_nuget_graph(root, root_version, fetch, versions_for, resolver, direct_only=False):
    # Перестраиваем BFS, пока изменение версий больше не меняет достижимые зависимости.
    fixed = root.lower()
    preferred = {fixed: root_version}
    states = set()
    while True:
        queue = deque([(root, root_version, 0)])
        names = {fixed: root}
        used = {fixed: root_version}
        requirements = {}
        nodes, edges = [], []
        while queue:
            package, version, depth = queue.popleft()
            node = package + '@' + version
            nodes.append({'id': node, 'version': version})
            if direct_only and depth > 0:
                continue
            for dependency, constraint in fetch(package, version):
                key = dependency.lower()
                requirements.setdefault(key, []).append((constraint, depth + 1))
                if key not in used:
                    names[key] = dependency
                    selected = preferred.get(key)
                    if selected is None:
                        selected = resolver(versions_for(dependency), constraint)
                    if selected is None:
                        raise WorkError(f'Не найдена версия {dependency} для {constraint}')
                    used[key] = selected
                    queue.append((dependency, selected, depth + 1))
                edges.append({'from': node, 'to': names[key] + '@' + used[key]})
        updated = {fixed: root_version}
        for key, incoming in requirements.items():
            if key == fixed:
                continue
            # Требования непосредственной зависимости корня имеют приоритет, как в NuGet.
            direct = [r for r, depth in incoming if depth == 1]
            ranges = direct if direct else [r for r, depth in incoming]
            selector = ranges[0] if len(ranges) == 1 else ranges
            selected = resolver(versions_for(names[key]), selector)
            if selected is None:
                raise WorkError(f'Несовместимые ограничения версий {names[key]}: {ranges}')
            updated[key] = selected
        if updated == used:
            for key, incoming in requirements.items():
                if key != fixed and (not any(depth == 1 for _, depth in incoming) or not any(depth > 1 for _, depth in incoming)):
                    continue
                try:
                    all_ranges = [r for r, _ in incoming]
                    selected = resolver([used[key]], all_ranges if len(all_ranges) > 1 else all_ranges[0])
                    if selected is None:
                        raise WorkError('Версия не удовлетворяет всем транзитивным ограничениям')
                except WorkError:
                    print(f'Предупреждение: прямая зависимость {names[key]}@{used[key]} имеет приоритет над транзитивными ограничениями (возможен NU1605).', file=sys.stderr)
            return {'root': root + '@' + root_version, 'nodes': nodes, 'edges': edges}
        state = tuple(sorted(updated.items()))
        if state in states:
            raise WorkError('Не удалось стабилизировать выбор версий NuGet: повторяющееся состояние ограничений')
        states.add(state)
        if len(states) >= 1000:
            raise WorkError('Не удалось стабилизировать выбор версий NuGet за 1000 проходов')
        preferred = updated


def build_graph(config, resolver=choose, direct_only=False):
    if config['test_mode']:
        root = config['package']
        graph = load_test_graph(config['repository'], root if direct_only else None)
        if root not in graph:
            raise WorkError(f'Тестовый пакет {root} отсутствует')
        # Тестовый формат задаёт только имена, поэтому всем вершинам соответствует введённая версия.
        version = resolver([config['version']], '[' + config['version'] + ']')
        def test_fetch(package, _):
            if direct_only and package != root:
                return []
            return [(item, '') for item in graph[package]]
        result = breadth_first(root, '', test_fetch)
        for node in result['nodes']:
            node['version'] = version
        return result
    base = flat_address(config['repository'])
    framework = config.get('framework', 'net8.0')
    cache = {}
    versions_cache = {}

    def fetch(package, current_version):
        key = (package.lower(), current_version.lower())
        if key not in cache:
            encoded_name = urllib.parse.quote(package.lower(), safe='')
            encoded_version = urllib.parse.quote(current_version.lower(), safe='')
            nuspec_url = urllib.parse.urljoin(base, f'{encoded_name}/{encoded_version}/{encoded_name}.nuspec')
            links = read_nuspec_dependencies(get_bytes(nuspec_url), framework)
            cache[key] = links
        return cache[key]

    def versions_for(package):
        key = package.lower()
        if key not in versions_cache:
            versions_url = urllib.parse.urljoin(base, f'{urllib.parse.quote(key, safe="")}/index.json')
            versions_cache[key] = get_json(versions_url).get('versions', [])
            if not versions_cache[key]:
                raise WorkError(f'Нет версий пакета {package}')
        return versions_cache[key]

    root_version = resolver(versions_for(config['package']), '[' + config['version'] + ']')
    return resolve_nuget_graph(config['package'], root_version, fetch, versions_for, resolver, direct_only)


def execute(config, stage=5):
    if stage == 1:
        print(yaml.safe_dump(config, allow_unicode=True, sort_keys=True).rstrip())
        return
    graph = build_graph(config, direct_only=stage == 2)
    if stage == 2:
        print('\n'.join(edge['to'] for edge in graph['edges'] if edge['from'] == graph['root']))
        return
    if stage == 3:
        print(json.dumps(graph, ensure_ascii=False, indent=2))
        return
    graph = invoke('go', graph)
    analysis = invoke('rust', graph)
    if stage == 4:
        print(json.dumps(analysis, ensure_ascii=False, indent=2))
        return
    graph['analysis'] = analysis
    diagram = invoke('kotlin', graph)
    ascii_output = invoke('java', graph)
    rendered = invoke('javascript', {'mermaid': diagram['mermaid'], 'output_png': config['output_png']})
    if config['ascii_tree']:
        print(ascii_output['ascii'])
    print('Mermaid:')
    print(diagram['mermaid'])
    print('PNG:', rendered.get('output_png', config['output_png']))
    if analysis.get('cycles'):
        print('В графе есть цикл; строгий порядок загрузки отсутствует.', file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description='Граф зависимостей NuGet (вариант 13)')
    parser.add_argument('config', help='Путь к конфигурации YAML')
    parser.add_argument('--stage', type=int, choices=range(1, 6), default=5)
    args = parser.parse_args()
    try:
        with open(args.config, encoding='utf-8') as source:
            data = yaml.safe_load(source)
        data = CheckConfig(data, 1, 2, 3, 4, 5, 6, 7)
        execute(data, args.stage)
        return 0
    except (WorkError, OSError, yaml.YAMLError) as ex:
        print('Ошибка:', ex, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
