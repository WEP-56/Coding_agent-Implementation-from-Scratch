"""
Tests for Skill Loader
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from codinggirl.core.skill_loader import Skill, SkillLoader


def test_skill_loader_scans_directory():
    """测试 SkillLoader 扫描目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir)

        # 创建测试技能文件
        (skills_dir / "test-skill.md").write_text(
            """---
name: test-skill
description: A test skill
tags: [test, example]
auto_load: false
---

# Test Skill Content
This is a test skill.
""",
            encoding="utf-8",
        )

        loader = SkillLoader(skills_dir)

        assert len(loader.skills) == 1
        assert "test-skill" in loader.skills


def test_skill_loader_parses_frontmatter():
    """测试解析 frontmatter"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir)

        (skills_dir / "git-workflow.md").write_text(
            """---
name: git-workflow
description: Git best practices
tags: [git, version-control]
auto_load: true
---

# Git Workflow
Content here.
""",
            encoding="utf-8",
        )

        loader = SkillLoader(skills_dir)
        skill = loader.get_skill("git-workflow")

        assert skill is not None
        assert skill.name == "git-workflow"
        assert skill.description == "Git best practices"
        assert skill.tags == ["git", "version-control"]
        assert skill.auto_load is True
        assert "# Git Workflow" in skill.content


def test_skill_loader_handles_no_frontmatter():
    """测试处理没有 frontmatter 的文件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir)

        (skills_dir / "simple.md").write_text(
            """# Simple Skill
Just content, no frontmatter.
""",
            encoding="utf-8",
        )

        loader = SkillLoader(skills_dir)
        skill = loader.get_skill("simple")

        assert skill is not None
        assert skill.name == "simple"
        assert "# Simple Skill" in skill.content


def test_skill_loader_list_skills():
    """测试列出技能摘要"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir)

        (skills_dir / "skill1.md").write_text(
            """---
name: skill1
description: First skill
tags: [tag1]
---
Content 1
""",
            encoding="utf-8",
        )

        (skills_dir / "skill2.md").write_text(
            """---
name: skill2
description: Second skill
tags: [tag2]
---
Content 2
""",
            encoding="utf-8",
        )

        loader = SkillLoader(skills_dir)
        skills_list = loader.list_skills()

        assert len(skills_list) == 2
        assert any(s["name"] == "skill1" for s in skills_list)
        assert any(s["name"] == "skill2" for s in skills_list)


def test_skill_loader_get_auto_load_skills():
    """测试获取自动加载的技能"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir)

        (skills_dir / "auto.md").write_text(
            """---
name: auto
description: Auto-load skill
auto_load: true
---
Content
""",
            encoding="utf-8",
        )

        (skills_dir / "manual.md").write_text(
            """---
name: manual
description: Manual-load skill
auto_load: false
---
Content
""",
            encoding="utf-8",
        )

        loader = SkillLoader(skills_dir)
        auto_skills = loader.get_auto_load_skills()

        assert len(auto_skills) == 1
        assert auto_skills[0].name == "auto"


def test_skill_loader_has_skill():
    """测试检查技能是否存在"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir)

        (skills_dir / "exists.md").write_text("# Content", encoding="utf-8")

        loader = SkillLoader(skills_dir)

        assert loader.has_skill("exists") is True
        assert loader.has_skill("not-exists") is False


def test_skill_loader_empty_directory():
    """测试空目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = SkillLoader(tmpdir)

        assert len(loader.skills) == 0
        assert loader.list_skills() == []


def test_skill_loader_nonexistent_directory():
    """测试不存在的目录"""
    loader = SkillLoader("/nonexistent/path")

    assert len(loader.skills) == 0


def test_real_skills_directory():
    """测试真实的 skills 目录"""
    skills_dir = Path("skills")

    if not skills_dir.exists():
        pytest.skip("skills directory not found")

    loader = SkillLoader(skills_dir)

    # 应该至少有几个技能
    assert len(loader.skills) > 0

    # 检查核心技能是否存在
    expected_skills = ["git-workflow", "testing", "debugging", "code-review"]
    for skill_name in expected_skills:
        if loader.has_skill(skill_name):
            skill = loader.get_skill(skill_name)
            assert skill is not None
            assert len(skill.content) > 0
            assert len(skill.description) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
