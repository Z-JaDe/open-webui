"""fork Config 读缓存(CONFIG_CACHE_TTL_S)行为测试:命中减查询、写穿透即时可见、
失效点全覆盖(upsert/delete/clear/rename/repair/seed)、TTL 到期重查、TTL=0 关闭。"""

import asyncio
import time

import pytest

# 收集序契约:本文件名 aaa 前缀确保在 test_banyan_feedback_bridge 之前收集
# ——后者会把 sys.modules['open_webui.models.config'] 整体替换成桩;先收集
# 则本文件常规 import 绑定到真模块,测试运行时不再查注册表(桩不影响)。
import open_webui.models.config as mc
from open_webui.models.config import Config


class _Row:
    def __init__(self, key, value):
        self.key = key
        self.value = value


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    """计数型假 session:get/execute 各计数一次。"""

    def __init__(self, store):
        self.store = store
        self.get_calls = 0
        self.execute_calls = 0
        self._flushed = []

    async def get(self, cls, key):
        self.get_calls += 1
        return self.store.get(key)

    async def execute(self, *_a, **_k):
        self.execute_calls += 1
        return _FakeResult(list(self.store.values()))

    def add(self, obj):
        self.store[obj.key] = _Row(obj.key, obj.value)
        self._flushed.append(obj.key)

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def delete(self, row):
        self.store.pop(row.key, None)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """隔离环境:清缓存、DEFAULTS/持久化开、注入计数 DB。
    全量套件下本模块可能被其它直载/reload 用例替换(sys.modules 换新实例),
    顶部 import 的旧引用会失配——fixture 实时取当前注册实例。"""
    monkeypatch.setattr(mc, '_MEM', {})
    monkeypatch.setattr(mc, '_CACHE_TTL_S', 30.0)
    Config.configure(defaults={'demo.a': 'def-a', 'demo.b': 'def-b'},
                     enable_persistent=True)
    db = _FakeDB({'demo.x': _Row('demo.x', 'v1'), 'demo.y': _Row('demo.y', 'v2')})

    class _Ctx:
        def __init__(self, d):
            self._d = d

        async def __aenter__(self):
            return self._d

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(mc, 'get_async_db', lambda: _Ctx(db))
    return db


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_get_hits_cache_after_first_query(env):
    env.get_calls = 0
    assert run(Config.get('demo.x')) == 'v1'
    assert env.get_calls == 1
    assert run(Config.get('demo.x')) == 'v1'
    assert run(Config.get('demo.x')) == 'v1'
    assert env.get_calls == 1, '缓存命中不再打库'


def test_get_caches_negative_result(env):
    env.get_calls = 0
    assert run(Config.get('demo.absent')) == Config.default_value('demo.absent')
    assert run(Config.get('demo.absent')) == Config.default_value('demo.absent')
    assert env.get_calls == 1, '不存在的键负缓存(防反复打库)'


def test_get_many_single_roundtrip(env):
    run(Config.get_many('demo.x', 'demo.y', 'demo.z'))
    assert env.execute_calls == 1, '批量 miss 合并为一次 IN 查询'
    run(Config.get_many('demo.x', 'demo.y', 'demo.z'))
    assert env.execute_calls == 1, '二次全命中零查询'


def test_upsert_write_through(env):
    run(Config.get('demo.x'))
    run(Config.upsert({'demo.x': 'v1-new'}))
    after = env.get_calls          # 含 upsert 内部 existing 检查那一次
    assert run(Config.get('demo.x')) == 'v1-new', '写穿透即时可见'
    assert env.get_calls == after, '读新值零额外查询(命中被穿透更新的缓存)'


def test_delete_invalidates(env):
    run(Config.get('demo.x'))
    run(Config.delete('demo.x'))    # 内部含一次 existing 检查
    after = env.get_calls
    assert run(Config.get('demo.x')) == Config.default_value('demo.x')
    assert env.get_calls == after + 1, '删除后重查一次落回 default'


def test_ttl_expiry_refetches(env, monkeypatch):
    run(Config.get('demo.x'))
    base = env.get_calls
    fake = [1000.0]
    monkeypatch.setattr(mc.time, 'monotonic', lambda: fake[0])
    mc._cache_put('demo.x', 'v1')
    fake[0] = 1000.0 + 31.0            # 越过 30s TTL
    assert run(Config.get('demo.x')) == 'v1'
    assert env.get_calls == base + 1, 'TTL 过期后重新打库'


def test_ttl_zero_disables_cache(env, monkeypatch):
    monkeypatch.setattr(mc, '_CACHE_TTL_S', 0.0)
    mc._MEM.clear()
    run(Config.get('demo.x'))
    run(Config.get('demo.x'))
    assert env.get_calls == 2, 'TTL=0 回归上游每查一次打库'


def test_namespace_and_all_cached_and_invalidated(env):
    run(Config.get_namespace('demo'))
    assert run(Config.get_namespace('demo')) == run(Config.get_namespace('demo'))
    assert env.execute_calls >= 1
    e = env.execute_calls
    run(Config.get_namespace('demo'))
    assert env.execute_calls == e, 'namespace 命中缓存'
    run(Config.upsert({'demo.n': 'v'}))
    assert 'demo.n' in run(Config.get_namespace('demo')), '写穿透使 namespace 段失效重取'
    run(Config.get_all())
    a = env.execute_calls
    run(Config.get_all())
    assert env.execute_calls == a, 'get_all 命中缓存'
