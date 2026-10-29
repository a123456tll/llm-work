"""Skill 动态加载机制的测试。

覆盖：发现与注册、Frontmatter 解析（含块标量多行 description）、
必需字段校验、惰性正文读取，以及"以启动工作目录为项目根"的默认行为。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.agent import Agent
from core.factory import build_agent, build_default_skill_registry
from core.skills import (
    LOAD_SKILL_TOOL_NAME,
    SkillLoaderTool,
    SkillRegistry,
    SkillSpec,
    build_skill_tools,
    build_skills_prompt,
    discover_skill_dirs,
    discover_skills,
    find_skills_root,
    load_skills,
)
from core.tools.registry import ToolRegistry
from tests.fakes import FakeLLMClient, text_events, tool_events


def _write_skill(root: Path, name: str, frontmatter: str, body: str = "# body") -> Path:
    """在 ``root/.agentskills/<name>`` 下写入一个 SKILL.md。"""
    skill_dir = root / ".agentskills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n" + frontmatter + "---\n\n" + body,
        encoding="utf-8",
    )
    return skill_dir


def test_find_skills_root_defaults_to_cwd(tmp_path, monkeypatch):
    """未显式指定根目录时，以启动时的工作目录为项目根。"""
    (tmp_path / ".agentskills").mkdir()
    monkeypatch.chdir(tmp_path)
    assert find_skills_root() == tmp_path / ".agentskills"


def test_find_skills_root_missing_returns_none(tmp_path):
    assert find_skills_root(tmp_path) is None


def test_discover_skill_dirs_only_dirs_with_manifest(tmp_path):
    _write_skill(tmp_path, "alpha", "name: alpha\ndescription: a\n")
    (tmp_path / ".agentskills" / "empty").mkdir()  # 无 SKILL.md，应被忽略
    dirs = discover_skill_dirs(tmp_path)
    assert [p.name for p in dirs] == ["alpha"]


def test_load_skills_reads_name_and_description_only(tmp_path):
    _write_skill(
        tmp_path,
        "greeter",
        "name: greeter\ndescription: 打招呼用\n",
        body="这是一段很长的正文，初始化阶段不应该被加载。",
    )
    registry = load_skills(tmp_path)
    assert registry.names() == ["greeter"]
    skill = registry.get("greeter")
    assert skill.name == "greeter"
    assert skill.description == "打招呼用"
    assert skill.path == tmp_path / ".agentskills" / "greeter"
    # 初始化只读 Frontmatter 元数据，正文必须惰性读取
    assert skill._body is None


def test_body_is_lazy(tmp_path):
    _write_skill(tmp_path, "s", "name: s\ndescription: d\n", body="BODY-TEXT")
    skill = load_skills(tmp_path).get("s")
    assert skill._body is None
    assert skill.body == "BODY-TEXT"
    assert skill._body is not None


def test_block_scalar_description(tmp_path):
    _write_skill(
        tmp_path,
        "writer",
        "name: writer\ndescription: |\n  第一行\n  第二行\n",
    )
    skill = load_skills(tmp_path).get("writer")
    assert skill.description == "第一行\n第二行"


def test_quoted_value_and_inline_comment(tmp_path):
    _write_skill(tmp_path, "q", 'name: "quoted-skill"\ndescription: 带注释的值 # 注释\n')
    skill = load_skills(tmp_path).get("quoted-skill")
    assert skill.description == "带注释的值"


def test_missing_name_and_description_are_skipped_with_warnings(tmp_path):
    _write_skill(tmp_path, "ok", "name: ok\ndescription: fine\n")
    _write_skill(tmp_path, "no_name", "description: 缺 name\n")
    _write_skill(tmp_path, "no_desc", "name: no_desc\n")
    # 真正没有 Frontmatter（不以 --- 开头）的 SKILL.md
    no_fm = tmp_path / ".agentskills" / "no_frontmatter"
    no_fm.mkdir(parents=True)
    (no_fm / "SKILL.md").write_text("没有 frontmatter 的正文\n", encoding="utf-8")

    skills, warnings = discover_skills(tmp_path)
    assert [s.name for s in skills] == ["ok"]
    assert len(warnings) == 3


def test_no_skills_dir_is_not_an_error(tmp_path):
    skills, warnings = discover_skills(tmp_path)
    assert skills == []
    assert warnings == []
    registry = load_skills(tmp_path)
    assert len(registry) == 0


def test_registry_api(tmp_path):
    _write_skill(tmp_path, "a", "name: a\ndescription: A\n")
    _write_skill(tmp_path, "b", "name: b\ndescription: B\n")
    registry = load_skills(tmp_path)
    assert len(registry) == 2
    assert "a" in registry
    assert registry.get("missing") is None
    assert registry.names() == ["a", "b"]
    assert [s.name for s in registry.all()] == ["a", "b"]
    assert registry.summaries() == [
        {"name": "a", "description": "A"},
        {"name": "b", "description": "B"},
    ]
    assert [s.name for s in registry] == ["a", "b"]


def test_custom_dirname(tmp_path):
    skill_dir = tmp_path / ".customskills" / "x"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: x\ndescription: X\n---\n",
        encoding="utf-8",
    )
    registry = load_skills(tmp_path, dirname=".customskills")
    assert registry.names() == ["x"]


def test_build_default_skill_registry(tmp_path):
    _write_skill(tmp_path, "hello", "name: hello\ndescription: say hi\n")
    registry = build_default_skill_registry(project_root=tmp_path)
    assert isinstance(registry, SkillRegistry)
    assert registry.names() == ["hello"]


def test_register_overwrites_by_name(tmp_path):
    _write_skill(tmp_path, "s", "name: s\ndescription: old\n")
    registry = load_skills(tmp_path)
    replaced = SkillSpec(name="s", description="new", path=tmp_path)
    registry.register(replaced)
    assert registry.get("s").description == "new"


def test_register_rejects_empty_name():
    registry = SkillRegistry()
    with pytest.raises(ValueError):
        registry.register(SkillSpec(name="", description="x", path=Path(".")))


def test_build_agent_loads_skills_from_cwd(tmp_path, monkeypatch, settings):
    """tAgent 初始化时，以启动工作目录为根发现并注册 Skill。"""
    _write_skill(tmp_path, "hello", "name: hello\ndescription: say hi\n")
    monkeypatch.chdir(tmp_path)
    agent = build_agent(settings=settings)
    assert agent.skills.names() == ["hello"]


def test_build_skills_prompt_lists_skills(tmp_path):
    _write_skill(tmp_path, "a", "name: a\ndescription: A工具\n")
    _write_skill(tmp_path, "b", "name: b\ndescription: B工具\n")
    prompt = build_skills_prompt(load_skills(tmp_path))
    assert "You have access to the following skills:" in prompt
    assert "'a': A工具" in prompt
    assert "'b': B工具" in prompt
    assert "Use the 'loadSkill' tool to load the full instructions" in prompt


def test_build_skills_prompt_empty_when_no_skills():
    assert build_skills_prompt(SkillRegistry()) == ""


def test_load_skill_tool_loads_body_and_lists(tmp_path):
    _write_skill(tmp_path, "s", "name: s\ndescription: d\n", body="完整指令")
    tool = SkillLoaderTool(load_skills(tmp_path))
    assert tool("s") == "完整指令"
    assert "当前可用技能" in tool("list")
    assert "未找到技能 missing" in tool("missing")


def test_load_skill_tool_empty_registry(tmp_path):
    tool = SkillLoaderTool(SkillRegistry())
    assert tool("anything") == "当前没有可用技能"


def test_build_skill_tools_registers_loadskill(tmp_path):
    _write_skill(tmp_path, "s", "name: s\ndescription: d\n")
    specs = build_skill_tools(load_skills(tmp_path))
    assert [s.name for s in specs] == ["loadSkill"]
    assert specs[0].handler("s") == "# body"


def test_build_agent_injects_skills_and_registers_tool(tmp_path, monkeypatch, settings):
    """build_agent 把 Skill 注入 System Prompt，并注册 loadSkill 工具。"""
    _write_skill(tmp_path, "hello", "name: hello\ndescription: say hi\n")
    monkeypatch.chdir(tmp_path)
    agent = build_agent(settings=settings)
    system = agent.session.system_prompt
    assert "You have access to the following skills:" in system
    assert "'hello': say hi" in system
    assert "loadSkill" in system
    assert LOAD_SKILL_TOOL_NAME in agent.registry.names()


# ------------------------------------------------------------------ loadSkill 附加文件
def _write_skill_file(root: Path, skill: str, relative: str, content: str) -> Path:
    """在 ``root/.agentskills/<skill>/<relative>`` 下写入一个附加文件。"""
    target = root / ".agentskills" / skill / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _make_tool(root: Path) -> SkillLoaderTool:
    _write_skill(root, "s", "name: s\ndescription: d\n", body="SKILL正文")
    return SkillLoaderTool(load_skills(root))


def test_load_skill_with_filename_relative_to_skill_dir(tmp_path):
    _write_skill_file(tmp_path, "s", "notes/usage.md", "用法说明")
    tool = _make_tool(tmp_path)
    assert tool("s", "notes/usage.md") == "用法说明"


def test_load_skill_with_filename_absolute_path(tmp_path):
    target = _write_skill_file(tmp_path, "s", "guide.md", "绝对路径指南")
    tool = _make_tool(tmp_path)
    assert tool("s", str(target)) == "绝对路径指南"


def test_load_skill_with_project_relative_path(tmp_path):
    _write_skill_file(tmp_path, "s", "guide.md", "项目相对路径内容")
    tool = _make_tool(tmp_path)
    assert tool("s", ".agentskills/s/guide.md") == "项目相对路径内容"


def test_load_skill_rejects_path_outside_skill_dir(tmp_path):
    _write_skill(tmp_path, "s", "name: s\ndescription: d\n")
    outside = tmp_path / "secret.txt"
    outside.write_text("机密", encoding="utf-8")
    tool = _make_tool(tmp_path)
    assert "机密" not in tool("s", str(outside))  # 绝对路径越界
    assert "机密" not in tool("s", "../secret.txt")  # 相对技能目录越界


def test_load_skill_bare_filename_recursive_unique(tmp_path):
    _write_skill_file(tmp_path, "s", "docs/deep/README.md", "深层唯一文件")
    tool = _make_tool(tmp_path)
    assert tool("s", "README.md") == "深层唯一文件"


def test_load_skill_bare_filename_multiple_matches_return_candidates(tmp_path):
    _write_skill_file(tmp_path, "s", "a/notes.txt", "CONTENT-A-MARKER-111")
    _write_skill_file(tmp_path, "s", "b/notes.txt", "CONTENT-B-MARKER-222")
    tool = _make_tool(tmp_path)
    result = tool("s", "notes.txt")
    assert "找到多个同名文件" in result
    assert "notes.txt" in result
    # 返回的是候选路径，而不是文件内容
    assert "CONTENT-A-MARKER-111" not in result
    assert "CONTENT-B-MARKER-222" not in result


def test_load_skill_filename_not_found(tmp_path):
    tool = _make_tool(tmp_path)
    assert "未找到文件" in tool("s", "no_such_file.txt")


def test_load_skill_filename_is_skill_md(tmp_path):
    tool = _make_tool(tmp_path)
    # 覆盖 SKILL.md，验证 filename 指向它时读取的是该文件全文
    (tmp_path / ".agentskills" / "s" / "SKILL.md").write_text(
        "这是 SKILL.md 原文", encoding="utf-8"
    )
    assert tool("s", "SKILL.md") == "这是 SKILL.md 原文"


def test_load_skill_name_only_reads_skill_md(tmp_path):
    tool = _make_tool(tmp_path)
    assert tool("s") == "SKILL正文"
    assert tool("s", None) == "SKILL正文"


# ------------------------------------------------------------------ 动态加载原则
def test_skill_body_enters_context_only_via_loadskill(tmp_path):
    """完整内容仅在 LLM 调用 loadSkill 时才进入会话上下文。"""
    import asyncio

    _write_skill(tmp_path, "s", "name: s\ndescription: d\n", body="完整指令内容")
    skill_registry = load_skills(tmp_path)
    tool_registry = ToolRegistry()
    for spec in build_skill_tools(skill_registry):
        tool_registry.register(spec)

    client = FakeLLMClient(
        [tool_events("loadSkill", '{"name": "s"}'), text_events("完成")]
    )
    agent = Agent(
        client=client,
        registry=tool_registry,
        skills=skill_registry,
        max_rounds=3,
        system_prompt="测试",
    )

    # 初始化：上下文只有 name/description，绝不含 Skill 全文
    assert "完整指令内容" not in agent.session.system_prompt
    assert all("完整指令内容" not in m.content for m in agent.history)

    async def collect() -> None:
        async for event in agent.run("go"):
            del event

    asyncio.run(collect())

    # 调用 loadSkill 后，完整指令以工具结果写入会话
    tool_messages = [m for m in agent.history if m.role == "tool"]
    assert tool_messages and "完整指令内容" in tool_messages[-1].content
    # 下一轮模型请求能看到该内容
    assert "完整指令内容" in client.calls[-1][-1]["content"]


def test_build_agent_skills_coexist_with_builtin_tools(tmp_path, monkeypatch, settings):
    """Skill 与 RunCli、文件系统等既有工具共存，Agent 工作流不变。"""
    _write_skill(tmp_path, "hello", "name: hello\ndescription: say hi\n")
    monkeypatch.chdir(tmp_path)
    agent = build_agent(settings=settings)
    names = agent.registry.names()
    assert LOAD_SKILL_TOOL_NAME in names  # 技能工具
    assert "RunCli" in names  # 命令行工具
    assert "read_file" in names  # 文件系统工具
    assert "getdate" in names
    assert agent.skills.names() == ["hello"]

