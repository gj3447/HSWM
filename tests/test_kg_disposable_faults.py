"""Real Bolt reply loss and SIGKILL recovery, only in the explicit disposable fixture."""
import contextlib
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import threading
import time
from urllib.parse import urlsplit

import pytest

from hswm.infrastructure import kg_legacy_projection as gateway
from test_kg_legacy_projection_integration import db, fixture, snapshot

pytestmark = pytest.mark.skipif(os.environ.get('HSWM_LEGACY_DISPOSABLE_TEST') != '1',
                                reason='explicit disposable database opt-in required')


class CommitReplyDrop:
    """One-connection TCP relay. Arm only after all RUN/PULL replies are consumed.

    Observe a complete Bolt COMMIT message, receive its server SUCCESS message,
    then close without forwarding that SUCCESS. The client cannot see the ACK.
    Negotiation and ordinary traffic pass unchanged; no query rewriting.
    """
    def __init__(self, uri):
        address = urlsplit(uri)
        assert address.hostname in ('localhost', '127.0.0.1')
        self.target = (address.hostname, address.port)
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(1)
        self.listener.settimeout(15)
        self.uri = f'bolt://127.0.0.1:{self.listener.getsockname()[1]}'
        self.armed = threading.Event()
        self.dropped = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        try:
            with self.listener, self.listener.accept()[0] as client, socket.create_connection(self.target) as server:
                outgoing = incoming = b''
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    ready, _, _ = select.select([client, server], [], [], 1)
                    for source in ready:
                        data = source.recv(65536)
                        if not data:
                            return
                        if self.armed.is_set():
                            if source is client:
                                outgoing += data
                                # COMMIT is an empty structure with signature 0x12.
                                assert b'\x00\x02\xb0\x12\x00\x00'.startswith(outgoing)
                            else:
                                assert outgoing == b'\x00\x02\xb0\x12\x00\x00'
                                incoming += data
                                if incoming.endswith(b'\x00\x00'):
                                    assert incoming[2:4] == b'\xb1\x70', 'expected server SUCCESS'
                                    self.dropped.set()
                                    return
                                continue
                            server.sendall(data)
                        else:
                            (server if source is client else client).sendall(data)
                raise TimeoutError('bounded Bolt fault relay expired')
        except BaseException as error:
            self.error = error

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.thread.join(timeout=16)
        self.listener.close()
        assert not self.thread.is_alive(), 'fault relay did not terminate'
        if self.error:
            raise self.error


def test_lost_server_commit_acknowledgement_recovers_without_duplicate(db):
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable, SessionExpired
    _, config, run, prepare, publish = db
    data = fixture(); prepare(data)
    with CommitReplyDrop(config['uri']) as relay:
        with GraphDatabase.driver(relay.uri, auth=(config['user'], config['password']),
                                  connection_timeout=10, max_transaction_retry_time=0) as driver:
            with driver.session(database=config['database']) as session:
                tx = session.begin_transaction()
                gateway.publish_projection(tx, data)
                relay.armed.set()
                with pytest.raises((ServiceUnavailable, SessionExpired)):
                    tx.commit()
            assert relay.dropped.wait(2), 'server SUCCESS was not suppressed'
    before = snapshot(run)
    assert publish(data)['created_nodes'] == 0
    assert snapshot(run) == before


def restart_disposable(config):
    """Kill only the fixture process group whose root is bound by the runner."""
    control_path = os.environ.get('HSWM_DISPOSABLE_CONTROL')
    if not control_path:
        pytest.skip('server crash requires runner-owned process control')
    path = Path(control_path)
    control = json.loads(path.read_text())
    root = Path(control['root']).resolve()
    pid = control['pid']
    command = Path(f'/proc/{pid}/cmdline').read_bytes()
    assert str(root).encode() in command and b'neo4j' in command
    assert os.getpgid(pid) == pid
    os.killpg(pid, signal.SIGKILL)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', urlsplit(config['uri']).port)) != 0:
                break
        time.sleep(.1)
    else:
        raise AssertionError('fixture listener survived SIGKILL')
    home = root / 'neo4j-community-5.26.0'
    env = dict(os.environ, JAVA_HOME=str(root / 'jdk-21.0.12.1+1-jre'))
    with (root / 'server-restarts.log').open('ab') as output:
        process = subprocess.Popen([str(home / 'bin/neo4j'), 'console'], env=env,
                                   stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    control['pid'] = process.pid
    path.write_text(json.dumps(control))
    from neo4j import GraphDatabase
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        assert process.poll() is None, 'fixture server failed to restart'
        try:
            with GraphDatabase.driver(config['uri'], auth=(config['user'], config['password']),
                                      connection_timeout=1) as driver:
                driver.verify_connectivity()
            return
        except Exception:
            time.sleep(.5)
    raise TimeoutError('fixture server restart exceeded 60 seconds')


@pytest.mark.parametrize('committed', [False, True])
def test_server_sigkill_recovers_transaction_boundary(db, committed):
    driver, config, run, prepare, publish = db
    data = fixture(); prepare(data)
    with driver.session(database=config['database']) as session:
        tx = session.begin_transaction()
        gateway.publish_projection(tx, data)
        if committed:
            tx.commit()
        restart_disposable(config)
        with contextlib.suppress(Exception):
            tx.close()
    assert publish(data)['created_nodes'] == (0 if committed else 2)
    before = snapshot(run)
    assert publish(data)['created_nodes'] == 0
    assert snapshot(run) == before
