# Регрессионные случаи для локального компонента разрешения NuGet-версий.
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent
DOTNET = os.environ.get('DOTNET_EXE') or shutil.which('dotnet') or '/workspace/toolchains/dotnet/dotnet'
DLL = ROOT / 'bin' / 'Release' / 'net8.0' / 'Resolver.dll'

class VersionChecks(unittest.TestCase):
    def resolve(self, versions, spec=None, ranges=None):
        request = {'versions': versions}
        if ranges is not None:
            request['ranges'] = ranges
        else:
            request['range'] = spec
        result = subprocess.run([DOTNET, str(DLL)], input=json.dumps(request), text=True, capture_output=True, check=True)
        return json.loads(result.stdout)['version']

    def test_ranges_and_floating(self):
        common = ['1.0.0', '1.2.0', '2.0.0']
        cases = [
            (common, '[1.0,2.0)', '1.0.0'),
            (common, '(1.0,2.0]', '1.2.0'),
            (common, '[1.2]', '1.2.0'),
            (common, '[3.0,)', None),
            (common, '', '1.0.0'),
            (common, '*', '2.0.0'),
            (common, '1.*', '1.2.0'),
            (['2.0.0', '3.0.0'], '1.*', '2.0.0'),
            (['1.0.0-beta.9', '1.0.0-beta.2', '1.0.0'], '[1.0.0-beta.1,1.0.0]', '1.0.0-beta.2'),
            (['1.0.0-alpha.1', '1.0.0'], '1.0.0-alpha.*', '1.0.0'),
            (['1.0.0-alpha.1', '1.0.0-alpha.2', '1.0.0-beta.1'], '1.0.0-alpha.*', '1.0.0-alpha.2'),
            (['1.0.0-beta.1', '1.0.0'], '1.0.0-alpha.*', '1.0.0'),
            (['1.0.0-beta.1'], '1.0.0-alpha.*', '1.0.0-beta.1'),
            (['1.0.0-alpha', '1.0.0-alpha.1'], '1.0.0-alpha*', '1.0.0-alpha.1'),
            (['1.2.3-rc.1', '1.2.3-rc.2'], '1.2.3-rc.*', '1.2.3-rc.2'),
            (['1.0.0-alpha', '1.0.0-beta', '1.0.0'], '*-*', '1.0.0'),
        ]
        for versions, spec, expected in cases:
            with self.subTest(spec=spec, versions=versions):
                self.assertEqual(self.resolve(versions, spec), expected)

    def test_intersection(self):
        versions = ['1.0.0', '1.5.0', '2.0.0', '2.5.0']
        self.assertEqual(self.resolve(versions, ranges=['[1.0,3.0)', '[1.5,2.5)']), '1.5.0')
        self.assertEqual(self.resolve(versions, ranges=['[1.0,2.0)', '[2.0,3.0)']), None)
        self.assertEqual(self.resolve(versions, ranges=['1.*', '[1.0,2.0)']), '1.5.0')
        self.assertEqual(self.resolve(versions, ranges=[]), '1.0.0')

    def test_invalid_range_fails(self):
        for spec in ('[invalid]', '(,)', '(1.0,1.0]', '[1.0,1.0)'):
            with self.subTest(spec=spec):
                result = subprocess.run([DOTNET, str(DLL)], input=json.dumps({'versions': ['1.0.0'], 'range': spec}), text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Invalid', result.stderr)

if __name__ == '__main__':
    unittest.main()
