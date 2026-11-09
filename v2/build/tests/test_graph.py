"""The build graph on toy stages: versioned outputs, resume, rebuild on change, check gates."""
import json

import pytest

from v2.build.graph import Graph, Stage

CALLS = []


def make(ctx):
    CALLS.append(("make", ctx.params.get("n")))
    (ctx.out / "x.txt").write_text(str(ctx.params.get("n")))
    return {"n": ctx.params.get("n")}


def use(ctx):
    CALLS.append(("use",))
    v = (ctx.dep("make") / "x.txt").read_text()
    (ctx.out / "y.txt").write_text(v * 2)
    return {"v": v}


def gate(ctx):
    CALLS.append(("gate",))
    ok = (ctx.dep("use") / "y.txt").read_text() != "99"
    return {"passed": ok, "lines": ["PASS" if ok else "FAIL"]}


def after(ctx):
    CALLS.append(("after",))
    return {}


def graph(n):
    return Graph([Stage("make", make, params={"n": n}), Stage("use", use, deps=("make",)),
                  Stage("gate", gate, deps=("use",), kind="check"), Stage("after", after, deps=("gate",))])


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("ISOLUX_DATA", str(tmp_path))
    CALLS.clear()
    return tmp_path


def test_builds_then_resumes(data):
    assert graph(1).build("test", ["after"]) == 0
    assert [c[0] for c in CALLS] == ["make", "use", "gate", "after"]
    CALLS.clear()
    assert graph(1).build("test", ["after"]) == 0
    assert CALLS == []                                    # everything up to date: nothing runs


def test_manifest_and_versioned_folder(data):
    g = graph(2)
    g.build("test", ["use"])
    folder = g.folder("use", "test")
    assert folder.parent == data / "v2" / "test" / "use"
    m = json.loads((folder / "manifest.json").read_text())
    assert m["status"] == "ok" and m["deps"]["make"]["key"] == g.key("make", "test")[0]
    assert {"code_hash", "code_version", "params", "raw", "files", "summary"} <= set(m)


def test_param_change_rebuilds_downstream_only_and_keeps_old_versions(data):
    graph(3).build("test", ["use"])
    CALLS.clear()
    g = graph(4)
    g.build("test", ["use"])
    assert [c[0] for c in CALLS] == ["make", "use"]
    assert len(list((data / "v2" / "test" / "make").glob("*/manifest.json"))) == 2


def test_failed_check_fails_the_build_and_blocks_downstream(data):
    assert graph(9).build("test", ["after"]) == 1        # y = "99": the gate fails
    assert ("after",) not in CALLS
    m = json.loads((graph(9).folder("gate", "test") / "manifest.json").read_text())
    assert m["status"] == "failed"


def test_error_is_recorded(data):
    def boom(ctx):
        raise ValueError("nope")
    g = Graph([Stage("boom", boom)])
    assert g.build("test", ["boom"]) == 1
    m = json.loads((g.folder("boom", "test") / "manifest.json").read_text())
    assert m["status"] == "error" and "nope" in m["error"]
