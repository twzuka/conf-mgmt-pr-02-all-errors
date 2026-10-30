import json
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class GraphChecks(unittest.TestCase):
    def test_diamond_and_cycle_retain_all_edges_without_unbounded_traversal(self):
        graph = main.load_test_graph('repository_cycle.yaml')
        result = main.breadth_first('A', '', lambda p, _: [(x, '') for x in graph[p]])
        self.assertEqual([x['id'] for x in result['nodes']], ['A', 'B', 'C', 'D'])
        self.assertEqual(result['edges'], [{'from':'A','to':'B'}, {'from':'A','to':'C'}, {'from':'B','to':'D'}, {'from':'C','to':'D'}, {'from':'D','to':'A'}])

    def test_case_insensitive_nuget_node_ids_do_not_create_dangling_edges(self):
        graph = {'ROOT': [('Package', '1.0.0'), ('package', '1.0.0')], 'Package': []}
        result = main.breadth_first('ROOT', '1.0.0', lambda p, _: graph[p])
        self.assertEqual([x['id'] for x in result['nodes']], ['ROOT@1.0.0', 'Package@1.0.0'])
        self.assertEqual(result['edges'][0]['to'], result['edges'][1]['to'])

    def test_conflicting_package_versions_are_not_silently_reported_as_nuget_graph(self):
        links = {'Root': [('Left', '1.0.0'), ('Right', '1.0.0')], 'Left': [('Shared', '1.0.0')], 'Right': [('shared', '2.0.0')], 'Shared': []}
        with self.assertRaisesRegex(main.WorkError, 'Конфликт версий shared'):
            main.breadth_first('Root', '1.0.0', lambda package, _: links[package], enforce_unique_versions=True)

    def test_nuget_diamond_intersects_requirements_and_drops_stale_edges(self):
        links = {('Root', '1.0.0'): [('Left', '>=1'), ('Right', '>=1')], ('Left', '1.0.0'): [('Shared', '>=1')], ('Right', '1.0.0'): [('Shared', '>=2')], ('Shared', '1.0.0'): [('Old', '>=1')], ('Shared', '2.0.0'): [('New', '>=1')], ('Old', '1.0.0'): [], ('New', '1.0.0'): []}
        def versions(package):
            return ['1.0.0', '2.0.0'] if package == 'Shared' else ['1.0.0']
        def resolve(options, constraint):
            rules = constraint if isinstance(constraint, list) else [constraint]
            return next((v for v in options if all(int(v.split('.')[0]) >= int(r[2:]) for r in rules)), None)
        result = main.resolve_nuget_graph('Root', '1.0.0', lambda p,v: links[p,v], versions, resolve)
        ids = {n['id'] for n in result['nodes']}
        self.assertIn('Shared@2.0.0', ids)
        self.assertIn('New@1.0.0', ids)
        self.assertNotIn('Shared@1.0.0', ids)
        self.assertNotIn('Old@1.0.0', ids)
        self.assertTrue(all('Old@' not in edge['to'] for edge in result['edges']))

    def test_nuget_direct_dependency_wins_and_reports_downgrade(self):
        links = {('Root', '1.0.0'): [('Shared', '>=1'), ('Left', '>=1')], ('Left', '1.0.0'): [('Shared', '>=2')], ('Shared', '1.0.0'): []}
        def versions(package):
            return ['1.0.0', '2.0.0'] if package == 'Shared' else ['1.0.0']
        def resolve(options, constraint):
            rules = constraint if isinstance(constraint, list) else [constraint]
            return next((v for v in options if all(int(v.split('.')[0]) >= int(r[2:]) for r in rules)), None)
        with patch('sys.stderr') as stderr:
            result = main.resolve_nuget_graph('Root', '1.0.0', lambda p,v: links[p,v], versions, resolve)
        self.assertIn('Shared@1.0.0', {n['id'] for n in result['nodes']})
        self.assertIn('NU1605', ''.join(str(c) for c in stderr.write.call_args_list))

    def test_nuget_incompatible_cousin_requirements_report_error(self):
        links = {('Root', '1.0.0'): [('Left', '>=1'), ('Right', '>=1')], ('Left', '1.0.0'): [('Shared', '>=2')], ('Right', '1.0.0'): [('Shared', '<=1')], ('Shared', '2.0.0'): []}
        def versions(package):
            return ['1.0.0', '2.0.0'] if package == 'Shared' else ['1.0.0']
        def resolve(options, constraint):
            rules = constraint if isinstance(constraint, list) else [constraint]
            return next((v for v in options if all((int(v[0]) >= int(r[2:])) if r.startswith('>=') else (int(v[0]) <= int(r[2:])) for r in rules)), None)
        with self.assertRaisesRegex(main.WorkError, 'Несовместимые ограничения'):
            main.resolve_nuget_graph('Root', '1.0.0', lambda p,v: links[p,v], versions, resolve)

    def test_cycle_back_to_root_reports_version_downgrade(self):
        links = {('Root', '1.0.0'): [('Child', '>=1')], ('Child', '1.0.0'): [('Root', '>=2')]}
        def resolve(options, constraint):
            rules = constraint if isinstance(constraint, list) else [constraint]
            return next((v for v in options if all(int(v[0]) >= int(r[2:]) for r in rules)), None)
        with patch('sys.stderr') as stderr:
            result = main.resolve_nuget_graph('Root', '1.0.0', lambda p,v: links[p,v], lambda p: ['1.0.0'], resolve)
        self.assertEqual(len(result['edges']), 2)
        self.assertIn('NU1605', ''.join(str(c) for c in stderr.write.call_args_list))

    def test_missing_graph_node_is_an_error(self):
        with patch('builtins.open', unittest.mock.mock_open(read_data='A: [B]')):
            with self.assertRaisesRegex(main.WorkError, 'B'):
                main.load_test_graph('unused')

    def test_bad_config_values_are_rejected(self):
        good = dict(package='A', version='1.0.0', repository='repository_cycle.yaml', test_mode=True, output_png='g.png', ascii_tree=True)
        for field, value in [('package','a'), ('version','wat'), ('repository','missing'), ('test_mode','true'), ('output_png','g.jpg'), ('ascii_tree','true')]:
            config = dict(good, **{field: value})
            with self.subTest(field=field), self.assertRaises(main.WorkError):
                main.CheckConfig(config, 1, 2, 3, 4, 5, 6, 7)

    def test_nuspec_selects_one_framework_group(self):
        spec = b'<package><metadata><dependencies><group targetFramework="net8.0"><dependency id="One" version="[1,2)"/></group><group targetFramework="net6.0"><dependency id="Other" version="1.0"/></group></dependencies></metadata></package>'
        self.assertEqual(main.read_nuspec_dependencies(spec, 'net8.0'), [('One', '[1,2)')])
        self.assertEqual(main.read_nuspec_dependencies(spec, 'net7.0'), [('Other', '1.0')])
        with self.assertRaises(main.WorkError):
            main.read_nuspec_dependencies(spec, 'net4.0')

    def test_framework_prefers_latest_compatible_and_never_unrelated(self):
        spec = b'<package><metadata><dependencies><group targetFramework=".NETFramework4.8"><dependency id="Wrong"/></group><group targetFramework=".NETStandard2.0"><dependency id="Standard"/></group><group targetFramework="net6.0"><dependency id="Net"/></group></dependencies></metadata></package>'
        self.assertEqual(main.read_nuspec_dependencies(spec, 'net8.0'), [('Net', '')])
        bad = b'<package><metadata><dependencies><group targetFramework=".NETFramework4.8"><dependency id="Wrong"/></group></dependencies></metadata></package>'
        with self.assertRaises(main.WorkError):
            main.read_nuspec_dependencies(bad, 'net8.0')

    def test_dapper_nuspec_netframework8_is_nuget_net8_and_has_no_dependencies(self):
        # NuGet.Frameworks воспринимает это нетривиальное имя как net8.0; net461 остаётся .NET Framework.
        spec = b'<package><metadata><dependencies><group targetFramework=".NETFramework4.6.1"><dependency id="Old"/></group><group targetFramework=".NETFramework8.0"/><group targetFramework=".NETStandard2.0"><dependency id="FalsePositive"/></group></dependencies></metadata></package>'
        self.assertEqual(main.read_nuspec_dependencies(spec, 'net8.0'), [])
        self.assertEqual(main.read_nuspec_dependencies(spec, '.NETFramework4.6.1'), [('Old', '')])
        self.assertEqual(main.framework_key('.NETFramework8.0'), main.framework_key('net8.0'))
        self.assertIsNone(main.framework_rank('.NETFramework4.6.1', 'net8.0'))

    def test_mock_nuget_http_discovers_root_and_transitive_package(self):
        index = {'resources': [{'@type':'PackageBaseAddress/3.0.0','@id':'https://example.org/flat/'}]}
        packages = {'https://example.org/v3/index.json': index, 'https://example.org/flat/root/index.json': {'versions':['1.0.0']}, 'https://example.org/flat/leaf/index.json': {'versions':['2.0.0']}}
        nuspecs = {'https://example.org/flat/root/1.0.0/root.nuspec': b'<package><metadata><dependencies><dependency id="Leaf" version="[2.0.0]"/></dependencies></metadata></package>', 'https://example.org/flat/leaf/2.0.0/leaf.nuspec': b'<package><metadata><dependencies/></metadata></package>'}
        cfg = dict(package='Root', version='1.0.0', repository='https://example.org/v3/index.json', test_mode=False, output_png='g.png', ascii_tree=False)
        with patch.object(main, 'get_json', side_effect=lambda url: packages[url]), patch.object(main, 'get_bytes', side_effect=lambda url: nuspecs[url]):
            graph = main.build_graph(cfg, lambda versions, constraint: versions[0])
        self.assertEqual(graph['edges'], [{'from':'Root@1.0.0', 'to':'Leaf@2.0.0'}])

    def test_large_graph_is_iterative(self):
        fixture = main.load_test_graph('repository_large.yaml')
        graph = main.breadth_first('A', '', lambda p, _: [(x, '') for x in fixture[p]])
        self.assertEqual(len(graph['nodes']), 1101)
        self.assertEqual(len(graph['edges']), 1100)

    def test_stage_two_does_not_read_transitive_nuspec(self):
        index = {'resources': [{'@type':'PackageBaseAddress/3.0.0','@id':'https://example.org/flat/'}]}
        packages = {'https://example.org/v3/index.json': index, 'https://example.org/flat/root/index.json': {'versions':['1.0.0']}, 'https://example.org/flat/leaf/index.json': {'versions':['2.0.0']}}
        root_spec = b'<package><metadata><dependencies><dependency id="Leaf" version="[2.0.0]"/></dependencies></metadata></package>'
        cfg = dict(package='Root', version='1.0.0', repository='https://example.org/v3/index.json', test_mode=False, output_png='g.png', ascii_tree=False)
        with patch.object(main, 'get_json', side_effect=lambda url: packages[url]), patch.object(main, 'get_bytes', return_value=root_spec) as get_nuspec:
            result = main.build_graph(cfg, lambda versions, constraint: versions[0], direct_only=True)
        self.assertEqual(len(result['edges']), 1)
        self.assertEqual(get_nuspec.call_count, 1)

    def test_test_mode_uses_configured_version_and_stage_two_ignores_broken_child(self):
        cfg = dict(package='A', version='2.3.4', repository='unused', test_mode=True, output_png='g.png', ascii_tree=False)
        inputs = []
        def resolver(versions, constraint):
            inputs.append((versions, constraint))
            return versions[0]
        with patch('builtins.open', unittest.mock.mock_open(read_data='A: [B]\nB: broken')):
            result = main.build_graph(cfg, resolver, direct_only=True)
        self.assertEqual(inputs, [(['2.3.4'], '[2.3.4]')])
        self.assertEqual(result['nodes'][0]['version'], '2.3.4')
        self.assertEqual(result['edges'], [{'from':'A', 'to':'B'}])


if __name__ == '__main__':
    unittest.main()
