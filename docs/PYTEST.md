
[Guidelines](../../Guidelines.md) > [Guideline: Coding Guidelines Python](../Guideline_%20Coding%20Guidelines%20Python.md)

# Pytest guidelines

This document applies the [Guideline: Testing](../Guideline_%20Testing.md) principles to actual code. Each section covers a single principle: test naming, structure, testing public entry points, dependency injection, choosing the right test double, and using one behavior per test.

- [Test naming: behavior, not mechanics](#pytestguidelines-testnamingbehaviornotmechanics)
- [Arrange-Act-Assert](#pytestguidelines-arrange-act-assert)
- [Test through the public surface](#pytestguidelines-testthroughthepublicsurface)
- [Stubs, mocks, fakes - pick the right double](#pytestguidelines-stubsmocksfakes-picktherightdouble)
- [Parametrize](#pytestguidelines-parametrize)
- [One behavior per test](#pytestguidelines-onebehaviorpertest)

# Test naming: behavior, not mechanics

Name the test after the observable outcome, not the function being exercised.

**[tests/unit/cmk/gui/test\_escaping.py[^![](/images/icons/linkext7.gif)]](https://github.com/Checkmk/checkmk/blob/cbc95b7/tests/unit/cmk/gui/test_escaping.py#L13)**

```python
# bad "escape_to_html_permissive" is the function name, not a behavior
def test_escape_to_html_permissive() -> None:
    assert str(escaping.escape_to_html_permissive("<script>")) == "&lt;script&gt;"
    assert str(escaping.escape_to_html_permissive("<b>")) == "<b>"
```

`parametrize` covers multiple input variants without duplicating the test body. Use a behavior-oriented function name and descriptive parameter names so each failing case tells you what broke:

**[tests/unit/cmk/gui/test\_valuespec.py[^![](/images/icons/linkext7.gif)]](https://github.com/Checkmk/checkmk/blob/cbc95b7/tests/unit/cmk/gui/test_valuespec.py#L235)**

```python
# good - behavior name; pytest.param(id=) names each case; single assertion; no branching in body
@pytest.mark.parametrize(
    "address",
    [
        pytest.param("text", id="no @ symbol"),
        pytest.param("user@foo", id="local hostname only"),
        pytest.param("\t\n a@localhost \t\n", id="whitespace around address"),
    ],
)
def test_email_validation_raises(address: str) -> None:
    with pytest.raises(MKUserError):
        vs.EmailAddress().validate_value(address, "")
```

# Arrange-Act-Assert

Three blank-line-separated phases; no inline comments needed.

**[tests/unit/cmk/gui/test\_http.py[^![](/images/icons/linkext7.gif)]](https://github.com/Checkmk/checkmk/blob/cbc95b7/tests/unit/cmk/gui/test_http.py#L30)**

```python
# good - three blank-line-separated phases are visible at a glance
def test_request_del_vars_from_query_string() -> None:
    r = http.Request(create_environ(method="GET", query_string="a=1&b=2"))

    r.del_var_from_env("a")

    assert r.query_string == b"b=2"
```

Use blank lines to separate multiple act/assert cycles and keep the logic readable. While this stretches the "one behavior per test" rule, state machines are an exception. Splitting these into separate tests would either duplicate setup or hide how steps depend on each other. If every step verifies a transition that relies on the previous one, keep them in a single, well-spaced test.

**[tests/unit/cmk/product\_usage/test\_schedule.py[^![](/images/icons/linkext7.gif)]](https://github.com/Checkmk/checkmk/blob/cbc95b7/tests/unit/cmk/product_usage/test_schedule.py#L39)**

```python
# good (exception) - state-machine test; each assert depends on the prior transition
def test_should_run_product_usage_on_schedule() -> None:
    now = datetime.now()
    ts_file_path = next_run_file_path(var_dir)

    assert should_run_collection_on_schedule(var_dir, now) is False

    store_next_run_ts(ts_file_path, 1)

    assert should_run_collection_on_schedule(var_dir, now) is True

    future_ts = int((now + timedelta(days=1)).timestamp())
    store_next_run_ts(ts_file_path, future_ts)

    assert should_run_collection_on_schedule(var_dir, now) is False
```

# Test through the public surface

Don't call private functions (prefixed `_`) from tests. Their behavior is reachable through the public entry point.

**[tests/unit/cmk/test\_cmkpasswd.py[^![](/images/icons/linkext7.gif)]](https://github.com/Checkmk/checkmk/blob/cbc95b7/tests/unit/cmk/test_cmkpasswd.py#L72)**

```python
# bad - calls private _run_cmkpasswd instead of the public CLI entry point
def test_invalid_password() -> None:
    with pytest.raises(InvalidPasswordError, match="Password too long"):
        _run_cmkpasswd("testuser", _get_pw(73 * "a"), None)
```

The same behaviors are reachable through `main()`, the public CLI entry point. Testing there also verifies the exit code and stderr message the user actually sees:

```python
# good - tests through main(); asserts on the observable CLI output
def test_invalid_passwords(capsys: Capsys) -> None:
    with patch("sys.stdin", StringIO(_get_pw(73 * "a"))):
        assert main(args=["-i", "testuser"]) != 0
        captured = capsys.readouterr()
        assert "Password too long" in captured.err.lower()
```

# Stubs, mocks, fakes - pick the right double

A **test double** stands in for a real collaborator. There are three kinds worth distinguishing:

- **Stub**: returns fixed canned values; contains no real logic. Use when the collaborator is expensive or stateful to construct and the test only needs a specific return value.
- **Fake**: a lightweight working implementation with a real-ish in-memory state. Use when the collaborator has a meaningful state across calls (reads its own writes, accumulates history, etc.).
- **Mock**: a stub that additionally records calls and lets you assert on them with `assert_called_*`. Use only when the call itself is the entire observable behavior: there is no return value and no state to inspect.

| Double   | Pattern                                | When to use                                                  |
|:---------|:---------------------------------------|:-------------------------------------------------------------|
| **Stub** | `Mock(spec=X)` with `.return_value`    | Collaborator is expensive to construct; assert on outcome    |
| **Fake** | Hand-written class with real-ish state | Collaborator has meaningful state across calls               |
| **Mock** | `Mock()` with `.assert_called_*`       | Last resort: the call itself is the only observable behavior |

**Warning:** *\_mocks are almost always the wrong choice. `assert*called*_` pins implementation - the test breaks when you rename a method or change how the code wires things together, even if behavior is identical. Reach for a stub or fake first. Only use a mock when there is genuinely no return value, no state to inspect, and no fake that would be simpler.\**

**Mock** - the hook system's contract is that `hooks.call("bla")` fires every handler registered under `"bla"` and no others. There is no return value or state to read - the call being made is the entire point, making this one of the rare cases where a mock is correct:

**[tests/unit/cmk/gui/test\_gui\_hooks.py[^![](/images/icons/linkext7.gif)]](https://github.com/Checkmk/checkmk/blob/cbc95b7/tests/unit/cmk/gui/test_gui_hooks.py#L254)**

```python
# good (rare mock use) - the call being fired is the entire observable behavior; no return value or state to inspect
def test_call(mocker: MockerFixture) -> None:
    hook1_mock = mocker.Mock()
    hook2_mock = mocker.Mock()
    hooks.register("bla", hook1_mock)
    hooks.register("blub", hook2_mock)

    hooks.call("bla")

    hook1_mock.assert_called_once()
    hook2_mock.assert_not_called()
```

`assert_called_*` is frequently misused to pin internal implementation steps nobody outside the function cares about. Reserve it for cases like the one above. When you want to verify *what* was sent (not just *that* it was sent), a fake that records its calls is clearer.

**Stub** - when a collaborator would be painful to instantiate, use `Mock(spec=X)` and set `.return_value` on the methods you need. The `spec=` keeps the stub honest: accessing attributes that don't exist on the real class raises `AttributeError` immediately.

**[tests/unit/cmk/gui/nonfree/ultimate/relay/watolib/test\_attributes.py[^![](/images/icons/linkext7.gif)]](https://github.com/Checkmk/checkmk/blob/cbc95b7/tests/unit/cmk/gui/nonfree/ultimate/relay/watolib/test_attributes.py#L28)**

```python
# good - Mock(spec=) stub; spec= catches stale attribute access, return_value supplies canned answer
def _mock_relay_config_manager(
    configs: dict[str, RelayConfiguration],
) -> RelayConfigManager:
    manager = Mock(spec=RelayConfigManager)
    manager.all.return_value = configs
    return manager

def test_always_includes_no_relay() -> None:
    choices = relay_choices(_mock_relay_config_manager({}))
    assert len(choices) == 1
    assert choices[0] == ("", "No relay")
```

`RelayConfigManager` requires site state and storage that has nothing to do with these tests - a stub with a canned `.all()` return value is the right call. No protocol needed.

**Fake** - when the collaborator has meaningful state across calls, a hand-written class with real-ish in-memory state is clearer than a stub. The fake is constructed, injected, and the test asserts on both the output and the fake's state:

**Adapted from: [tests/unit/cmk/checkengine/test\_parsers.py[^![](/images/icons/linkext7.gif)]](https://github.com/Checkmk/checkmk/blob/cbc95b7/tests/unit/cmk/checkengine/test_parsers.py#L933)**

```python
# good - fake with real copy-on-store semantics; injected into AgentParser, no patching
class FakeStore(SectionStore):
    def __init__(self, path: str | Path, sections: object, *, logger: logging.Logger) -> None:
        super().__init__(path, logger=logger)
        self._sections = sections

    def store(self, sections):
        self._sections = copy.copy(sections)

    def load(self):
        return copy.copy(self._sections)

def test_update_with_empty_store_and_empty_raw_data(self, logger: logging.Logger) -> None:
    section_store = FakeStore("/dev/null", {}, logger=logger)
    parser = AgentParser(
        HostName("testhost"),
        section_store,
        host_check_interval=0,
        keep_outdated=True,
        translation=TranslationOptions(),
        encoding_fallback="ascii",
        logger=logger,
    )

    ahs = parser.parse(AgentRawData(b""), selection=NO_SELECTION)

    assert not ahs.sections
    assert not ahs.cache_info
    assert not ahs.piggybacked_raw_data
    assert section_store.load() == {}
```

Dependency injection over patching

**Dependency injection** means you make a collaborator a parameter of the function or class. At call time, you pass in a real instance, a stub, or a fake. This approach avoids module-level globals and makes dependencies explicit in the signature.

**Patching** (`unittest.mock.patch`) replaces a name in a module namespace during a test. While patching works without changing the production API, it couples the test to import paths. If you rename a module or move a function, the patch will fail silently.

Prefer dependency injection when you own the code. Patching is acceptable for external boundaries you do not control, such as standard library I/O, third-party HTTP requests, or OS calls. You use patching in these cases because the library does not allow you to inject the collaborator as a parameter. When you use a patch, assert on observable outcomes instead of mock call details.

**[tests/unit/cmk/product\_usage/test\_transmission.py[^![](/images/icons/linkext7.gif)]](https://github.com/Checkmk/checkmk/blob/cbc95b7/tests/unit/cmk/product_usage/test_transmission.py#L66)**

```python
# acceptable - patching third-party requests.post (external boundary we don't own)
with patch("requests.post") as mock_post:
    mock_post.side_effect = mocks
    transmit_data(tmp_path, logger=mock.Mock())
```

# Parametrize

When cases differ meaningfully, name each one with `pytest.param(id=)` so the failing case is immediately clear in test output. This works best when the case list stays short and each row fits comfortably on one line:

**[tests/unit/cmk/gui/test\_valuespec.py[^![](/images/icons/linkext7.gif)]](https://github.com/Checkmk/checkmk/blob/cbc95b7/https://github.com/Checkmk/checkmk/blob/cbc95b7/tests/unit/cmk/gui/test_valuespec.py#L235#L235)**

```python
# good - short inputs; each case fits on one line; id= makes failures self-explaining
@pytest.mark.parametrize(
    "address",
    [
        pytest.param("text",                   id="no @ symbol"),
        pytest.param("user@foo",               id="local hostname only"),
        pytest.param("\t\n a@localhost \t\n",  id="whitespace around address"),
    ],
)
def test_email_validation_raises(address: str) -> None:
    with pytest.raises(MKUserError):
        vs.EmailAddress().validate_value(address, "")
```

Don't overuse `parametrize`. The signal that it's being misused: the test body contains an `if` that branches on the input.

```py
# bad - out: str | None drives two different assertions; 20+ cases obscure what's actually tested
@pytest.mark.parametrize(
    "inp,out",
    [
        ("<script>alert(1)</script>", "&lt;script&gt;alert(1)&lt;/script&gt;"),
        ("<h1>abc</h1>", None),
        ("<h2>abc</h2>", None),
        # ... 17 more cases
        ("<b/onclick=alert(1)>abc</b>", "&lt;b/onclick=alert(1)&gt;abc</b>"),
    ],
)
def test_escape_text(inp: str, out: str | None) -> None:
    if out is None:
        assert escaping.escape_permissive(inp) == inp   # behavior 1: allowed tags pass through
    else:
        assert escaping.escape_permissive(inp) == out   # behavior 2: dangerous tags are escaped
```

Split on the behavioral boundary. It can be good to use `# fmt: off` / `# fmt: on` around the parametrize decorator to keep the formatter from collapsing the layout; with multiple columns, aligning them as a table makes each case easy to scan:

**[packages/cmk-web/tests/utils/test\_escaping.py#L46[^![](/images/icons/linkext7.gif)]](https://github.com/Checkmk/checkmk/blob/cbc95b7/https://github.com/Checkmk/checkmk/blob/cbc95b7/packages/cmk-web/tests/utils/test_escaping.py#L46#L46)**

```python
# good (illustrative) - each test covers one behavior; the case list is short and focused
@pytest.mark.parametrize("tag", [
    pytest.param("<h1>abc</h1>", id="h1"),
    pytest.param("<b>abc</b>", id="b"),
    pytest.param("<i>abc</i>", id="i"),
    # ... remaining allowed tags
])
def test_allowed_tags_pass_through_unchanged(tag: str) -> None:
    assert escaping.escape_permissive(tag) == tag


# fmt: off
@pytest.mark.parametrize("inp,expected", [
    pytest.param("<script>alert(1)</script>",  "&lt;script&gt;alert(1)&lt;/script&gt;",          id="script tag"),
    pytest.param('<a href="xyz">abc</a>',      "&lt;a href=&quot;xyz&quot;&gt;abc&lt;/a&gt;",     id="anchor without target"),
    pytest.param("<b/onclick=alert(1)>abc</b>","&lt;b/onclick=alert(1)&gt;abc</b>",               id="event handler injection"),
])
# fmt: on
def test_dangerous_markup_is_escaped(inp: str, expected: str) -> None:
    assert escaping.escape_permissive(inp) == expected
```

When arguments grow long enough that each case needs multiple lines, `parametrize` hurts readability more than it helps, and the case list becomes harder to scan than just reading separate functions:

**[xpackages/cmk-web/tests/utils/test\_escaping.py#L46[^![](/images/icons/linkext7.gif)]](https://github.com/Checkmk/checkmk/blob/cbc95b7/packages/cmk-web/tests/utils/test_escaping.py#L46)**

```python
# bad - each case spans multiple lines; harder to read than named tests
@pytest.mark.parametrize(
    ("proxy_setting", "expected_proxy_config"),
    [
        pytest.param(("no_proxy", None), http_proxy_config.NoProxyConfig(), id="no proxy"),
        pytest.param(
            ("url", http_proxy_config.ProxyConfigSpec(scheme="http", proxy_server_name="company.com", port=123)),
            http_proxy_config.ExplicitProxyConfig("http://company.com:123"),
            id="proxy without auth",
        ),
        # ... more cases
    ],
)
def test_get_proxy_config(proxy_setting: ProxySetting, expected_proxy_config: ...) -> None:
    assert get_proxy_config(proxy_setting, global_proxies=global_settings_proxies) == expected_proxy_config
```

```py
# good (illustrative) - each case is a named test; the arrange block is self-contained and readable
def test_get_proxy_config_no_proxy(global_settings_proxies: ...) -> None:
    proxy_config = get_proxy_config(("no_proxy", None), global_proxies=global_settings_proxies)
    assert proxy_config == http_proxy_config.NoProxyConfig()


def test_get_proxy_config_explicit_url(global_settings_proxies: ...) -> None:
    proxy_config = get_proxy_config(
        ("url", http_proxy_config.ProxyConfigSpec(scheme="http", proxy_server_name="company.com", port=123)),
        global_proxies=global_settings_proxies,
    )
    assert proxy_config == http_proxy_config.ExplicitProxyConfig("http://company.com:123")
```

# One behavior per test

Each test should fail for exactly one reason. Name each test after the outcome it protects. A failure message should tell you exactly what broke:

**[tests/unit/cmk/base/test\_events.py#L543[^![](/images/icons/linkext7.gif)]](https://github.com/Checkmk/checkmk/blob/cbc95b7/tests/unit/cmk/base/test_events.py#L543)**

```python
# good - each test names an outcome; fails independently; short body
def test_apply_matchers_returns_none_on_empty_matchers(basic_event_rule: EventRule) -> None:
    assert apply_matchers([], basic_event_rule, context={}, analyse=False, all_timeperiods={}) is None


def test_apply_matchers_returns_none_when_all_pass(basic_event_rule: EventRule) -> None:
    assert apply_matchers(
        [lambda *args, **kw: None, lambda *args, **kw: None],
        basic_event_rule, context={}, analyse=False, all_timeperiods={},
    ) is None


def test_apply_matchers_returns_first_non_none_result(basic_event_rule: EventRule) -> None:
    result = apply_matchers(
        [lambda *args, **kw: None, lambda *args, **kw: "reason one", lambda *args, **kw: "reason two"],
        basic_event_rule, context={}, analyse=False, all_timeperiods={},
    )
    assert result == "reason one"


def test_apply_matchers_stops_at_first_failure(basic_event_rule: EventRule) -> None:
    called: list[str] = []

    def first_matcher(rule, context, analyse, all_timeperiods) -> str:
        called.append("first")
        return "failed"

    def second_matcher(rule, context, analyse, all_timeperiods) -> None:
        called.append("second")

    apply_matchers([first_matcher, second_matcher], basic_event_rule, context={}, analyse=False, all_timeperiods={})
    assert called == ["first"]
```

**[tests/unit/cmk/product\_usage/test\_schedule.py#L28[^![](/images/icons/linkext7.gif)]](https://github.com/Checkmk/checkmk/blob/cbc95b7/tests/unit/cmk/product_usage/test_schedule.py#L28)**

```python
# bad - two behaviors, one test; failure message points at the whole operation
def test_get_and_store_next_product_usage_run_ts() -> None:
    ts_file_path = next_run_file_path(var_dir)
    now = datetime.now().replace(microsecond=0)
    assert get_next_run_ts(ts_file_path) is None          # behavior 1
    store_next_run_ts(ts_file_path, int(now.timestamp()))
    assert get_next_run_ts(ts_file_path) == now           # behavior 2
```

```py
# good (illustrative) - one behavior per test; each can fail and be understood independently
def test_get_next_run_ts_returns_none_before_any_run() -> None:
    ts_file_path = next_run_file_path(var_dir)
    assert get_next_run_ts(ts_file_path) is None


def test_get_next_run_ts_returns_stored_timestamp() -> None:
    ts_file_path = next_run_file_path(var_dir)
    now = datetime.now().replace(microsecond=0)
    store_next_run_ts(ts_file_path, int(now.timestamp()))
    assert get_next_run_ts(ts_file_path) == now
```

A common variant: multiple `pytest.raises` blocks in one test function, each testing a distinct rejection case. Each `raises` is a separate behavior, a single failure won't tell you which case broke.

**[tests/unit/cmk/utils/test\_version.py#L42[^![](/images/icons/linkext7.gif)]](https://github.com/Checkmk/checkmk/blob/cbc95b7/tests/unit/cmk/utils/test_version.py#L42)**

```python
# bad - five distinct invalid formats bundled; one failure hides the other four
def test_invalid_combo(self) -> None:
    with pytest.raises(ValueError):
        Version.from_str("1.2.3b5-2023.01.01")
    with pytest.raises(ValueError):
        Version.from_str("2.2.0rc1")
    with pytest.raises(ValueError):
        Version.from_str("2.2.0p5-rc")
    with pytest.raises(ValueError):
        Version.from_str("1.2.3-2023.12.24-rc1")
    with pytest.raises(ValueError):
        Version.from_str("2023.12.24-rc1")
```

`parametrize` collapses these into one declaration; each case now fails and is reported independently:

**[tests/unit/cmk/utils/test\_version.py#L42[^![](/images/icons/linkext7.gif)]](https://github.com/Checkmk/checkmk/blob/cbc95b7/tests/unit/cmk/utils/test_version.py#L42)**

```python
# good (ilustrative) - each format gets its own named run; failures identify exactly which case broke
@pytest.mark.parametrize(
    "version_string",
    [
        pytest.param("1.2.3b5-2023.01.01", id="beta with date suffix"),
        pytest.param("2.2.0rc1", id="rc without patch level"),
        pytest.param("2.2.0p5-rc", id="patch with bare rc suffix"),
        pytest.param("1.2.3-2023.12.24-rc1", id="stable daily with rc suffix"),
        pytest.param("2023.12.24-rc1", id="daily with rc suffix"),
    ],
)
def test_invalid_version_string_raises(self, version_string: str) -> None:
    with pytest.raises(ValueError):
        Version.from_str(version_string)
```
