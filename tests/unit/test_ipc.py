from browser_harness import _ipc as ipc


def test_runtime_stem_uses_name_in_shared_runtime_dir(monkeypatch):
    monkeypatch.setattr(ipc, "BH_RUNTIME_DIR", "/tmp/browser-harness")
    monkeypatch.setattr(ipc, "BH_RUNTIME_DIR_SHARED", True)

    assert ipc._runtime_stem("work") == "bu-work"


def test_runtime_stem_uses_bare_name_in_isolated_runtime_dir(monkeypatch):
    monkeypatch.setattr(ipc, "BH_RUNTIME_DIR", "/tmp/browser-harness-work")
    monkeypatch.setattr(ipc, "BH_RUNTIME_DIR_SHARED", False)

    assert ipc._runtime_stem("work") == "bu"


def test_tmp_stem_uses_name_in_shared_tmp_dir(monkeypatch):
    monkeypatch.setattr(ipc, "BH_TMP_DIR", "/tmp/browser-harness")
    monkeypatch.setattr(ipc, "BH_TMP_DIR_SHARED", True)

    assert ipc._tmp_stem("work") == "bu-work"


# --- identify(): ping payload sanitation ---

class _FakeConn:
    def close(self): pass


def _patch_identify_response(monkeypatch, response):
    """Stub connect() and request() so identify() sees `response` as the JSON
    parsed from the daemon's reply, exactly as it would arrive over the wire."""
    monkeypatch.setattr(ipc, "connect", lambda name, timeout=1.0: (_FakeConn(), "tok"))
    monkeypatch.setattr(ipc, "request", lambda conn, tok, msg: response)


def test_identify_returns_pid_for_well_formed_ping_reply(monkeypatch):
    _patch_identify_response(monkeypatch, {"pong": True, "pid": 4242})

    assert ipc.identify("default", timeout=0.0) == 4242


def test_identify_rejects_boolean_pid(monkeypatch):
    """isinstance(True, int) is True in Python; a hostile or buggy daemon
    that replies {"pid": True} would otherwise yield PID 1 (init on POSIX),
    which os.kill(1, SIGTERM) would target. Reject it explicitly."""
    _patch_identify_response(monkeypatch, {"pong": True, "pid": True})

    assert ipc.identify("default", timeout=0.0) is None


def test_identify_rejects_boolean_false_pid(monkeypatch):
    """False is also an int subclass and would yield PID 0."""
    _patch_identify_response(monkeypatch, {"pong": True, "pid": False})

    assert ipc.identify("default", timeout=0.0) is None


def test_identify_returns_none_when_pid_field_missing(monkeypatch):
    """Pre-upgrade daemons reply {pong: True} only — no pid. identify must
    return None so callers know they have no verified PID to signal, while
    still letting alive-checks via ipc.ping() succeed."""
    _patch_identify_response(monkeypatch, {"pong": True})

    assert ipc.identify("default", timeout=0.0) is None


def test_identify_handles_non_dict_ping_payload(monkeypatch):
    """request() can deserialize any valid JSON value. A stale or hostile
    endpoint replying with a list / scalar / null would crash a naive
    resp.get() with AttributeError; identify must absorb that and return None."""
    for payload in ([1, 2, 3], "hello", 42, None):
        _patch_identify_response(monkeypatch, payload)
        assert ipc.identify("default", timeout=0.0) is None, (
            f"identify() should reject non-dict ping payload: {payload!r}"
        )


def test_identify_returns_none_when_pong_is_not_true(monkeypatch):
    _patch_identify_response(monkeypatch, {"pong": False, "pid": 4242})

    assert ipc.identify("default", timeout=0.0) is None


def test_identify_rejects_zero_and_negative_pids(monkeypatch):
    """os.kill semantics on POSIX: pid=0 signals every process in the calling
    process group; pid=-1 signals every process the caller can; pid<-1 signals
    the corresponding process group. None of these are valid daemon PIDs and
    forwarding any of them to os.kill would be catastrophic."""
    for bad_pid in (0, -1, -42, -99999):
        _patch_identify_response(monkeypatch, {"pong": True, "pid": bad_pid})
        assert ipc.identify("default", timeout=0.0) is None, (
            f"identify() must reject non-positive pid {bad_pid!r}"
        )


# --- ping(): same payload sanitation ---

def _patch_ping_response(monkeypatch, response):
    monkeypatch.setattr(ipc, "connect", lambda name, timeout=1.0: (_FakeConn(), "tok"))
    monkeypatch.setattr(ipc, "request", lambda conn, tok, msg: response)


def test_ping_returns_true_for_well_formed_pong(monkeypatch):
    _patch_ping_response(monkeypatch, {"pong": True})

    assert ipc.ping("default", timeout=0.0) is True


def test_ping_handles_non_dict_payload(monkeypatch):
    """Same regression class as identify(): if a stale or hostile endpoint
    replies with a list / scalar / null, ping() must return False rather than
    raising AttributeError on resp.get(). restart_daemon() now calls ping() on
    the fallback path, so an unhandled raise here would abort cleanup."""
    for payload in ([1, 2, 3], "hello", 42, None):
        _patch_ping_response(monkeypatch, payload)
        assert ipc.ping("default", timeout=0.0) is False, (
            f"ping() should reject non-dict payload: {payload!r}"
        )


def test_ping_returns_false_when_pong_field_is_missing_or_not_true(monkeypatch):
    for resp in ({}, {"pong": False}, {"pong": "yes"}, {"pong": 1}):
        _patch_ping_response(monkeypatch, resp)
        assert ipc.ping("default", timeout=0.0) is False, (
            f"ping() should require pong is exactly True; got: {resp!r}"
        )


def test_serve_accepts_requests_larger_than_64kib(monkeypatch, tmp_path):
    """asyncio's default stream limit is 64 KiB per line. The daemon frames one
    JSON request per line and payloads like js() with a bundled library or a
    long type_text() easily exceed that; serve() must raise the limit or every
    such request dies with "Separator is not found, and chunk exceed the limit"."""
    import asyncio, json, tempfile

    # AF_UNIX sun_path is 104 bytes on macOS; pytest tmp_path can blow the
    # budget, so bind in a short /tmp dir like the dev wrapper does.
    short_dir = tempfile.mkdtemp(prefix="bh-ipc-", dir="/tmp")
    monkeypatch.setattr(ipc, "IS_WINDOWS", False)
    monkeypatch.setattr(ipc, "BH_RUNTIME_DIR", short_dir)
    monkeypatch.setattr(ipc, "BH_RUNTIME_DIR_SHARED", False)
    from pathlib import Path
    monkeypatch.setattr(ipc, "_RUNTIME", Path(short_dir))

    payload = "x" * (128 * 1024)  # 2x the default limit

    async def scenario():
        async def handler(reader, writer):
            # Mirrors daemon.serve(): one readline per connection.
            try:
                line = await reader.readline()
                req = json.loads(line)
                resp = {"len": len(req["payload"])}
            except Exception as e:
                resp = {"error": str(e)}
            writer.write((json.dumps(resp) + "\n").encode())
            await writer.drain()
            writer.close()

        serve_task = asyncio.create_task(ipc.serve("default", handler))
        await asyncio.sleep(0.1)  # let the socket bind
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(ipc._sock_path("default")), limit=1 << 24
            )
            writer.write((json.dumps({"payload": payload}) + "\n").encode())
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), timeout=5)
            writer.close()
            return json.loads(line)
        finally:
            serve_task.cancel()

    resp = asyncio.run(scenario())
    assert resp.get("error") is None, f"oversized request rejected: {resp}"
    assert resp.get("len") == len(payload)
