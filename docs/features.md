# 功能扩展

> **Read based on task** - 实现扩展功能时阅读

## 1. 高级文件操作

### 1.1 文件监听

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class FileWatcher:
    """文件系统监听器"""
    
    def __init__(self, paths: list[str], callback: Callable):
        self.observer = Observer()
        self.callback = callback
        
        handler = FileSystemEventHandler()
        handler.on_created = lambda e: self._on_event("created", e)
        handler.on_modified = lambda e: self._on_event("modified", e)
        handler.on_deleted = lambda e: self._on_event("deleted", e)
        handler.on_moved = lambda e: self._on_event("moved", e)
        
        for path in paths:
            self.observer.schedule(handler, path, recursive=True)
    
    def start(self):
        self.observer.start()
    
    def stop(self):
        self.observer.stop()
        self.observer.join()
    
    def _on_event(self, event_type: str, event):
        self.callback({
            "type": event_type,
            "path": event.src_path,
            "is_directory": event.is_directory,
            "timestamp": datetime.now().isoformat()
        })
```

### 1.2 文件比较

```python
import difflib

class FileComparator:
    """文件比较器"""
    
    @staticmethod
    def compare_text(file1: str, file2: str) -> dict:
        """比较两个文本文件"""
        with open(file1, "r") as f1, open(file2, "r") as f2:
            lines1 = f1.readlines()
            lines2 = f2.readlines()
        
        diff = difflib.unified_diff(
            lines1, lines2,
            fromfile=file1, tofile=file2
        )
        
        return {
            "identical": lines1 == lines2,
            "added_lines": [l for l in diff if l.startswith("+")],
            "removed_lines": [l for l in diff if l.startswith("-")],
            "diff_text": "".join(diff),
            "similarity": SequenceMatcher(None, "".join(lines1), "".join(lines2)).ratio()
        }
    
    @staticmethod
    def compare_binary(file1: str, file2: str, chunk_size: int = 1024) -> dict:
        """比较二进制文件"""
        hashes1 = []
        hashes2 = []
        
        with open(file1, "rb") as f1, open(file2, "rb") as f2:
            while chunk := f1.read(chunk_size):
                hashes1.append(hashlib.md5(chunk).hexdigest())
            while chunk := f2.read(chunk_size):
                hashes2.append(hashlib.md5(chunk).hexdigest())
        
        return {
            "identical": hashes1 == hashes2,
            "different_chunks": sum(1 for a, b in zip(hashes1, hashes2) if a != b),
            "total_chunks": max(len(hashes1), len(hashes2))
        }
```

### 1.3 文件同步

```python
import shutil

class DirectorySync:
    """目录同步"""
    
    def sync(
        self,
        source: str,
        target: str,
        mode: str = "incremental",  # incremental | full
        delete_missing: bool = False
    ) -> dict:
        """同步目录"""
        stats = {"copied": 0, "updated": 0, "deleted": 0, "errors": []}
        
        for src_path in Path(source).rglob("*"):
            rel_path = src_path.relative_to(source)
            dst_path = Path(target) / rel_path
            
            try:
                if src_path.is_file():
                    if not dst_path.exists():
                        shutil.copy2(src_path, dst_path)
                        stats["copied"] += 1
                    elif src_path.stat().st_mtime > dst_path.stat().st_mtime:
                        shutil.copy2(src_path, dst_path)
                        stats["updated"] += 1
                
                elif src_path.is_dir():
                    dst_path.mkdir(parents=True, exist_ok=True)
            
            except Exception as e:
                stats["errors"].append({"file": str(src_path), "error": str(e)})
        
        # 删除目标中多余的文件
        if delete_missing:
            for dst_path in Path(target).rglob("*"):
                rel_path = dst_path.relative_to(target)
                src_path = Path(source) / rel_path
                if not src_path.exists():
                    if dst_path.is_file():
                        dst_path.unlink()
                        stats["deleted"] += 1
                    elif dst_path.is_dir():
                        shutil.rmtree(dst_path)
                        stats["deleted"] += 1
        
        return stats
```

---

## 2. 内容分析

### 2.1 文件类型检测

```python
import magic

class FileTypeDetector:
    """文件类型检测器（基于magic number）"""
    
    # 轻量级实现（不依赖python-magic）
    SIGNATURES = {
        b'\x89PNG': 'image/png',
        b'\xff\xd8\xff': 'image/jpeg',
        b'PK': 'application/zip',
        b'Rar!': 'application/x-rar',
        b'7z\xBC\xAF\x27\x1C': 'application/x-7z',
        b'%PDF': 'application/pdf',
        b'\x1F\x8B': 'application/gzip',
        b'<?xml': 'application/xml',
        b'{': 'application/json',
    }
    
    @classmethod
    def detect(cls, file_path: str) -> str:
        """检测文件真实类型"""
        with open(file_path, "rb") as f:
            header = f.read(16)
        
        # 检查二进制签名
        for sig, mimeType in cls.SIGNATURES.items():
            if header.startswith(sig):
                return mimeType
        
        # 检查文本文件
        try:
            header.decode("utf-8")
            # 文本文件，尝试通过扩展名判断
            mime, _ = mimetypes.guess_type(file_path)
            return mime or "text/plain"
        except UnicodeDecodeError:
            return "application/octet-stream"
```

### 2.2 编码检测

```python
import chardet

