# Сравнение предназначено для проверки результатов, а не получения данных основным приложением.
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import yaml
import main


def nuget_restore(config, directory):
    dotnet = os.environ.get('DOTNET_EXE') or shutil.which('dotnet')
    if not dotnet:
        raise RuntimeError('Для сравнения нужен установленный .NET SDK: укажите DOTNET_EXE или добавьте dotnet в PATH')
    folder = Path(directory)
    project = folder / 'comparison.csproj'
    nuget_config = folder / 'NuGet.Config'
    framework = config.get('framework', 'net8.0')

    project_root = ET.Element('Project', Sdk='Microsoft.NET.Sdk')
    properties = ET.SubElement(project_root, 'PropertyGroup')
    ET.SubElement(properties, 'TargetFramework').text = framework
    item_group = ET.SubElement(project_root, 'ItemGroup')
    ET.SubElement(item_group, 'PackageReference', Include=config['package'], Version='[' + config['version'] + ']')
    ET.ElementTree(project_root).write(project, encoding='utf-8', xml_declaration=True)

    sources_root = ET.Element('configuration')
    sources = ET.SubElement(sources_root, 'packageSources')
    ET.SubElement(sources, 'clear')
    ET.SubElement(sources, 'add', key='comparison-source', value=config['repository'])
    ET.ElementTree(sources_root).write(nuget_config, encoding='utf-8', xml_declaration=True)

    process_env = os.environ.copy()
    process_env.setdefault('DOTNET_CLI_HOME', str(folder / 'dotnet-home'))
    process_env.setdefault('NUGET_PACKAGES', str(folder / 'packages'))
    process_env.setdefault('DOTNET_CLI_TELEMETRY_OPTOUT', '1')
    command = [dotnet, 'restore', str(project), '--configfile', str(nuget_config), '--nologo']
    try:
        result = subprocess.run(command, cwd=folder, env=process_env, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f'Не удалось выполнить dotnet restore: {error}') from error
    if result.returncode != 0:
        raise RuntimeError('dotnet restore завершился с ошибкой:\n' + result.stdout + result.stderr)
    assets_path = folder / 'obj' / 'project.assets.json'
    try:
        data = json.loads(assets_path.read_text(encoding='utf-8'))
        targets = data['targets']
    except (OSError, ValueError, KeyError) as error:
        raise RuntimeError(f'Не удалось прочитать результат dotnet restore: {error}') from error
    if len(targets) != 1:
        raise RuntimeError(f'Ожидалась одна целевая платформа, получены: {list(targets)}')
    packages = {key: value for key, value in next(iter(targets.values())).items() if value.get('type') == 'package'}
    selected = {}
    for key in packages:
        name, separator, version = key.rpartition('/')
        if not separator or not name or not version:
            raise RuntimeError(f'Неожиданное имя пакета в NuGet: {key}')
        if name.casefold() in selected:
            raise RuntimeError(f'Несколько версий пакета в результате NuGet: {name}')
        selected[name.casefold()] = (name, version)
    if config['package'].casefold() not in selected:
        raise RuntimeError('NuGet не вернул выбранный корневой пакет')
    nodes = {f'{name}@{version}'.casefold() for name, version in selected.values()}
    edges = set()
    for key, metadata in packages.items():
        package, _, version = key.rpartition('/')
        source = f'{package}@{version}'.casefold()
        for dependency in metadata.get('dependencies', {}):
            node = selected.get(dependency.casefold())
            if node is None:
                raise RuntimeError(f'NuGet не вернул разрешённый пакет для зависимости {package} → {dependency}')
            edges.add((source, f'{node[0]}@{node[1]}'.casefold()))
    return nodes, edges


def run():
    parser = argparse.ArgumentParser(description='Сравнение собственного графа с NuGet restore')
    parser.add_argument('config', help='Конфигурация YAML для реального репозитория')
    args = parser.parse_args()
    try:
        with open(args.config, encoding='utf-8') as stream:
            config = main.CheckConfig(yaml.safe_load(stream), 1, 2, 3, 4, 5, 6, 7)
        if config['test_mode']:
            raise RuntimeError('Сравнение с NuGet возможно только при test_mode: false')
        graph = main.build_graph(config)
        actual_nodes = {node['id'].casefold() for node in graph['nodes']}
        actual_edges = {(edge['from'].casefold(), edge['to'].casefold()) for edge in graph['edges']}
        with tempfile.TemporaryDirectory(prefix='compare-nuget-') as directory:
            expected_nodes, expected_edges = nuget_restore(config, directory)
    except (main.WorkError, OSError, yaml.YAMLError, RuntimeError) as error:
        print(f'Ошибка сравнения: {error}', file=sys.stderr)
        return 2
    differences = [
        ('Узлы только приложения', actual_nodes - expected_nodes),
        ('Узлы только NuGet', expected_nodes - actual_nodes),
        ('Рёбра только приложения', actual_edges - expected_edges),
        ('Рёбра только NuGet', expected_edges - actual_edges),
    ]
    print(f"Сравнение {config['package']} {config['version']} ({config.get('framework', 'net8.0')})")
    print(f'Приложение: {len(actual_nodes)} узлов и {len(actual_edges)} рёбер; NuGet: {len(expected_nodes)} узлов и {len(expected_edges)} рёбер')
    for label, values in differences:
        print(label + ':')
        if not values:
            print('  нет')
        for value in sorted(values):
            print('  ' + (' → '.join(value) if isinstance(value, tuple) else value))
    if any(values for _, values in differences):
        return 1
    print('Узлы и рёбра совпадают.')
    return 0


if __name__ == '__main__':
    sys.exit(run())
