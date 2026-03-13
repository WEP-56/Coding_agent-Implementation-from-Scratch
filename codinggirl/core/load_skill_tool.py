"""
Load Skill Tool - 按需加载技能文档

允许 agent 加载领域知识
"""
from __future__ import annotations

from typing import Any

from codinggirl.core.skill_loader import SkillLoader
from codinggirl.runtime.tools.registry import ToolSpec


def create_load_skill_tool_spec() -> ToolSpec:
    """创建 load_skill 工具规范"""
    return ToolSpec(
        name="load_skill",
        description=(
            "Load a skill document with domain-specific knowledge and best practices. "
            "Use this when you need guidance on specific topics.\n\n"
            "Available skills will be listed in the system prompt. "
            "Common skills include:\n"
            "- git-workflow: Git operations, commit messages, PR workflow\n"
            "- testing: Test strategies, framework selection, coverage\n"
            "- debugging: Diagnostic steps, common issues, profiling\n"
            "- code-review: Review checklist, security, performance\n"
            "- python-best-practices: Type hints, patterns, error handling\n\n"
            "Once loaded, the skill content will be available in your context."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Name of the skill to load (e.g., 'git-workflow', 'testing')",
                }
            },
            "required": ["skill_name"],
        },
        risk_level="low",
        required_permission=None,
    )


def create_load_skill_handler(skill_loader: SkillLoader) -> callable:
    """
    创建 load_skill 工具处理器

    Args:
        skill_loader: SkillLoader 实例
    """

    def handler(skill_name: str) -> dict[str, Any]:
        """加载技能"""
        skill = skill_loader.get_skill(skill_name)

        if not skill:
            available = ", ".join(s["name"] for s in skill_loader.list_skills())
            return {
                "ok": False,
                "error": f"Skill '{skill_name}' not found. Available skills: {available}",
            }

        return {
            "ok": True,
            "skill_name": skill.name,
            "description": skill.description,
            "content": skill.content,
            "message": f"Loaded skill: {skill.name}",
        }

    return handler
