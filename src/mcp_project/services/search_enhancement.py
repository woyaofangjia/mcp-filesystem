"""
搜索增强服务
实现全文搜索、正则搜索、模糊搜索、索引搜索等高级搜索功能
"""

import os
import re
import hashlib
import fnmatch
import difflib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set
import threading
import time
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from .errors import MCPError, ErrorCode


@dataclass
class SearchResult:
    """搜索结果"""
    file_path: str
    matches: List[Dict[str, Any]]
    relevance: float = 0.0
    metadata: Optional[Dict[str, Any]] = None


class EnhancedSearcher:
    """增强搜索器"""
    
    def __init__(self, max_results: int = 1000, max_file_size: int = 10 * 1024 * 1024):
        self.max_results = max_results
        self.max_file_size = max_file_size
        self.text_extensions = {
            '.txt', '.md', '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.hpp',
            '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.sql', '.html', '.css',
            '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.properties',
            '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd'
        }
    
    def full_text_search(
        self, 
        directory: Path, 
        query: str, 
        case_sensitive: bool = False,
        whole_word: bool = False,
        file_pattern: Optional[str] = None
    ) -> Dict[str, Any]:
        """全文搜索"""
        if not directory.exists():
            raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"目录不存在: {directory}")
        if not directory.is_dir():
            raise MCPError(ErrorCode.INVALID_PATH, detail=f"路径不是目录: {directory}")
            
        results: List[SearchResult] = []
        files_processed = 0
        total_matches = 0
        
        # 构建搜索模式
        if whole_word:
            search_pattern = f"\\b{re.escape(query)}\\b"
        else:
            search_pattern = re.escape(query)
            
        flags = 0 if case_sensitive else re.IGNORECASE
        
        try:
            search_regex = re.compile(search_pattern, flags)
            
            # 遍历文件
            for file_path in directory.rglob("*"):
                if not file_path.is_file():
                    continue
                    
                # 检查文件大小限制
                try:
                    file_size = file_path.stat().st_size
                    if file_size > self.max_file_size:
                        continue
                except OSError:
                    continue
                    
                # 检查文件扩展名（只搜索文本文件）
                ext = file_path.suffix.lower()
                if ext not in self.text_extensions:
                    continue
                    
                # 检查文件模式
                if file_pattern and not fnmatch.fnmatch(file_path.name, file_pattern):
                    continue
                    
                files_processed += 1
                
                try:
                    # 读取文件内容
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                    # 搜索匹配
                    matches = []
                    for match in search_regex.finditer(content):
                        matches.append({
                            "position": match.start(),
                            "line": content[:match.start()].count('\n') + 1,
                            "matched_text": match.group(),
                            "context": self._get_context(content, match.start(), match.end())
                        })
                        total_matches += 1
                        
                        # 限制每个文件的匹配数量
                        if len(matches) >= 50:
                            break
                            
                    if matches:
                        # 计算相关性分数
                        relevance = self._calculate_relevance(
                            len(matches), 
                            file_size,
                            query,
                            content
                        )
                        
                        result = SearchResult(
                            file_path=str(file_path),
                            matches=matches[:10],  # 只保留前10个匹配
                            relevance=relevance,
                            metadata={
                                "size_bytes": file_size,
                                "total_matches_in_file": len(matches),
                                "extension": ext
                            }
                        )
                        results.append(result)
                        
                        # 限制总结果数量
                        if len(results) >= self.max_results:
                            break
                except (OSError, UnicodeDecodeError):
                    continue
        
        except re.error as e:
            raise MCPError(ErrorCode.INVALID_PARAMS, detail=f"搜索模式错误: {e}")
            
        # 按相关性排序
        results.sort(key=lambda x: x.relevance, reverse=True)
        
        return {
            "directory": str(directory),
            "query": query,
            "case_sensitive": case_sensitive,
            "whole_word": whole_word,
            "files_processed": files_processed,
            "files_with_matches": len(results),
            "total_matches": total_matches,
            "results": [
                {
                    "file": r.file_path,
                    "matches": r.matches,
                    "relevance": round(r.relevance, 3),
                    "metadata": r.metadata
                }
                for r in results[:100]  # 限制返回结果数
            ]
        }
    
    def regex_search(
        self,
        directory: Path,
        pattern: str,
        file_pattern: Optional[str] = None
    ) -> Dict[str, Any]:
        """正则表达式搜索"""
        if not directory.exists():
            raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"目录不存在: {directory}")
        if not directory.is_dir():
            raise MCPError(ErrorCode.INVALID_PATH, detail=f"路径不是目录: {directory}")
            
        results: List[SearchResult] = []
        files_processed = 0
        total_matches = 0
        
        try:
            search_regex = re.compile(pattern, re.DOTALL)
            
            for file_path in directory.rglob("*"):
                if not file_path.is_file():
                    continue
                    
                try:
                    file_size = file_path.stat().st_size
                    if file_size > self.max_file_size:
                        continue
                except OSError:
                    continue
                    
                ext = file_path.suffix.lower()
                if ext not in self.text_extensions:
                    continue
                    
                if file_pattern and not fnmatch.fnmatch(file_path.name, file_pattern):
                    continue
                    
                files_processed += 1
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                    matches = []
                    for match in search_regex.finditer(content):
                        matches.append({
                            "position": match.start(),
                            "line": content[:match.start()].count('\n') + 1,
                            "matched_text": match.group(),
                            "context": self._get_context(content, match.start(), match.end()),
                            "groups": list(match.groups()) if match.groups() else []
                        })
                        total_matches += 1
                        
                        if len(matches) >= 50:
                            break
                            
                    if matches:
                        relevance = self._calculate_regex_relevance(
                            len(matches),
                            file_size,
                            pattern,
                            content
                        )
                        
                        result = SearchResult(
                            file_path=str(file_path),
                            matches=matches[:10],
                            relevance=relevance,
                            metadata={
                                "size_bytes": file_size,
                                "total_matches_in_file": len(matches),
                                "extension": ext
                            }
                        )
                        results.append(result)
                        
                        if len(results) >= self.max_results:
                            break
                except (OSError, UnicodeDecodeError):
                    continue
                    
        except re.error as e:
            raise MCPError(ErrorCode.INVALID_PARAMS, detail=f"正则表达式错误: {e}")
            
        results.sort(key=lambda x: x.relevance, reverse=True)
        
        return {
            "directory": str(directory),
            "pattern": pattern,
            "files_processed": files_processed,
            "files_with_matches": len(results),
            "total_matches": total_matches,
            "regex_results": results[:100]
        }
    
    def fuzzy_search(
        self,
        directory: Path,
        query: str,
        similarity_threshold: float = 0.8,
        file_pattern: Optional[str] = None
    ) -> Dict[str, Any]:
        """模糊搜索（支持拼写错误的匹配）"""
        if not directory.exists():
            raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"目录不存在: {directory}")
        if not directory.is_dir():
            raise MCPError(ErrorCode.INVALID_PATH, detail=f"路径不是目录: {directory}")
            
        results: List[Dict[str, Any]] = []
        files_processed = 0
        
        # 将查询转换为小写用于模糊匹配
        query_lower = query.lower()
        
        for file_path in directory.rglob("*"):
            if not file_path.is_file():
                continue
                
            try:
                file_size = file_path.stat().st_size
                if file_size > self.max_file_size:
                    continue
            except OSError:
                continue
                
            # 检查文件名
            if file_pattern and not fnmatch.fnmatch(file_path.name, file_pattern):
                continue
                
            files_processed += 1
            
            # 检查文件名模糊匹配
            filename_lower = file_path.name.lower()
            if filename_lower == query_lower:
                # 完全匹配
                similarity = 1.0
            else:
                # 计算相似度
                similarity = difflib.SequenceMatcher(
                    None, filename_lower, query_lower
                ).ratio()
                
            if similarity >= similarity_threshold:
                results.append({
                    "file": str(file_path),
                    "filename": file_path.name,
                    "similarity": round(similarity, 3),
                    "type": "filename_match",
                    "metadata": {
                        "size_bytes": file_size,
                        "extension": file_path.suffix.lower()
                    }
                })
            
            # 如果是文本文件，检查内容模糊匹配
            if file_path.suffix.lower() in self.text_extensions:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        
                    # 简单的分词和模糊匹配
                    words = content.split()
                    for word in set(words):  # 去重
                        if len(word) > 2:  # 忽略短词
                            word_similarity = difflib.SequenceMatcher(
                                None, word, query_lower
                            ).ratio()
                            
                            if word_similarity >= similarity_threshold:
                                results.append({
                                    "file": str(file_path),
                                    "word": word,
                                    "similarity": round(word_similarity, 3),
                                    "type": "content_word_match",
                                    "metadata": {
                                        "size_bytes": file_size,
                                        "extension": file_path.suffix.lower()
                                    }
                                })
                                break  # 每个文件只记录一次内容匹配
                except (OSError, UnicodeDecodeError):
                    continue
                
            # 限制结果数量
            if len(results) >= self.max_results:
                break
        
        # 按相似度排序
        results.sort(key=lambda x: x["similarity"], reverse=True)
        
        return {
            "directory": str(directory),
            "query": query,
            "similarity_threshold": similarity_threshold,
            "files_processed": files_processed,
            "total_matches": len(results),
            "fuzzy_results": results[:100]
        }
    
    def advanced_search(
        self,
        directory: Path,
        query: str,
        file_types: Optional[List[str]] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        modified_after: Optional[str] = None,
        modified_before: Optional[str] = None
    ) -> Dict[str, Any]:
        """多条件高级搜索"""
        if not directory.exists():
            raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"目录不存在: {directory}")
        if not directory.is_dir():
            raise MCPError(ErrorCode.INVALID_PATH, detail=f"路径不是目录: {directory}")
            
        results: List[Dict[str, Any]] = []
        files_processed = 0
        
        query_lower = query.lower()
        
        for file_path in directory.rglob("*"):
            if not file_path.is_file():
                continue
                
            files_processed += 1
            
            try:
                stat_info = file_path.stat()
                file_size = stat_info.st_size
                
                # 检查文件类型
                if file_types:
                    ext = file_path.suffix.lower()
                    if ext not in file_types:
                        continue
                
                # 检查文件大小
                if min_size is not None and file_size < min_size:
                    continue
                if max_size is not None and file_size > max_size:
                    continue
                
                # 检查修改时间
                if modified_after:
                    try:
                        after_dt = datetime.fromisoformat(modified_after.replace('Z', '+00:00'))
                        if stat_info.st_mtime < after_dt.timestamp():
                            continue
                    except ValueError:
                        raise MCPError(ErrorCode.INVALID_PARAMS, detail=f"无效的修改时间格式: {modified_after}")
                
                if modified_before:
                    try:
                        before_dt = datetime.fromisoformat(modified_before.replace('Z', '+00:00'))
                        if stat_info.st_mtime > before_dt.timestamp():
                            continue
                    except ValueError:
                        raise MCPError(ErrorCode.INVALID_PARAMS, detail=f"无效的修改时间格式: {modified_before}")
                
                # 检查文件名匹配
                filename_match = query_lower in file_path.name.lower()
                
                # 检查文件内容匹配（如果是文本文件）
                content_match = False
                if file_path.suffix.lower() in self.text_extensions:
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                        content_match = query_lower in content
                    except (OSError, UnicodeDecodeError):
                        pass
                
                if filename_match or content_match:
                    results.append({
                        "file": str(file_path),
                        "filename_match": filename_match,
                        "content_match": content_match,
                        "size_bytes": file_size,
                        "modified_time": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                        "extension": file_path.suffix.lower()
                    })
                
                if len(results) >= self.max_results:
                    break
                    
            except OSError:
                continue
        
        return {
            "directory": str(directory),
            "query": query,
            "filters": {
                "file_types": file_types,
                "min_size": min_size,
                "max_size": max_size,
                "modified_after": modified_after,
                "modified_before": modified_before
            },
            "files_processed": files_processed,
            "total_matches": len(results),
            "advanced_results": results
        }
    
    def _get_context(self, content: str, start: int, end: int, context_chars: int = 100) -> str:
        """获取匹配内容的上下文"""
        context_start = max(0, start - context_chars)
        context_end = min(len(content), end + context_chars)
        
        # 提取上下文并确保在单词边界处
        context = content[context_start:context_end]
        
        # 如果不是开头，向前找到最近的空格或换行
        if context_start > 0:
            for i in range(start - context_start, 0, -1):
                if context[i] in (' ', '\n', '\t', '\r'):
                    context = context[i + 1:]
                    break
        
        # 如果不是结尾，向后找到最近的空格或换行
        if context_end < len(content):
            for i in range(end - context_start, len(context)):
                if context[i] in (' ', '\n', '\t', '\r'):
                    context = context[:i]
                    break
        
        # 高亮匹配部分
        match_start = start - context_start
        match_end = end - context_start
        
        # 调整位置以适应修剪后的上下文
        match_start = max(0, match_start)
        match_end = min(len(context), match_end)
        
        if match_end > match_start:
            highlighted = (
                context[:match_start] +
                ">>>" + context[match_start:match_end] + "<<<" +
                context[match_end:]
            )
            return highlighted
        
        return context
    
    def _calculate_relevance(self, match_count: int, file_size: int, 
                           query: str, content: str) -> float:
        """计算搜索结果相关性分数"""
        if match_count == 0 or file_size == 0:
            return 0.0
        
        # 基本分数：匹配密度
        density_score = min(match_count / (file_size / 1000), 1.0)
        
        # 文件大小惩罚：小文件可能相关性更高
        size_score = 1.0 / (1.0 + (file_size / (1024 * 1024)))  # MB单位
        
        # 查询长度权重：长查询可能更具体
        query_length_score = min(len(query) / 10, 1.0)
        
        # 组合分数
        relevance = (density_score * 0.5 + size_score * 0.3 + query_length_score * 0.2)
        
        return relevance * 100  # 转换为百分比
    
    def _calculate_regex_relevance(self, match_count: int, file_size: int,
                                 pattern: str, content: str) -> float:
        """计算正则搜索相关性分数"""
        if match_count == 0 or file_size == 0:
            return 0.0
        
        # 正则复杂度权重：复杂模式可能更具体
        pattern_complexity = min(len(pattern) / 20, 1.0)
        
        # 匹配密度
        density_score = min(match_count / (file_size / 1000), 1.0)
        
        # 组合分数
        relevance = (density_score * 0.6 + pattern_complexity * 0.4)
        
        return relevance * 100


