#!/usr/bin/env python3
"""Provision a pinned loopback-only Neo4j for publisher tests inside managed scratch.

Invoke through proxmox-scratch run; no live configuration or database is used.
Requires Python packages neo4j and pytest. Downloads only checksum-pinned public
distributions, runs bounded tests, records credential-free evidence and cleans up.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import tarfile
import tempfile
import time
import urllib.request

PACKAGES = [
    ('java', 'https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jre_x64_linux_hotspot_21.0.12.1_1.tar.gz',
     '2413149700df0f7d440500a84a8f764c535f21e5a5e87d38328b64eec2c5b500'),
    ('neo4j', 'https://dist.neo4j.org/neo4j-community-5.26.0-unix.tar.gz',
     'ad8ac3398606145502b8f489530bbd39333707ae4668156af16b6086b5b037d7'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get('STORAGE_ARTIFACT_DIR') or not os.environ.get('TMPDIR'):
        parser.error('run only inside proxmox-scratch with managed scratch/artifact paths')
    from neo4j import GraphDatabase
    args.artifacts.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='kg-disposable-'))
    os.chmod(root, 0o700)
    control_path = root / 'control.json'
    report = {'schema': 'hswm-disposable-publisher-run/v1', 'production_configuration_used': False,
              'packages': [], 'tests_exit_code': None, 'cleanup': {}}
    try:
        for name, url, expected in PACKAGES:
            archive = root / (name + '.tar.gz')
            with urllib.request.urlopen(url, timeout=90) as response, archive.open('wb') as output:
                shutil.copyfileobj(response, output)
            actual = hashlib.sha256(archive.read_bytes()).hexdigest()
            assert actual == expected, 'download checksum mismatch: ' + name
            report['packages'].append({'name': name, 'url': url, 'sha256': actual})
            with tarfile.open(archive) as tar:
                tar.extractall(root, filter='data')
            archive.unlink()
        home = root / 'neo4j-community-5.26.0'
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
        config_text = f'''server.default_listen_address=127.0.0.1
server.bolt.listen_address=127.0.0.1:{port}
server.bolt.advertised_address=127.0.0.1:{port}
server.http.enabled=false
server.https.enabled=false
server.memory.heap.initial_size=128m
server.memory.heap.max_size=512m
server.memory.pagecache.size=64m
dbms.security.auth_enabled=true
dbms.usage_report.enabled=false
'''
        (home / 'conf/neo4j.conf').write_text(config_text)
        report['config_sha256'] = hashlib.sha256(config_text.encode()).hexdigest()
        env = dict(os.environ, JAVA_HOME=str(root / 'jdk-21.0.12.1+1-jre'))
        with (root / 'server.log').open('wb') as output:
            process = subprocess.Popen([str(home / 'bin/neo4j'), 'console'], env=env,
                                       stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        control_path.write_text(json.dumps({'root': str(root), 'pid': process.pid}))
        config = {'uri': f'bolt://127.0.0.1:{port}', 'user': 'neo4j',
                  'password': secrets.token_urlsafe(32), 'database': 'neo4j'}
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            assert process.poll() is None, 'fixture server exited before readiness'
            try:
                # Initial auth is changed over Bolt parameters, never command arguments.
                with GraphDatabase.driver(config['uri'], auth=('neo4j', 'neo4j'),
                                          connection_timeout=1) as driver:
                    with driver.session(database='system') as session:
                        session.run('ALTER CURRENT USER SET PASSWORD FROM $old TO $new',
                                    old='neo4j', new=config['password']).consume()
                break
            except Exception:
                time.sleep(.5)
        else:
            raise TimeoutError('fixture did not become ready in 90 seconds')
        private = root / 'credentials.json'
        private.write_text(json.dumps(config)); os.chmod(private, 0o600)
        env.update(HSWM_LEGACY_DISPOSABLE_TEST='1', HSWM_LEGACY_DISPOSABLE_CONFIG=str(private),
                   HSWM_DISPOSABLE_CONTROL=str(control_path), PYTHONPATH='src')
        import sys
        command = [sys.executable, '-B', '-m', 'pytest', '-q', '--tb=short',
                   '--basetemp', str(root / 'pytest'), '-p', 'no:cacheprovider',
                   'tests/test_kg_legacy_projection_integration.py',
                   'tests/test_kg_remaining_publishers_integration.py', 'tests/test_kg_disposable_faults.py']
        with (args.artifacts / 'disposable-tests.log').open('wb') as output:
            completed = subprocess.run(command, env=env, stdout=output, stderr=subprocess.STDOUT, timeout=600)
        report['tests_exit_code'] = completed.returncode
        with GraphDatabase.driver(config['uri'], auth=(config['user'], config['password'])) as driver:
            with driver.session(database=config['database']) as session:
                report['cleanup']['remaining_nodes'] = session.run('MATCH (n) RETURN count(n) AS n').single()['n']
        assert report['cleanup']['remaining_nodes'] == 0
    finally:
        if control_path.exists():
            pid = json.loads(control_path.read_text())['pid']
            try:
                command = Path(f'/proc/{pid}/cmdline').read_bytes()
                if str(root).encode() in command and os.getpgid(pid) == pid:
                    os.killpg(pid, signal.SIGTERM)
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline and Path(f'/proc/{pid}/cmdline').exists():
                        if not Path(f'/proc/{pid}/cmdline').read_bytes():
                            break
                        time.sleep(.2)
                    else:
                        os.killpg(pid, signal.SIGKILL)
            except (ProcessLookupError, FileNotFoundError):
                pass
        for name in ('server.log', 'server-restarts.log'):
            if (root / name).exists():
                shutil.copyfile(root / name, args.artifacts / name)
        shutil.rmtree(root)
        report['cleanup']['private_runtime_removed'] = not root.exists()
        (args.artifacts / 'runtime.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    raise SystemExit(report['tests_exit_code'])


if __name__ == '__main__':
    main()
