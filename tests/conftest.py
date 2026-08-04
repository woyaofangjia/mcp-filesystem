"""pytest 配置和公共 fixtures"""
import os
import sys
import tempfile
import shutil
from pathlib import Path

import pytest

# 确保项目根目录在 path 中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_workspace(tmp_path):
    """临时工作目录，测试结束后自动清理"""
    yield tmp_path


@pytest.fixture
def sample_text_file(tmp_path):
    """创建临时文本文件"""
    f = tmp_path / "sample.txt"
    f.write_text("Hello World\nLine 2\nLine 3", encoding="utf-8")
    return f


@pytest.fixture
def sample_python_file(tmp_path):
    """创建临时Python文件"""
    f = tmp_path / "test_code.py"
    f.write_text(
        "#!/usr/bin/env python3\n"
        "'''docstring'''\n"
        "import os\n"
        "\n"
        "# 这是一个注释\n"
        "def hello():\n"
        "    print('hello')\n"
        "\n"
        "class Foo:\n"
        "    pass\n",
        encoding="utf-8",
    )
    return f


@pytest.fixture
def sandbox(tmp_path):
    """沙箱实例，限定在临时目录"""
    from src.mcp_project.services.sandbox import Sandbox
    return Sandbox(allowed_roots=[str(tmp_path)])
