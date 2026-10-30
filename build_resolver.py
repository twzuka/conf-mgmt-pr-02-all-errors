# Сборка C# без NuGet restore: все ссылки входят в установленный .NET SDK.
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parent
executable = os.environ.get('DOTNET_EXE') or shutil.which('dotnet') or '/workspace/toolchains/dotnet/dotnet'
dotnet = Path(executable).resolve()
installation = dotnet.parent
sdks = sorted((installation / 'sdk').glob('8.*'), key=lambda p: tuple(int(x) for x in p.name.split('.') if x.isdigit()))
refs = sorted((installation / 'packs' / 'Microsoft.NETCore.App.Ref').glob('8.*'), key=lambda p: tuple(int(x) for x in p.name.split('.') if x.isdigit()))
if not sdks or not refs:
    raise SystemExit('The .NET 8 SDK and reference packs are required')
out = root / 'bin' / 'Release' / 'net8.0'
out.mkdir(parents=True, exist_ok=True)
response = ['-nologo', '-target:exe', '-nullable:enable', f'-out:{out / "Resolver.dll"}']
response += [f'-r:{p}' for p in sorted((refs[-1] / 'ref' / 'net8.0').glob('*.dll'))]
response.append(str(root / 'Resolver.cs'))
with tempfile.TemporaryDirectory(prefix='build-csharp-') as temp:
    args = Path(temp) / 'csc.rsp'
    args.write_text('\n'.join(response), encoding='utf-8')
    subprocess.run([str(dotnet), 'exec', str(sdks[-1] / 'Roslyn/bincore/csc.dll'), '@' + str(args)], check=True)
(out / 'Resolver.runtimeconfig.json').write_text(json.dumps({'runtimeOptions': {'tfm': 'net8.0', 'framework': {'name': 'Microsoft.NETCore.App', 'version': '8.0.0'}}}), encoding='utf-8')
print(out / 'Resolver.dll')
