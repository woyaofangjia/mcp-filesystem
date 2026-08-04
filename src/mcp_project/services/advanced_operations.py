"""
高级文件操作服务
实现文件监听、比较、合并、批量重命名等高级功能
"""

import asyncio
import difflib
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set
import hashlib

from .errors import MCPError, ErrorCode
from .sandbox import Sandbox


class FileComparator:
    """文件比较器"""
    
    @staticmethod
    def compare_files(file1: Path, file2: Path) -> Dict[str, Any]:
        """比较两个文本文件的内容差异"""
        if not file1.exists() or not file2.exists():
            raise MCPError(ErrorCode.FILE_NOT_FOUND, detail="要比较的文件不存在")
            
        if not file1.is_file() or not file2.is_file():
            raise MCPError(ErrorCode.INVALID_PATH, detail="路径不是文件")
            
        try:
            with open(file1, 'r', encoding='utf-8', errors='ignore') as f1:
                content1 = f1.read()
            with open(file2, 'r', encoding='utf-8', errors='ignore') as f2:
                content2 = f2.read()
                
            lines1 = content1.splitlines(keepends=True)
            lines2 = content2.splitlines(keepends=True)
            
            # 使用difflib比较差异
            differ = difflib.Differ()
            diff_lines = list(differ.compare(lines1, lines2))
            
            # 计算差异统计
            additions = sum(1 for line in diff_lines if line.startswith('+ '))
            deletions = sum(1 for line in diff_lines if line.startswith('- '))
            changes = sum(1 for line in diff_lines if line.startswith('? '))
            
            # 获取差异上下文（前几行）
            diff_context = []
            for i, line in enumerate(diff_lines):
                if not line.startswith('  '):  # 只显示有差异的行
                    diff_context.append(line)
                    if len(diff_context) >= 10:  # 限制显示行数
                        break
                        
            return {
                "file1": str(file1),
                "file2": str(file2),
                "size1": file1.stat().st_size,
                "size2": file2.stat().st_size,
                "identical": content1 == content2,
                "diff_summary": {
                    "additions": additions,
                    "deletions": deletions,
                    "changes": changes,
                    "total_differences": additions + deletions
                },
                "diff_preview": "\n".join(diff_context[:10]),
                "diff_full": "\n".join(diff_lines)
            }
        except (OSError, UnicodeDecodeError) as e:
            raise MCPError(ErrorCode.READ_ERROR, detail=f"比较文件失败: {e}")


class FileMerger:
    """文件合并器"""
    
    @staticmethod
    def merge_files(input_files: List[Path], output_file: Path, separator: str = "\n") -> Dict[str, Any]:
        """合并多个文本文件"""
        if not input_files:
            raise MCPError(ErrorCode.MISSING_PARAMS, detail="输入文件列表不能为空")
            
        for file_path in input_files:
            if not file_path.exists():
                raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"文件不存在: {file_path}")
            if not file_path.is_file():
                raise MCPError(ErrorCode.INVALID_PATH, detail=f"路径不是文件: {file_path}")
                
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        total_size = 0
        merged_content = []
        
        try:
            for i, file_path in enumerate(input_files):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    total_size += len(content)
                    
                    if i > 0:  # 添加分隔符
                        content = separator + content
                    merged_content.append(content)
                    
            # 写入输出文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(''.join(merged_content))
                
            return {
                "output_file": str(output_file),
                "input_files": [str(f) for f in input_files],
                "total_files": len(input_files),
                "total_size": total_size,
                "output_size": output_file.stat().st_size,
                "separator": repr(separator)
            }
        except (OSError, UnicodeDecodeError) as e:
            raise MCPError(ErrorCode.WRITE_ERROR, detail=f"合并文件失败: {e}")


