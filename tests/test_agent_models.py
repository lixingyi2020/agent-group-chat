from app.db.models import Agent, LLMConfig, Message


def test_agent_defaults():
    a = Agent()
    assert a.name == ""
    assert a.style_preset == "custom"
    assert a.participation_mode == "mention_only"
    assert a.probability == 0.3


def test_agent_create_with_fields():
    a = Agent(name="xiaozhushou", llm_config_id=1, system_prompt="Be helpful",
              style_preset="brief", participation_mode="always", probability=1.0)
    assert a.name == "xiaozhushou"
    assert a.llm_config_id == 1
    assert a.system_prompt == "Be helpful"
    assert a.style_preset == "brief"
    assert a.participation_mode == "always"
    assert a.probability == 1.0


def test_llm_config_no_longer_has_name():
    c = LLMConfig(provider="openai", model="gpt-4o")
    # name should not exist as a field
    assert not hasattr(c, 'name')


def test_message_has_agent_id():
    m = Message(agent_id=5)
    assert m.agent_id == 5
    assert m.llm_config_id is None
