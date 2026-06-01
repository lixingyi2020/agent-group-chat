from app.db.models import LLMConfig
from app.orchestrator import should_respond, extract_mentions


def test_extract_mentions():
    assert extract_mentions("Hello @claude what do you think?") == ["claude"]
    assert extract_mentions("@claude and @gpt help me") == ["claude", "gpt"]
    assert extract_mentions("No mentions here") == []
    assert extract_mentions("@mention-with-dashes") == ["mention-with-dashes"]


def test_mention_always_responds():
    config = LLMConfig(name="claude", participation_mode="mention_only")
    assert should_respond(config, "Hey @claude", mention_names=["claude"]) is True


def test_always_mode_responds():
    config = LLMConfig(name="claude", participation_mode="always")
    assert should_respond(config, "Just a normal message") is True


def test_mention_only_skips_without_mention():
    config = LLMConfig(name="claude", participation_mode="mention_only")
    assert should_respond(config, "Just a normal message") is False


def test_probabilistic_0_never_responds():
    config = LLMConfig(name="claude", participation_mode="probabilistic", probability=0.0)
    responses = [should_respond(config, "msg") for _ in range(100)]
    assert all(r is False for r in responses)


def test_probabilistic_1_always_responds():
    config = LLMConfig(name="claude", participation_mode="probabilistic", probability=1.0)
    responses = [should_respond(config, "msg") for _ in range(100)]
    assert all(r is True for r in responses)


def test_self_reply_prevented():
    config = LLMConfig(name="claude", participation_mode="always")
    assert should_respond(config, "my own message", is_self=True) is False


def test_self_reply_allowed_when_mentioned():
    config = LLMConfig(name="claude", participation_mode="always")
    assert should_respond(config, "I agree with @claude", is_self=True, mention_names=["claude"]) is True


def test_everyone_triggers_all():
    config = LLMConfig(name="claude", participation_mode="mention_only")
    assert should_respond(config, "Hey @Everyone", mention_names=["Everyone"]) is True
    assert should_respond(config, "Hey @所有AI", mention_names=["所有AI"]) is True


def test_everyone_overrides_self_reply():
    config = LLMConfig(name="claude", participation_mode="always")
    assert should_respond(config, "@Everyone what now?", is_self=True, mention_names=["Everyone"]) is True