class SearchIndex:
    """搜索索引管理器"""
    
    def __init__(self, index_dir: Path):
        self.index_dir = index_dir
        self.index_file = index_dir / "search_index.db"
        self.lock = threading.Lock()
        
        # 确保索引目录存在
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库
        self._init_database()
    
    def _init_database(self):
        """初始化索引数据库"""
        with self.lock:
            conn = sqlite3.connect(self.index_file)
            cursor = conn.cursor()
            
            # 创建文件表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE,
                    size INTEGER,
                    modified_time REAL,
                    created_time REAL,
                    extension TEXT,
                    indexed_at REAL,
                    indexed_version INTEGER DEFAULT 1
                )
            ''')
            
            # 创建索引表（倒排索引）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS word_index (
                    word TEXT,
                    file_id INTEGER,
                    positions TEXT,  -- JSON数组存储单词位置
                    frequency INTEGER,
                    PRIMARY KEY (word, file_id),
                    FOREIGN KEY (file_id) REFERENCES files (id)
                )
            ''')
            
            # 创建索引以提高查询性能
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_word ON word_index (word)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_path ON files (path)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_extension ON files (extension)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_modified ON files (modified_time)')
            
            conn.commit()
            conn.close()
    
    def index_directory(self, directory: Path, rebuild: bool = False) -> Dict[str, Any]:
        """索引目录中的文件"""
        if not directory.exists():
            raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"目录不存在: {directory}")
        if not directory.is_dir():
            raise MCPError(ErrorCode.INVALID_PATH, detail=f"路径不是目录: {directory}")
            
        indexed_files = 0
        skipped_files = 0
        total_words = 0
        
        try:
            with self.lock:
                conn = sqlite3.connect(self.index_file)
                cursor = conn.cursor()
                
                if rebuild:
                    # 清理旧的索引
                    cursor.execute('DELETE FROM word_index')
                    cursor.execute('DELETE FROM files')
                    conn.commit()
                
                current_time = time.time()
                
                # 遍历文件
                for file_path in directory.rglob("*"):
                    if not file_path.is_file():
                        continue
                    
                    try:
                        stat_info = file_path.stat()
                        file_size = stat_info.st_size
                        
                        # 只索引文本文件（小于10MB）
                        if file_size > 10 * 1024 * 1024:
                            skipped_files += 1
                            continue
                        
                        ext = file_path.suffix.lower()
                        text_extensions = {
                            '.txt', '.md', '.py', '.js', '.ts', '.java', '.cpp', '.c',
                            '.html', '.css', '.json', '.xml', '.yaml', '.yml'
                        }
                        
                        if ext not in text_extensions:
                            skipped_files += 1
                            continue
                        
                        # 检查文件是否需要重新索引
                        cursor.execute(
                            'SELECT indexed_at, indexed_version FROM files WHERE path = ?',
                            (str(file_path),)
                        )
                        existing = cursor.fetchone()
                        
                        if existing and not rebuild:
                            last_indexed, version = existing
                            # 如果文件未修改且版本未更新，跳过
                            if stat_info.st_mtime <= last_indexed:
                                skipped_files += 1
                                continue
                        
                        # 读取文件内容
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                        
                        # 简单的分词（按空格和标点分割）
                        words = re.findall(r'\b\w+\b', content)
                        
                        # 更新或插入文件记录
                        if existing:
                            cursor.execute('''
                                UPDATE files 
                                SET size = ?, modified_time = ?, indexed_at = ?
                                WHERE path = ?
                            ''', (file_size, stat_info.st_mtime, current_time, str(file_path)))
                            file_id = cursor.lastrowid
                        else:
                            cursor.execute('''
                                INSERT INTO files (path, size, modified_time, created_time, extension, indexed_at)
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (
                                str(file_path), file_size, stat_info.st_mtime,
                                stat_info.st_ctime, ext, current_time
                            ))
                            file_id = cursor.lastrowid
                        
                        # 删除旧的单词索引
                        cursor.execute('DELETE FROM word_index WHERE file_id = ?', (file_id,))
                        
                        # 统计单词频率和位置
                        word_positions: Dict[str, List[int]] = {}
                        for pos, word in enumerate(words):
                            if len(word) > 2:  # 忽略短词
                                if word not in word_positions:
                                    word_positions[word] = []
                                word_positions[word].append(pos)
                        
                        # 插入单词索引
                        for word, positions in word_positions.items():
                            positions_json = ','.join(map(str, positions[:100]))  # 限制位置数量
                            cursor.execute('''
                                INSERT INTO word_index (word, file_id, positions, frequency)
                                VALUES (?, ?, ?, ?)
                            ''', (word, file_id, positions_json, len(positions)))
                            total_words += 1
                        
                        indexed_files += 1
                        
                        # 每100个文件提交一次
                        if indexed_files % 100 == 0:
                            conn.commit()
                    
                    except (OSError, UnicodeDecodeError, sqlite3.Error):
                        skipped_files += 1
                        continue
                
                conn.commit()
                conn.close()
                
        except Exception as e:
            raise MCPError(ErrorCode.INTERNAL_ERROR, detail=f"索引创建失败: {e}")
        
        return {
            "directory": str(directory),
            "rebuild": rebuild,
            "indexed_files": indexed_files,
            "skipped_files": skipped_files,
            "total_words_indexed": total_words,
            "index_location": str(self.index_file)
        }
    
    def search_index(self, query: str, limit: int = 100) -> Dict[str, Any]:
        """搜索索引"""
        query_words = [w.lower() for w in re.findall(r'\b\w+\b', query.lower())]
        
        if not query_words:
            return {
                "query": query,
                "results": [],
                "total_results": 0
            }
        
        try:
            with self.lock:
                conn = sqlite3.connect(self.index_file)
                cursor = conn.cursor()
                
                # 构建查询SQL
                search_sql = '''
                    SELECT f.path, f.size, f.modified_time, f.extension,
                           GROUP_CONCAT(wi.word) as matched_words,
                           SUM(wi.frequency) as total_frequency
                    FROM files f
                    JOIN word_index wi ON f.id = wi.file_id
                    WHERE wi.word IN ({})
                    GROUP BY f.id
                    ORDER BY total_frequency DESC
                    LIMIT ?
                '''.format(','.join(['?'] * len(query_words)))
                
                cursor.execute(search_sql, query_words + [limit])
                results = cursor.fetchall()
                
                conn.close()
                
                formatted_results = []
                for row in results:
                    path, size, mod_time, ext, matched_words, total_freq = row
                    
                    # 计算相关性分数
                    relevance = min(total_freq / 10, 1.0) * 100  # 简单频率分数
                    
                    formatted_results.append({
                        "file": path,
                        "size_bytes": size,
                        "modified_time": datetime.fromtimestamp(mod_time).isoformat(),
                        "extension": ext,
                        "matched_words": matched_words.split(','),
                        "total_frequency": total_freq,
                        "relevance": round(relevance, 2)
                    })
                
                return {
                    "query": query,
                    "query_words": query_words,
                    "results": formatted_results,
                    "total_results": len(formatted_results)
                }
                
        except sqlite3.Error as e:
            raise MCPError(ErrorCode.INTERNAL_ERROR, detail=f"索引搜索失败: {e}")
    
    def get_index_stats(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.index_file)
                cursor = conn.cursor()
                
                # 获取统计信息
                cursor.execute('SELECT COUNT(*) FROM files')
                file_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM word_index')
                word_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT SUM(size) FROM files')
                total_size = cursor.fetchone()[0] or 0
                
                cursor.execute('''
                    SELECT extension, COUNT(*) as count 
                    FROM files 
                    GROUP BY extension 
                    ORDER BY count DESC 
                    LIMIT 10
                ''')
                top_extensions = [{"extension": ext, "count": cnt} for ext, cnt in cursor.fetchall()]
                
                conn.close()
                
                return {
                    "index_location": str(self.index_file),
                    "total_files": file_count,
                    "total_words": word_count,
                    "total_size_bytes": total_size,
                    "top_extensions": top_extensions,
                    "index_size_mb": os.path.getsize(self.index_file) / (1024 * 1024)
                }
                
        except (sqlite3.Error, OSError) as e:
            raise MCPError(ErrorCode.INTERNAL_ERROR, detail=f"获取索引统计失败: {e}")


def get_enhanced_searcher(max_results: int = 1000, max_file_size: int = 10 * 1024 * 1024) -> EnhancedSearcher:
    """获取增强搜索器实例"""
    return EnhancedSearcher(max_results, max_file_size)


def get_search_index(index_dir: Optional[Path] = None) -> SearchIndex:
    """获取搜索索引管理器实例"""
    if index_dir is None:
        index_dir = Path.home() / ".filesystem_mcp_index"
    return SearchIndex(index_dir)


__all__ = [
    "EnhancedSearcher", "SearchIndex",
    "get_enhanced_searcher", "get_search_index"
]