class BatchRenamer:
    """批量重命名器"""
    
    @staticmethod
    def batch_rename(
        directory: Path, 
        pattern: str, 
        replacement: str, 
        regex: bool = False,
        preview_only: bool = False
    ) -> Dict[str, Any]:
        """批量重命名文件"""
        if not directory.exists():
            raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"目录不存在: {directory}")
        if not directory.is_dir():
            raise MCPError(ErrorCode.INVALID_PATH, detail=f"路径不是目录: {directory}")
            
        renamed_files = []
        failed_files = []
        
        try:
            for file_path in directory.iterdir():
                if not file_path.is_file():
                    continue
                    
                old_name = file_path.name
                
                if regex:
                    try:
                        new_name = re.sub(pattern, replacement, old_name)
                    except re.error as e:
                        failed_files.append({
                            "file": str(file_path),
                            "error": f"正则表达式错误: {e}"
                        })
                        continue
                else:
                    # 简单字符串替换
                    new_name = old_name.replace(pattern, replacement)
                    
                # 如果名称没有变化，跳过
                if new_name == old_name:
                    continue
                    
                new_path = file_path.parent / new_name
                
                # 检查新文件是否已存在
                if new_path.exists():
                    failed_files.append({
                        "file": str(file_path),
                        "new_name": new_name,
                        "error": "目标文件已存在"
                    })
                    continue
                    
                # 执行重命名（如果不需要预览）
                if not preview_only:
                    try:
                        file_path.rename(new_path)
                        renamed_files.append({
                            "old_name": old_name,
                            "new_name": new_name,
                            "old_path": str(file_path),
                            "new_path": str(new_path)
                        })
                    except OSError as e:
                        failed_files.append({
                            "file": str(file_path),
                            "error": f"重命名失败: {e}"
                        })
                else:
                    # 预览模式，只记录将要进行的操作
                    renamed_files.append({
                        "old_name": old_name,
                        "new_name": new_name,
                        "old_path": str(file_path),
                        "new_path": str(new_path),
                        "preview": True
                    })
                    
            return {
                "directory": str(directory),
                "pattern": pattern,
                "replacement": replacement,
                "regex": regex,
                "preview_only": preview_only,
                "renamed_files": renamed_files,
                "failed_files": failed_files,
                "total_renamed": len(renamed_files),
                "total_failed": len(failed_files)
            }
        except Exception as e:
            raise MCPError(ErrorCode.WRITE_ERROR, detail=f"批量重命名失败: {e}")


class ContentAnalyzer:
    """内容分析器"""
    
    @staticmethod
    def analyze_file_content(file_path: Path) -> Dict[str, Any]:
        """分析文本文件内容"""
        if not file_path.exists():
            raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"文件不存在: {file_path}")
        if not file_path.is_file():
            raise MCPError(ErrorCode.INVALID_PATH, detail=f"路径不是文件: {file_path}")
            
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            lines = content.splitlines()
            
            # 统计信息
            char_count = len(content)
            line_count = len(lines)
            word_count = sum(len(line.split()) for line in lines)
            
            # 计算代码统计（针对常见编程语言）
            comment_lines = 0
            blank_lines = 0
            code_lines = 0
            
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    blank_lines += 1
                elif stripped.startswith(('#', '//', '/*', '*/', '--', 'REM')):
                    comment_lines += 1
                else:
                    code_lines += 1
            
            # 检测可能的编码问题
            encoding_issues = False
            try:
                content.encode('utf-8')
            except UnicodeEncodeError:
                encoding_issues = True
                
            # 检测可能的编程语言（基于文件扩展名）
            ext = file_path.suffix.lower()
            language_map = {
                '.py': 'Python',
                '.js': 'JavaScript',
                '.ts': 'TypeScript',
                '.java': 'Java',
                '.cpp': 'C++',
                '.c': 'C',
                '.cs': 'C#',
                '.php': 'PHP',
                '.rb': 'Ruby',
                '.go': 'Go',
                '.rs': 'Rust',
                '.swift': 'Swift',
                '.sql': 'SQL',
                '.html': 'HTML',
                '.css': 'CSS',
                '.md': 'Markdown',
                '.json': 'JSON',
                '.xml': 'XML',
                '.yaml': 'YAML',
                '.yml': 'YAML',
                '.toml': 'TOML',
                '.ini': 'INI',
                '.cfg': 'INI'
            }
            
            language = language_map.get(ext, 'Unknown')
            
            return {
                "file": str(file_path),
                "size_bytes": file_path.stat().st_size,
                "character_count": char_count,
                "line_count": line_count,
                "word_count": word_count,
                "code_analysis": {
                    "code_lines": code_lines,
                    "comment_lines": comment_lines,
                    "blank_lines": blank_lines,
                    "total_lines": line_count,
                    "comment_ratio": comment_lines / line_count if line_count > 0 else 0,
                    "code_ratio": code_lines / line_count if line_count > 0 else 0
                },
                "encoding_issues": encoding_issues,
                "detected_language": language,
                "file_extension": ext
            }
        except (OSError, UnicodeDecodeError) as e:
            raise MCPError(ErrorCode.READ_ERROR, detail=f"分析文件内容失败: {e}")


