"""错误处理模块单元测试"""
import pytest
from src.mcp_project.services.errors import (
    ErrorCode, MCPError, error_result, classify_error
)


class TestErrorCode:
    def test_error_code_values(self):
        assert ErrorCode.INVALID_PARAMS == 1001
        assert ErrorCode.PATH_TRAVERSAL == 2001
        assert ErrorCode.FILE_NOT_FOUND == 3001
        assert ErrorCode.INTERNAL_ERROR == 4001

    def test_error_message(self):
        err = MCPError(ErrorCode.FILE_NOT_FOUND)
        assert "文件不存在" in err.message

    def test_error_with_detail(self):
        err = MCPError(ErrorCode.PERMISSION_DENIED, detail="user test")
        assert err.detail == "user test"

    def test_error_to_text(self):
        err = MCPError(ErrorCode.FILE_NOT_FOUND, detail="test.txt", suggestion="check path")
        text = err.to_text()
        assert "E3001" in text
        assert "test.txt" in text
        assert "check path" in text


class TestClassifyError:
    def test_file_not_found(self):
        assert classify_error(FileNotFoundError()) == ErrorCode.FILE_NOT_FOUND

    def test_permission_error(self):
        assert classify_error(PermissionError()) == ErrorCode.PERMISSION_DENIED

    def test_unicode_error(self):
        assert classify_error(UnicodeDecodeError("utf-8", b"", 0, 1, "reason")) == ErrorCode.ENCODING_ERROR

    def test_os_error(self):
        assert classify_error(OSError()) == ErrorCode.READ_ERROR

    def test_unknown_error(self):
        assert classify_error(ValueError()) == ErrorCode.INTERNAL_ERROR
