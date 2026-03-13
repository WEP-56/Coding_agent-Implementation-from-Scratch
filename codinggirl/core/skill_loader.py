"""
Skill Loader - 技能加载器

按需加载领域知识，避免 system prompt 膨胀
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Skill:
    """技能定义"""

    name: str
    description: str
    tags: list[str]
    content: str
    auto_load: bool = False


class SkillLoader:
    """
    Skill Loader - 扫描和加载技能文档

    技能文件格式（YAML frontmatter + Markdown）：
    ---
    name: git-workflow
    description: Git commit, branch, and PR best practices
    tags: [git, version-control]
    auto_load: false
    ---

    # Git Workflow Best Practices
    ...
    """

    def __init__(self, skills_dir: str | Path):
        self.skills_dir = Path(skills_dir)
        self.skills: dict[str, Skill] = {}
        self._scan_skills()

    def _scan_skills(self) -> None:
        """扫描 skills/ 目录，解析所有技能"""
        if not self.skills_dir.exists():
            return

        for file in self.skills_dir.glob("*.md"):
            try:
                skill = self._parse_skill_file(file)
                self.skills[skill.name] = skill
            except Exception as e:
                # 跳过解析失败的文件
                print(f"Warning: Failed to parse skill file {file}: {e}")

    def _parse_skill_file(self, file_path: Path) -> Skill:
        """
        解析技能文件

        格式：
        ---
        name: skill-name
        description: Short description
        tags: [tag1, tag2]
        auto_load: false
        ---

        # Skill Content
        ...
        """
        content = file_path.read_text(encoding="utf-8")

        # 提取 frontmatter
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)

        if not frontmatter_match:
            # 没有 frontmatter，使用文件名作为 name
            return Skill(
                name=file_path.stem,
                description=f"Skill from {file_path.name}",
                tags=[],
                content=content,
                auto_load=False,
            )

        frontmatter_text = frontmatter_match.group(1)
        body = frontmatter_match.group(2)

        # 解析 frontmatter（简单的 YAML 解析）
        metadata = self._parse_frontmatter(frontmatter_text)

        return Skill(
            name=metadata.get("name", file_path.stem),
            description=metadata.get("description", ""),
            tags=metadata.get("tags", []),
            content=body.strip(),
            auto_load=metadata.get("auto_load", False),
        )

    def _parse_frontmatter(self, text: str) -> dict[str, Any]:
        """
        简单的 YAML frontmatter 解析

        支持：
        - name: value
        - tags: [tag1, tag2]
        - auto_load: true/false
        """
        metadata: dict[str, Any] = {}

        for line in text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            # 解析列表 [tag1, tag2]
            if value.startswith("[") and value.endswith("]"):
                items = value[1:-1].split(",")
                metadata[key] = [item.strip() for item in items]
            # 解析布尔值
            elif value.lower() in ("true", "false"):
                metadata[key] = value.lower() == "true"
            # 字符串
            else:
                metadata[key] = value

        return metadata

    def get_skill(self, name: str) -> Skill | None:
        """获取技能完整内容"""
        return self.skills.get(name)

    def list_skills(self) -> list[dict[str, Any]]:
        """返回技能摘要列表（用于 system prompt）"""
        return [
            {
                "name": s.name,
                "description": s.description,
                "tags": s.tags,
                "auto_load": s.auto_load,
            }
            for s in self.skills.values()
        ]

    def get_auto_load_skills(self) -> list[Skill]:
        """获取需要自动加载的技能"""
        return [s for s in self.skills.values() if s.auto_load]

    def has_skill(self, name: str) -> bool:
        """检查技能是否存在"""
        return name in self.skills