class DuplicateFinder:
    """重复文件检测器"""
    
    @staticmethod
    def find_duplicates(directory: Path, check_content: bool = True, min_size: int = 1024) -> Dict[str, Any]:
        """查找目录中的重复文件"""
        if not directory.exists():
            raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"目录不存在: {directory}")
        if not directory.is_dir():
            raise MCPError(ErrorCode.INVALID_PATH, detail=f"路径不是目录: {directory}")
            
        try:
            # 收集文件信息
            file_groups: Dict[str, List[Path]] = {}
            total_files = 0
            skipped_files = []
            
            for file_path in directory.rglob("*"):
                if not file_path.is_file():
                    continue
                    
                total_files += 1
                file_size = file_path.stat().st_size
                
                # 跳过小文件
                if file_size < min_size:
                    skipped_files.append({
                        "file": str(file_path),
                        "reason": f"文件大小小于 {min_size} 字节"
                    })
                    continue
                    
                if check_content:
                    # 计算文件哈希
                    try:
                        file_hash = DuplicateFinder._calculate_file_hash(file_path)
                        if file_hash not in file_groups:
                            file_groups[file_hash] = []
                        file_groups[file_hash].append(file_path)
                    except (OSError, PermissionError):
                        skipped_files.append({
                            "file": str(file_path),
                            "reason": "无法计算文件哈希（权限或IO错误）"
                        })
                else:
                    # 只检查文件名和大小
                    key = f"{file_path.name}_{file_size}"
                    if key not in file_groups:
                        file_groups[key] = []
                    file_groups[key].append(file_path)
            
            # 找出重复文件（组中文件数 > 1）
            duplicates = []
            duplicate_size_saved = 0
            
            for group_key, files in file_groups.items():
                if len(files) > 1:
                    duplicate_group = {
                        "group_key": group_key,
                        "files": [str(f) for f in files],
                        "count": len(files),
                        "size_bytes": files[0].stat().st_size if files else 0
                    }
                    duplicates.append(duplicate_group)
                    duplicate_size_saved += (len(files) - 1) * files[0].stat().st_size
            
            return {
                "directory": str(directory),
                "check_content": check_content,
                "min_size": min_size,
                "total_files_scanned": total_files,
                "duplicate_groups": len(duplicates),
                "duplicate_files": sum(g["count"] for g in duplicates),
                "potential_space_saved": duplicate_size_saved,
                "skipped_files": skipped_files,
                "duplicates": duplicates
            }
        except Exception as e:
            raise MCPError(ErrorCode.READ_ERROR, detail=f"查找重复文件失败: {e}")
    
    @staticmethod
    def _calculate_file_hash(file_path: Path, chunk_size: int = 8192) -> str:
        """计算文件的哈希值"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()


def get_file_comparator() -> FileComparator:
    """获取文件比较器实例"""
    return FileComparator()


def get_file_merger() -> FileMerger:
    """获取文件合并器实例"""
    return FileMerger()


def get_batch_renamer() -> BatchRenamer:
    """获取批量重命名器实例"""
    return BatchRenamer()


def get_content_analyzer() -> ContentAnalyzer:
    """获取内容分析器实例"""
    return ContentAnalyzer()


def get_duplicate_finder() -> DuplicateFinder:
    """获取重复文件检测器实例"""
    return DuplicateFinder()


__all__ = [
    "FileComparator", "FileMerger", "BatchRenamer", "ContentAnalyzer", "DuplicateFinder",
    "get_file_comparator", "get_file_merger", "get_batch_renamer", 
    "get_content_analyzer", "get_duplicate_finder"
]