class EncodingDetector:
    """编码检测器"""
    
    @classmethod
    def detect(cls, file_path: str) -> str:
        """检测文件编码"""
        with open(file_path, "rb") as f:
            raw = f.read(10000)  # 读取前10KB用于检测
        
        result = chardet.detect(raw)
        encoding = result["encoding"]
        
        # 验证编码是否正确
        if encoding:
            try:
                raw.decode(encoding)
                return encoding
            except (UnicodeDecodeError, LookupError):
                pass
        
        # 回退方案
        for enc in ["utf-8", "gbk", "latin-1", "ascii"]:
            try:
                raw.decode(enc)
                return enc
            except UnicodeDecodeError:
                continue
        
        return "utf-8"  # 默认UTF-8
```

### 2.3 重复文件检测

```python
import hashlib

class DuplicateDetector:
    """重复文件检测器"""
    
    def __init__(self, block_size: int = 65536):
        self.block_size = block_size
    
    def find_duplicates(self, directory: str) -> dict[str, list[str]]:
        """查找重复文件"""
        # 第一阶段: 按大小分组
        size_groups = {}
        for path in Path(directory).rglob("*"):
            if path.is_file():
                size = path.stat().st_size
                size_groups.setdefault(size, []).append(str(path))
        
        # 第二阶段: 对同大小文件计算哈希
        hash_groups = {}
        for size, files in size_groups.items():
            if len(files) < 2:
                continue
            
            for file_path in files:
                file_hash = self._file_hash(file_path)
                hash_groups.setdefault(file_hash, []).append(file_path)
        
        # 返回重复组
        return {h: files for h, files in hash_groups.items() if len(files) > 1}
    
    def _file_hash(self, path: str) -> str:
        """计算文件哈希"""
        hasher = hashlib.md5()
        with open(path, "rb") as f:
            while chunk := f.read(self.block_size):
                hasher.update(chunk)
        return hasher.hexdigest()
```

### 2.4 文件压缩

```python
import zipfile
import tarfile

class FileCompressor:
    """文件压缩器"""
    
    @staticmethod
    def create_zip(
        files: list[str],
        output_path: str,
        compression: int = zipfile.ZIP_DEFLATED
    ):
        """创建ZIP文件"""
        with zipfile.ZipFile(output_path, "w", compression) as zf:
            for file_path in files:
                arcname = os.path.basename(file_path)
                zf.write(file_path, arcname)
    
    @staticmethod
    def create_tar_gz(files: list[str], output_path: str):
        """创建TAR.GZ文件"""
        with tarfile.open(output_path, "w:gz") as tar:
            for file_path in files:
                tar.add(file_path, arcname=os.path.basename(file_path))
    
    @staticmethod
    def extract_zip(zip_path: str, extract_to: str):
        """解压ZIP文件"""
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_to)
    
    @staticmethod
    def extract_tar_gz(tar_path: str, extract_to: str):
        """解压TAR.GZ文件"""
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(extract_to)
```

---

## 3. 搜索增强

### 3.1 全文搜索

```python
class FullTextSearch:
    """全文搜索引擎"""
    
    def __init__(self, index_dir: str):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(exist_ok=True)
        self._index = {}  # {word: {doc_id: [positions]}}
    
    def index_file(self, file_path: str, doc_id: str | None = None):
        """索引文件"""
        doc_id = doc_id or file_path
        
        with open(file_path, "r", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                words = line.lower().split()
                for pos, word in enumerate(words):
                    if word not in self._index:
                        self._index[word] = {}
                    if doc_id not in self._index[word]:
                        self._index[word][doc_id] = []
                    self._index[word][doc_id].append((line_num, pos))
    
    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """搜索"""
        words = query.lower().split()
        doc_scores = {}
        
        for word in words:
            if word in self._index:
                for doc_id, positions in self._index[word].items():
                    doc_scores[doc_id] = doc_scores.get(doc_id, 0) + len(positions)
        
        # 排序并返回Top-K
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        return [
            {"doc_id": doc_id, "score": score}
            for doc_id, score in sorted_docs[:top_k]
        ]
```

### 3.2 正则搜索

```python
class RegexSearch:
    """正则表达式搜索"""
    
    @staticmethod
    def search_in_files(
        directory: str,
        pattern: str,
        file_pattern: str = "*",
        max_results: int = 100
    ) -> list[dict]:
        """在文件中搜索正则匹配"""
        regex = re.compile(pattern)
        results = []
        
        for file_path in Path(directory).glob(f"**/{file_pattern}"):
            if file_path.is_file():
                try:
                    with open(file_path, "r", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            matches = list(regex.finditer(line))
                            if matches:
                                results.append({
                                    "file": str(file_path),
                                    "line": line_num,
                                    "content": line.strip(),
                                    "matches": len(matches)
                                })
                                if len(results) >= max_results:
                                    return results
                except Exception:
                    continue
        
        return results
```

### 3.3 模糊搜索

```python
from difflib import SequenceMatcher

class FuzzySearch:
    """模糊搜索引擎"""
    
    @staticmethod
    def find_files(
        directory: str,
        query: str,
        threshold: float = 0.6,
        max_results: int = 20
    ) -> list[dict]:
        """模糊搜索文件"""
        results = []
        
        for file_path in Path(directory).rglob("*"):
            if file_path.is_file():
                name = file_path.stem.lower()
                query_lower = query.lower()
                
                # 计算相似度
                similarity = SequenceMatcher(None, name, query_lower).ratio()
                
                # 也检查子串包含
                if query_lower in name or any(
                    w in name for w in query_lower.split()
                ):
                    similarity = max(similarity, 0.8)
                
                if similarity >= threshold:
                    results.append({
                        "path": str(file_path),
                        "name": file_path.name,
                        "score": round(similarity, 2)
                    })
        
        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]
```
