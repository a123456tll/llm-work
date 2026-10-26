"""组装根（Composition Root）。

前端只从这里获取"可用的 Agent 实例"，不需要知道 LLM 客户端、工具注册中心
与会话是如何拼装起来的。更换模型服务商或新增工具时只需改动本文件。
"""

from __future__ import annotations

from core.agent import Agent
from core.config import Settings, load_settings
from core.llm.client import LLMClient
from core.llm.openai_client import OpenAICompatibleClient
from core.session import Session
from core.tools.base import ToolSpec
from core.tools.builtin.cli_tools import build_cli_tools
from core.tools.builtin.datetime_tools import build_datetime_tools
from core.tools.builtin.fetch_web import build_fetch_tools
from core.tools.builtin.filesystem_tools import build_filesystem_tools
from core.tools.builtin.web_search import build_search_tools
from core.tools.registry import ToolRegistry


def build_default_registry(settings: Settings | None = None) -> ToolRegistry:
    """构造内置工具集合（日期时间 + 文件系统 + 网络搜索 + 网页抓取 + 本地 CLI）。"""
    registry = ToolRegistry()
    search_settings = settings.search if settings is not None else None
    tools = (
        build_datetime_tools()
        + build_filesystem_tools()
        + build_search_tools(search_settings)
        + build_fetch_tools()
        + build_cli_tools()
    )
    for tool in tools:
        registry.register(tool)
    return registry


def build_client(settings: Settings) -> LLMClient:
    """根据配置构造 LLM 客户端。"""
    return OpenAICompatibleClient(
        base_url=settings.llm.base_url,
        api_key=settings.llm.api_key,
        model=settings.llm.model,
        timeout=settings.llm.timeout,
    )


def build_agent(
    settings: Settings | None = None,
    *,
    client: LLMClient | None = None,
    registry: ToolRegistry | None = None,
    session: Session | None = None,
    extra_tools: list[ToolSpec] | None = None,
) -> Agent:
    """构造一个开箱即用的 Agent。

    参数全部可选：未显式提供时使用配置文件 + 内置工具 + 新会话。
    """
    resolved = settings if settings is not None else load_settings()
    tool_registry = registry if registry is not None else build_default_registry(resolved)
    for tool in extra_tools or []:
        tool_registry.register(tool)

    llm_client = client if client is not None else build_client(resolved)
    conversation = (
        session
        if session is not None
        else Session(system_prompt=resolved.system_prompt, session_id="default")
    )
    return Agent(
        client=llm_client,
        registry=tool_registry,
        session=conversation,
        max_rounds=resolved.max_tool_rounds,
        system_prompt=resolved.system_prompt,
    )


__all__ = ["build_agent", "build_client", "build_default_registry"]
