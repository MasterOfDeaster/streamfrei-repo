#!/usr/bin/env python3
"""Builds "Nuvio TV B2": Nuvio TV (GPL-3.0, https://github.com/NuvioMedia/NuvioTVSmart)
tuned for the LG OLED55B29LA on webOS TV 23 (Chromium 94), as a separate app
(space.nuvio.webosb2) so the official app can stay installed.

Changes (source patch: nuvio-b2.patch):
  * JavaScript compiled for Chromium 94 instead of Chromium 56 (smaller bundle, fewer
    transforms and polyfills; the start-up gate refuses older TVs with a message).
  * LG alpha5/alpha7 models (OLED A/B1-B3, UHD/NanoCell LCD) start in the
    performance-constrained profile: no blur layers, single hero artwork layer, no
    sliding route animations, instant poster collapse, throttled D-pad hold repeat.

Usage: build-nuvio-b2.py <NuvioTVSmart checkout> <official release ipk> <out dir>
The official release ipk only supplies nuvio.env.js (public service keys), which the
source tree does not contain.
"""
import json, os, shutil, subprocess, sys

repo, official_ipk, out = (os.path.abspath(a) for a in sys.argv[1:4])
here = os.path.dirname(os.path.abspath(__file__))
OLD, NEW = 'space.nuvio.webos', 'space.nuvio.webosb2'
CHROMIUM = '94'
work = os.path.join(out, 'work')
shutil.rmtree(work, ignore_errors=True)
os.makedirs(work)


def run(cmd, **kw):
    print('+', ' '.join(cmd))
    subprocess.run(cmd, check=True, **kw)


# 1. Source patch + build
if subprocess.run(['git', 'apply', '--check', os.path.join(here, 'nuvio-b2.patch')], cwd=repo).returncode == 0:
    run(['git', 'apply', os.path.join(here, 'nuvio-b2.patch')], cwd=repo)
else:
    print('Patch already applied or not applicable; continuing with the tree as it is.')
env = dict(os.environ, NUVIO_CHROMIUM_TARGET=CHROMIUM)
run(['npm', 'ci', '--no-audit', '--no-fund'], cwd=repo, env=env)
run(['npm', 'run', 'build'], cwd=repo, env=env)

# 2. Public service keys from the official release
ex = os.path.join(work, 'official')
os.makedirs(ex)
run(['ar', 'x', official_ipk], cwd=ex)
os.makedirs(os.path.join(ex, 'data'))
run(['tar', 'xzf', 'data.tar.gz', '-C', 'data'], cwd=ex)
shutil.copy(os.path.join(ex, 'data/usr/palm/applications', OLD, 'nuvio.env.js'),
            os.path.join(repo, 'dist', 'nuvio.env.js'))

# 3. Official packaging pipeline (stages app + both services, builds the ipk)
run(['node', 'scripts/package-webos.mjs'], cwd=repo, env=env)
version = json.load(open(os.path.join(repo, 'dist', 'appinfo.json')))['version']
built = os.path.join(repo, f'{OLD}_{version}_all.ipk')

# 4. Re-id as a separate app
src = os.path.join(work, 'built')
os.makedirs(src)
run(['ar', 'x', built], cwd=src)
os.makedirs(os.path.join(src, 'data'))
run(['tar', 'xzf', 'data.tar.gz', '-C', 'data'], cwd=src)
data = os.path.join(src, 'data')
stage = os.path.join(work, 'stage')
os.makedirs(stage)
app_dst = os.path.join(stage, 'app')
shutil.copytree(os.path.join(data, 'usr/palm/applications', OLD), app_dst)
services = []
for name in sorted(os.listdir(os.path.join(data, 'usr/palm/services'))):
    new_name = NEW + name[len(OLD):]
    shutil.copytree(os.path.join(data, 'usr/palm/services', name), os.path.join(stage, new_name))
    services.append(new_name)

for root, _, files in os.walk(stage):
    for fn in files:
        if fn.endswith(('.json', '.js', '.cjs', '.mjs', '.html')) and not fn.endswith('.min.js'):
            p = os.path.join(root, fn)
            s = open(p, encoding='utf-8').read()
            s2 = s.replace(OLD + '.', NEW + '.').replace('"' + OLD + '"', '"' + NEW + '"')
            if s2 != s:
                open(p, 'w', encoding='utf-8').write(s2)

ai_path = os.path.join(app_dst, 'appinfo.json')
ai = json.load(open(ai_path))
ai['id'] = NEW
ai['title'] = 'Nuvio TV B2'
ai['services'] = [s for s in services if s.endswith('.service') and 'plugin' not in s]
json.dump(ai, open(ai_path, 'w'), indent=2)

with open(os.path.join(app_dst, 'NUVIO-B2-NOTICE.txt'), 'w') as f:
    f.write(f'Nuvio TV B2: modified build of Nuvio TV {version} (GPL-3.0, '
            'https://github.com/NuvioMedia/NuvioTVSmart), tuned for LG OLED B2 / webOS TV 23. '
            'Changes: see nuvio-b2.patch and build-nuvio-b2.py.\n')

ares = os.path.realpath(os.path.join(repo, 'node_modules', '.bin', 'ares-package'))
compat = os.path.join(repo, 'scripts', 'node24-ares-compat.cjs')
run(['node', '--require', compat, ares, app_dst] + [os.path.join(stage, s) for s in services] + ['-o', out])
print('OK:', [f for f in os.listdir(out) if f.endswith('.ipk')])
