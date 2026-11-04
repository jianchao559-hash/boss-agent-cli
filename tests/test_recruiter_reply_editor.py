"""Exercise the recruiter reply action against a fake editor, without BOSS access."""

import json
import shutil
import subprocess

import pytest

from boss_agent_cli.api.recruiter_client import _SEND_MESSAGE_ACTION_JS


_PAGE = r"""
const AsyncFunction = Object.getPrototypeOf(async function() {}).constructor;
const action = new AsyncFunction(
  'args', 'input', 'editor', 'conversation', 'log', 'escapeHtml', 'sleep',
  __ACTION_JSON__
);
const scenario = __SCENARIO_JSON__;
let now = 0;
let sendCount = 0;
let updateCount = 0;
const input = {
  _html: '',
  textContent: '',
  get innerHTML() { return this._html; },
  set innerHTML(value) { this._html = value; this.textContent = value; },
  dispatchEvent() { editor.callback(); },
};
const editor = {
  disabled: true,
  conversationLoading$: scenario === 'loading',
  conversation$: {friendId: 42},
  uniqueId: '42-0',
  draft: {},
  callback() {
    updateCount += 1;
    if (scenario === 'ready' || scenario === 'switched') this.disabled = false;
    if (scenario === 'switched') this.conversation$.friendId = 99;
  },
  sendText() { sendCount += 1; },
};
Date.now = () => now;
const sleep = async (ms) => { now += ms; };
const escapeHtml = (text) => String(text)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
action(
  {targetFriendId: 42, content: '在的', postSendUiWaitMs: 1200},
  input, editor, editor.conversation$, [], escapeHtml, sleep,
).then((result) => {
  console.log(JSON.stringify({result, sendCount, updateCount, html: input.innerHTML,
    draft: editor.draft[editor.uniqueId] || null, friendId: editor.conversation$.friendId}));
}).catch((error) => { console.error(error); process.exitCode = 1; });
"""


def _run_action(tmp_path, scenario):
    script = tmp_path / "reply-action.js"
    script.write_text(
        _PAGE.replace("__ACTION_JSON__", json.dumps(_SEND_MESSAGE_ACTION_JS))
        .replace("__SCENARIO_JSON__", json.dumps(scenario)),
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, encoding="utf-8", check=True, timeout=10
    )
    return json.loads(completed.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="requires node for page script")
def test_empty_editor_becomes_ready_before_one_send(tmp_path):
    page = _run_action(tmp_path, "ready")
    assert page["result"]["ok"] is True
    assert page["html"] == "在的"
    assert page["draft"] == "在的"
    assert page["updateCount"] >= 1
    assert page["sendCount"] == 1


@pytest.mark.skipif(shutil.which("node") is None, reason="requires node for page script")
def test_editor_stays_disabled_and_never_sends(tmp_path):
    page = _run_action(tmp_path, "stuck")
    assert page["result"]["ok"] is False
    assert page["html"] == "在的"
    assert page["sendCount"] == 0


@pytest.mark.skipif(shutil.which("node") is None, reason="requires node for page script")
def test_conversation_switches_during_preparation_and_never_sends(tmp_path):
    page = _run_action(tmp_path, "switched")
    assert page["result"]["ok"] is False
    assert page["html"] == "在的"
    assert page["friendId"] == 99
    assert page["sendCount"] == 0


@pytest.mark.skipif(shutil.which("node") is None, reason="requires node for page script")
def test_loading_editor_is_not_modified_or_sent(tmp_path):
    page = _run_action(tmp_path, "loading")
    assert page["result"]["ok"] is False
    assert page["html"] == ""
    assert page["sendCount"] == 0
