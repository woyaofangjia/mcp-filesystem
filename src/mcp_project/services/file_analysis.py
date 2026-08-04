"""
文件类型检测和内容分析服务
实现文件类型检测、编码检测、压缩支持等功能
"""

import os
import re
import hashlib
import mimetypes
import chardet
import zipfile
import tarfile
import gzip
import bz2
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import tempfile

from .errors import MCPError, ErrorCode


class FileTypeDetector:
    """文件类型检测器"""
    
    def __init__(self):
        # 初始化MIME类型数据库
        mimetypes.init()
        
        # 常用文件类型的魔数签名
        self.magic_numbers: Dict[bytes, str] = {
            b'\x89PNG\r\n\x1a\n': 'image/png',
            b'\xff\xd8\xff': 'image/jpeg',
            b'GIF87a': 'image/gif',
            b'GIF89a': 'image/gif',
            b'\x25\x50\x44\x46': 'application/pdf',
            b'PK\x03\x04': 'application/zip',
            b'PK\x05\x06': 'application/zip',  # 空的ZIP
            b'PK\x07\x08': 'application/zip',  # 分段的ZIP
            b'\x1f\x8b\x08': 'application/gzip',
            b'BZh': 'application/x-bzip2',
            b'\x1f\x9d': 'application/x-compress',
            b'\x37\x7a\xbc\xaf\x27\x1c': 'application/x-7z-compressed',
            b'\x52\x61\x72\x21\x1a\x07': 'application/x-rar',
            b'<?xml': 'text/xml',
            b'<!DOCTYPE html': 'text/html',
            b'<!DOCTYPE HTML': 'text/html',
            b'{\n': 'application/json',
            b'{\r\n': 'application/json',
        }
    
    def detect_file_type(self, file_path: Path) -> Dict[str, Any]:
        """检测文件类型"""
        if not file_path.exists():
            raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"文件不存在: {file_path}")
        if not file_path.is_file():
            raise MCPError(ErrorCode.INVALID_PATH, detail=f"路径不是文件: {file_path}")
        
        try:
            file_size = file_path.stat().st_size
            extension = file_path.suffix.lower()
            
            # 方法1：基于扩展名的MIME类型
            mime_from_ext, _ = mimetypes.guess_type(str(file_path))
            
            # 方法2：基于魔数的真实类型检测
            real_type = self._detect_by_magic(file_path)
            
            # 方法3：如果是文本文件，尝试检测内容
            content_type = self._detect_by_content(file_path) if file_size < 1024 * 1024 else None
            
            # 确定最佳类型
            best_type = real_type or mime_from_ext or content_type or 'application/octet-stream'
            
            # 分类
            categories = self._categorize_type(best_type, extension)
            
            return {
                "file": str(file_path),
                "extension": extension,
                "size_bytes": file_size,
                "mime_type": best_type,
                "mime_from_extension": mime_from_ext,
                "real_type": real_type,
                "content_type": content_type,
                "categories": categories,
                "is_text": 'text/' in best_type or categories.get('is_text', False),
                "is_binary": not ('text/' in best_type or categories.get('is_text', False))
            }
        except OSError as e:
            raise MCPError(ErrorCode.READ_ERROR, detail=f"文件类型检测失败: {e}")
    
    def _detect_by_magic(self, file_path: Path) -> Optional[str]:
        """通过魔数检测文件类型"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(1024)  # 读取前1KB
            
            # 检查魔数
            for magic_bytes, mime_type in self.magic_numbers.items():
                if header.startswith(magic_bytes):
                    return mime_type
            
            # 简单的文件类型检测，基于扩展名和内容
            # 注：更精确的类型检测需要python-magic或filemagic库
            pass
            
            # 检查是否为文本文件
            try:
                header_str = header.decode('utf-8', errors='ignore')
                # 简单的文本文件检测规则
                text_indicators = [
                    '#!/',  # shebang
                    '<?php', '<?xml', '<!DOCTYPE',
                    'import', 'from', 'def ', 'function ',
                    'class ', 'public ', 'private ', 'protected ',
                    'return', 'if ', 'for ', 'while ', 'do ',
                ]
                
                if any(indicator in header_str for indicator in text_indicators):
                    return 'text/plain'
            except UnicodeDecodeError:
                pass
                
        except OSError:
            pass
        
        return None
    
    def _detect_by_content(self, file_path: Path) -> Optional[str]:
        """通过内容检测文件类型"""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # 尝试解码为UTF-8文本
            try:
                text = content.decode('utf-8')
                
                # 根据内容特征检测
                if '<?xml' in text or '<!DOCTYPE' in text:
                    return 'text/xml'
                elif '<html' in text or '<!DOCTYPE html' in text:
                    return 'text/html'
                elif text.strip().startswith('{') and text.strip().endswith('}'):
                    # 可能是JSON
                    import json
                    try:
                        json.loads(text)
                        return 'application/json'
                    except json.JSONDecodeError:
                        pass
                elif text.strip().startswith('[') and text.strip().endswith(']'):
                    # 可能是JSON数组
                    import json
                    try:
                        json.loads(text)
                        return 'application/json'
                    except json.JSONDecodeError:
                        pass
                elif '#!/' in text[:100]:  # shebang
                    return 'text/x-script'
                
                return 'text/plain'
            except UnicodeDecodeError:
                pass
                
        except OSError:
            pass
        
        return None
    
    def _categorize_type(self, mime_type: str, extension: str) -> Dict[str, bool]:
        """将MIME类型分类"""
        categories = {
            "is_text": False,
            "is_image": False,
            "is_archive": False,
            "is_audio": False,
            "is_video": False,
            "is_document": False,
            "is_code": False,
            "is_config": False,
            "is_executable": False,
        }
        
        # 文本类型
        if mime_type.startswith('text/'):
            categories["is_text"] = True
            
            # 代码文件
            code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.cs',
                              '.php', '.rb', '.go', '.rs', '.swift', '.sql', '.sh'}
            if extension in code_extensions:
                categories["is_code"] = True
            
            # 配置文件
            config_extensions = {'.json', '.yaml', '.yml', '.toml', '.ini', '.cfg',
                                '.properties', '.env', '.config', '.conf'}
            if extension in config_extensions:
                categories["is_config"] = True
        
        # 图像
        elif mime_type.startswith('image/'):
            categories["is_image"] = True
        
        # 文档
        elif mime_type in ['application/pdf', 'application/msword',
                          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                          'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                          'application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation']:
            categories["is_document"] = True
        
        # 压缩包
        elif mime_type.startswith('application/x-') and 'compress' in mime_type or \
             mime_type in ['application/zip', 'application/x-rar', 'application/x-7z-compressed',
                          'application/gzip', 'application/x-bzip2']:
            categories["is_archive"] = True
        
        # 音频
        elif mime_type.startswith('audio/'):
            categories["is_audio"] = True
        
        # 视频
        elif mime_type.startswith('video/'):
            categories["is_video"] = True
        
        # 可执行文件
        elif mime_type in ['application/x-executable', 'application/x-msdownload',
                          'application/x-sh', 'application/x-bash'] or \
             extension in ['.exe', '.bat', '.cmd', '.ps1', '.sh']:
            categories["is_executable"] = True
        
        return categories


class EncodingDetector:
    """编码检测器"""
    
    def detect_encoding(self, file_path: Path, sample_size: int = 10240) -> Dict[str, Any]:
        """检测文件编码"""
        if not file_path.exists():
            raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"文件不存在: {file_path}")
        if not file_path.is_file():
            raise MCPError(ErrorCode.INVALID_PATH, detail=f"路径不是文件: {file_path}")
        
        try:
            file_size = file_path.stat().st_size
            sample_size = min(sample_size, file_size)
            
            # 读取样本数据
            with open(file_path, 'rb') as f:
                sample = f.read(sample_size)
            
            # 使用chardet检测编码
            detection = chardet.detect(sample)
            
            # 常见的编码列表
            common_encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'big5',
                               'latin-1', 'iso-8859-1', 'ascii', 'cp1252']
            
            # 测试常见编码
            tested_encodings = []
            for encoding in common_encodings:
                try:
                    sample.decode(encoding)
                    tested_encodings.append({
                        "encoding": encoding,
                        "valid": True
                    })
                except UnicodeDecodeError:
                    tested_encodings.append({
                        "encoding": encoding,
                        "valid": False
                    })
            
            # 判断是否为文本文件
            try:
                sample.decode(detection['encoding'] if detection['encoding'] else 'utf-8')
                is_text = True
            except UnicodeDecodeError:
                is_text = False
            
            return {
                "file": str(file_path),
                "size_bytes": file_size,
                "detected_encoding": detection['encoding'],
                "detection_confidence": detection['confidence'],
                "sample_size": sample_size,
                "is_text_file": is_text,
                "common_encodings_tested": tested_encodings,
                "recommended_encoding": detection['encoding'] if detection['confidence'] > 0.7 else 'utf-8'
            }
        except OSError as e:
            raise MCPError(ErrorCode.READ_ERROR, detail=f"编码检测失败: {e}")


class FileCompressor:
    """文件压缩器"""
    
    def compress_file(self, source_file: Path, format_type: str = 'zip',
                     compression_level: int = 6) -> Dict[str, Any]:
        """压缩单个文件"""
        if not source_file.exists():
            raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"文件不存在: {source_file}")
        if not source_file.is_file():
            raise MCPError(ErrorCode.INVALID_PATH, detail=f"路径不是文件: {source_file}")
        
        try:
            original_size = source_file.stat().st_size
            
            # 创建临时输出文件
            temp_dir = tempfile.mkdtemp()
            output_name = f"{source_file.stem}.{format_type}"
            output_path = Path(temp_dir) / output_name
            
            if format_type == 'zip':
                import zipfile
                compression_method = zipfile.ZIP_DEFLATED
                with zipfile.ZipFile(output_path, 'w', compression_method) as zipf:
                    zipf.write(source_file, arcname=source_file.name)
            
            elif format_type == 'gzip':
                import gzip
                with open(source_file, 'rb') as f_in:
                    with gzip.open(output_path, 'wb', compresslevel=compression_level) as f_out:
                        f_out.write(f_in.read())
            
            elif format_type == 'bzip2':
                import bz2
                with open(source_file, 'rb') as f_in:
                    with bz2.open(output_path, 'wb', compresslevel=compression_level) as f_out:
                        f_out.write(f_in.read())
            
            else:
                raise MCPError(ErrorCode.INVALID_PARAMS, detail=f"不支持的压缩格式: {format_type}")
            
            compressed_size = output_path.stat().st_size
            
            return {
                "source_file": str(source_file),
                "compressed_file": str(output_path),
                "format": format_type,
                "compression_level": compression_level,
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_ratio": round(compressed_size / original_size * 100, 2) if original_size > 0 else 0,
                "space_saved": original_size - compressed_size,
                "temporary_location": True
            }
        except (OSError, ImportError) as e:
            raise MCPError(ErrorCode.WRITE_ERROR, detail=f"压缩文件失败: {e}")
    
    def decompress_file(self, archive_file: Path, output_dir: Optional[Path] = None) -> Dict[str, Any]:
        """解压文件"""
        if not archive_file.exists():
            raise MCPError(ErrorCode.FILE_NOT_FOUND, detail=f"压缩文件不存在: {archive_file}")
        if not archive_file.is_file():
            raise MCPError(ErrorCode.INVALID_PATH, detail=f"路径不是文件: {archive_file}")
        
        try:
            archive_size = archive_file.stat().st_size
            
            # 确定输出目录
            if output_dir is None:
                output_dir = archive_file.parent / f"{archive_file.stem}_extracted"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            extracted_files = []
            
            # 根据扩展名选择解压方法
            extension = archive_file.suffix.lower()
            
            if extension == '.zip':
                import zipfile
                with zipfile.ZipFile(archive_file, 'r') as zipf:
                    file_list = zipf.namelist()
                    for file_name in file_list:
                        # 解压文件
                        output_path = output_dir / file_name
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        zipf.extract(file_name, output_dir)
                        extracted_files.append(str(output_path))
            
            elif extension in ['.gz', '.gzip']:
                import gzip
                output_file = output_dir / archive_file.stem
                if output_file.suffix == '.gz':
                    output_file = output_file.with_suffix('')
                
                with gzip.open(archive_file, 'rb') as f_in:
                    with open(output_file, 'wb') as f_out:
                        f_out.write(f_in.read())
                extracted_files.append(str(output_file))
            
            elif extension in ['.bz2', '.bzip2']:
                import bz2
                output_file = output_dir / archive_file.stem
                if output_file.suffix in ['.bz2', '.bzip2']:
                    output_file = output_file.with_suffix('')
                
                with bz2.open(archive_file, 'rb') as f_in:
                    with open(output_file, 'wb') as f_out:
                        f_out.write(f_in.read())
                extracted_files.append(str(output_file))
            
            elif extension == '.tar':
                import tarfile
                with tarfile.open(archive_file, 'r') as tarf:
                    tarf.extractall(output_dir)
                    extracted_files.extend([str(output_dir / name) for name in tarf.getnames()])
            
            else:
                raise MCPError(ErrorCode.INVALID_PARAMS, detail=f"不支持的解压格式: {extension}")
            
            # 统计解压结果
            total_extracted_size = 0
            for file_path in extracted_files:
                try:
                    total_extracted_size += Path(file_path).stat().st_size
                except OSError:
                    pass
            
            return {
                "archive_file": str(archive_file),
                "output_directory": str(output_dir),
                "archive_size": archive_size,
                "extracted_files": extracted_files,
                "total_files": len(extracted_files),
                "total_extracted_size": total_extracted_size,
                "compression_ratio": round(archive_size / total_extracted_size * 100, 2) if total_extracted_size > 0 else 0
            }
        except (OSError, ImportError) as e:
            raise MCPError(ErrorCode.WRITE_ERROR, detail=f"解压文件失败: {e}")


def get_file_type_detector() -> FileTypeDetector:
    """获取文件类型检测器实例"""
    return FileTypeDetector()


def get_encoding_detector() -> EncodingDetector:
    """获取编码检测器实例"""
    return EncodingDetector()


def get_file_compressor() -> FileCompressor:
    """获取文件压缩器实例"""
    return FileCompressor()


__all__ = [
    "FileTypeDetector", "EncodingDetector", "FileCompressor",
    "get_file_type_detector", "get_encoding_detector", "get_file_compressor"
]