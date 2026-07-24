"""帮助文档端点 — 将 docs/ 目录下的 Markdown 文件转换为 HTML 返回给前端"""
from __future__ import annotations

import html
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.deps import get_current_active_player
from app.models.player import Player, UserRole

router = APIRouter()

# docs 目录路径：
#   Docker 镜像中 __file__ = /app/app/api/v1/endpoints/…，5 级 parent = /app，docs = /app/docs
#   本地开发中  __file__ = …/backend/app/api/v1/endpoints/…，5 级 parent = backend/，需再上一级到项目根
_DOCS_DIR = Path(__file__).parent.parent.parent.parent.parent / "docs"
if not _DOCS_DIR.exists():
    _DOCS_DIR = Path(__file__).parent.parent.parent.parent.parent.parent / "docs"

_MANUALS_DIR = _DOCS_DIR / "manuals"

_DOC_FILES = {
    "admin": "solarc-ultimate-管理员手册.md",
    "member": "solarc-ultimate-队员用户手册.md",
}


def _markdown_to_html(text: str) -> str:
    """极简 Markdown → HTML 转换（仅用于显示，无需完整实现）"""
    lines = text.split("\n")
    out: list[str] = []
    in_list = False
    in_code = False

    for line in lines:
        # 代码块
        if line.strip().startswith("```"):
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                in_code = True
                out.append("<pre><code>")
            continue
        if in_code:
            out.append(html.escape(line))
            continue

        # 标题
        h3 = re.match(r"^### (.+)", line)
        h2 = re.match(r"^## (.+)", line)
        h1 = re.match(r"^# (.+)", line)
        if h1:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h1>{html.escape(h1.group(1))}</h1>")
        elif h2:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h2>{html.escape(h2.group(1))}</h2>")
        elif h3:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h3>{html.escape(h3.group(1))}</h3>")
        # 列表项
        elif re.match(r"^[-*] (.+)", line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = re.sub(r"^[-*] ", "", line)
            out.append(f"<li>{_inline(item)}</li>")
        elif re.match(r"^\d+\. (.+)", line):
            if not in_list:
                out.append("<ol>")
                in_list = True
            item = re.sub(r"^\d+\. ", "", line)
            out.append(f"<li>{_inline(item)}</li>")
        # 空行
        elif line.strip() == "":
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append("<br/>")
        # 普通段落
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<p>{_inline(line)}</p>")

    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _inline(text: str) -> str:
    """处理内联格式：加粗、代码、转义"""
    text = html.escape(text)
    # **bold**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # *italic*
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # `code`
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


@router.get("/{doc_type}")
async def get_help_doc(
    doc_type: str,
    current_player: Player = Depends(get_current_active_player),
):
    """返回帮助手册 HTML 内容。doc_type: admin | member"""
    if doc_type not in _DOC_FILES:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 非管理员只能看队员手册
    is_admin = current_player.is_superadmin or current_player.role in (UserRole.admin, UserRole.owner)
    if doc_type == "admin" and not is_admin:
        raise HTTPException(status_code=403, detail="无权查看管理员手册")

    doc_path = _MANUALS_DIR / _DOC_FILES[doc_type]
    if not doc_path.exists():
        raise HTTPException(status_code=404, detail="手册文件未找到")

    text = doc_path.read_text(encoding="utf-8")
    html_content = _markdown_to_html(text)
    return {"html": html_content}
