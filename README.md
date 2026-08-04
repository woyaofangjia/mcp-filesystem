# 文件系统MCP服务器

一个适合初学者的文件系统MCP服务器，提供基本的文件操作功能。

## 功能

1. **列出目录内容** - 查看指定目录下的文件和文件夹
2. **读取文件内容** - 读取文本文件的内容
3. **写入文件** - 创建或修改文本文件
4. **文件信息** - 获取文件的详细信息（大小、创建时间等）
5. **搜索文件** - 在目录中搜索文件

## 安装

```bash
# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate

# 安装依赖
pip install -e .
```

## 使用

### 启动MCP服务器
```bash
python server.py
```

### 使用客户端测试
```bash
python client.py
```

### 与Claude Desktop集成
将以下配置添加到Claude Desktop的MCP设置中：

```json
{
  "mcpServers": {
    "filesystem-server": {
      "command": "python",
      "args": ["server.py"],
      "env": {}
    }
  }
}
```

## 项目结构

```
mcp-project/
├── src/mcp_project/
│   └── __init__.py
├── client.py          # MCP客户端测试代码
├── server.py         # MCP服务器主文件
├── pyproject.toml    # 项目配置和依赖
└── README.md         # 项目说明
```

## 工具列表

1. **list_directory** - 列出目录内容
2. **read_file** - 读取文件内容
3. **write_file** - 写入文件内容
4. **get_file_info** - 获取文件信息
5. **search_files** - 搜索文件

## 示例用法

在Claude中可以使用以下命令：
- "列出当前目录的内容"
- "读取README.md文件的内容"
- "创建test.txt文件并写入内容"
- "搜索包含'python'的文件"
- "获取server.py文件的详细信息"

## 开发说明

这是一个初学者友好的MCP服务器项目，适合学习MCP协议的基础概念和实现。所有功能都基于Python标准库，无需外部依赖。

## 许可证

MIT License