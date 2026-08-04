# 升级路线图

> **Read based on task** - 规划开发时阅读

## 1. 阶段划分

### 第一阶段：基础增强 ✅ 已完成
**目标**: 安全加固、错误处理、日志系统

| 任务 | 状态 | 优先级 | 实现文件 |
|------|------|--------|----------|
| 路径沙箱化 | ✅ 已完成 | 🔴 高 | `services/sandbox.py` |
| 操作审计日志 | ✅ 已完成 | 🔴 高 | `services/audit.py` |
| 权限控制 | ✅ 已完成 | 🔴 高 | `services/permissions.py` |
| 危险操作保护 | ✅ 已完成 | 🟡 中 | `server.py` (delete/write标记) |
| 敏感文件检测 | ✅ 已完成 | 🟡 中 | `services/sensitive.py` |
| 结构化错误码 | ✅ 已完成 | 🔴 高 | `services/errors.py` |
| 异常处理策略 | ✅ 已完成 | 🔴 高 | `server.py` + `errors.py` |
| 分级日志系统 | ✅ 已完成 | 🔴 高 | `services/logger.py` |
| 日志持久化 | ✅ 已完成 | 🟡 中 | `services/logger.py` (RotatingFileHandler) |

### 第二阶段：性能优化 ✅ 已完成
**目标**: 异步处理、缓存、大文件支持

| 任务 | 状态 | 优先级 | 实现文件 |
|------|------|--------|----------|
| 异步IO改造 | ✅ 已完成 | 🔴 高 | `server.py` (asyncio.Semaphore) |
| 并发控制 | ✅ 已完成 | 🔴 高 | `_ops_semaphore` (MAX_CONCURRENT_OPS=20) |
| LRU内存缓存 | ✅ 已完成 | 🔴 高 | `services/cache.py` |
| 文件内容缓存 | ✅ 已完成 | 🟡 中 | `FileCacheManager` (max 50MB) |
| 缓存失效策略 | ✅ 已完成 | 🟡 中 | `mtime` 自动检测 |
| 批量操作支持 | ✅ 已完成 | 🟡 中 | `batch_read_files`, `batch_delete_files` |
| 分块读写 | ✅ 已完成 | 🟡 中 | `read_file_chunked` |
| 缓存统计 | ✅ 已完成 | 🟡 中 | `cache_stats` 工具 |

### 第三阶段：功能扩展 ✅ 已完成（2026-08-04）
**目标**: 高级文件操作、内容分析、搜索增强
**成果**: 新增17个工具，工具总数达到29个

| 任务 | 状态 | 优先级 | 实现文件 |
|------|------|--------|----------|
| 文件比较 | ✅ 已完成 | 🟡 中 | `services/advanced_operations.py` (FileComparator) |
| 文件合并 | ✅ 已完成 | 🟡 中 | `services/advanced_operations.py` (FileMerger) |
| 批量重命名 | ✅ 已完成 | 🟡 中 | `services/advanced_operations.py` (BatchRenamer) |
| 内容分析 | ✅ 已完成 | 🟡 中 | `services/advanced_operations.py` (ContentAnalyzer) |
| 重复文件检测 | ✅ 已完成 | 🟡 中 | `services/advanced_operations.py` (DuplicateFinder) |
| 全文搜索 | ✅ 已完成 | 🔴 高 | `services/search_enhancement.py` (EnhancedSearcher) |
| 正则搜索 | ✅ 已完成 | 🔴 高 | `services/search_enhancement.py` (regex_search) |
| 模糊搜索 | ✅ 已完成 | 🟡 中 | `services/search_enhancement.py` (fuzzy_search) |
| 多条件搜索 | ✅ 已完成 | 🟡 中 | `services/search_enhancement.py` (advanced_search) |
| 文件类型检测 | ✅ 已完成 | 🔴 高 | `services/file_analysis.py` (FileTypeDetector) |
| 编码检测 | ✅ 已完成 | 🟡 中 | `services/file_analysis.py` (EncodingDetector) |
| 文件压缩/解压 | ✅ 已完成 | 🟢 低 | `services/file_analysis.py` (FileCompressor) |
| 目录索引 | ✅ 已完成 | 🟡 中 | `services/search_enhancement.py` (SearchIndex) |
| 索引搜索 | ✅ 已完成 | 🔴 高 | `services/search_enhancement.py` (search_index) |
| 索引统计 | ✅ 已完成 | 🟡 中 | `services/search_enhancement.py` (get_index_stats) |
| **待完成** | **-** | **-** | **-** |
| 文件监听 | ⬜ 待开始 | 🟢 低 | [features.md](features.md#1-高级文件操作) |
| 目录同步 | ⬜ 待开始 | 🟡 中 | [features.md](features.md#1-高级文件操作) |

### 第四阶段：企业级特性 ✅ 已完成（2026-08-04）
**目标**: 可观测性、配置管理、测试体系
**成果**: 新增5个MCP工具（工具总数从28增至33），建立完整测试体系（47单元测试 + 8集成测试通过）

| 任务 | 状态 | 优先级 | 实现文件 |
|------|------|--------|----------|
| 健康检查端点 | ✅ 已完成 | 🔴 高 | `services/observability.py` (HealthChecker) + `health_check` 工具 |
| 性能监控指标 | ✅ 已完成 | 🟡 中 | `services/observability.py` (MetricsCollector) + `get_metrics` 工具 |
| 告警系统 | ✅ 已完成 | 🟡 中 | `services/observability.py` (AlertManager) + `get_alerts` 工具 |
| 配置管理 | ✅ 已完成 | 🔴 高 | `services/config.py` (ConfigManager/ServerConfig) + `get_config`/`update_config` 工具 |
| 单元测试覆盖 | ✅ 已完成 | 🔴 高 | `tests/unit/`（47项全部通过） |
| 集成测试 | ✅ 已完成 | 🔴 高 | `tests/integration/`（8项通过：5新工具 + 3回归） |
| 安全测试 | ✅ 已完成 | 🔴 高 | `tests/security/` |
| CI/CD配置 | ⬜ 待开始 | 🟡 中 | [testing.md](testing.md#6-测试运行) |

---

## 2. 推荐实施计划

### 第1-2周：安全与基础 ✅ 已完成

```
Week 1: ✅
├── 周一: 路径沙箱化 + 单元测试
├── 周二: 操作审计日志
├── 周三: 权限控制框架
├── 周四: 敏感文件检测
└── 周五: 第一阶段集成测试

Week 2: ✅
├── 周一: 结构化错误码
├── 周二: 异常处理策略
├── 周三: 分级日志系统
├── 周四: 日志持久化
└── 周五: 第一阶段完成验证
```

### 第3-4周：性能优化

```
Week 3:
├── 周一: 异步IO改造
├── 周二: 并发控制 + 文件操作池
├── 周三: LRU缓存实现
├── 周四: 文件内容缓存
└── 周五: 缓存失效策略

Week 4:
├── 周一: 批量操作支持
├── 周二: 分块读写实现
├── 周三: 性能基准测试
├── 周四: 性能调优
└── 周五: 第二阶段完成验证
```

### 第5-6周：功能与测试 ✅ 已完成（2026-08-04）

```
Week 5: ✅
├── 周一: 文件类型/编码检测 ✅
├── 周二: 文件比较工具 ✅
├── 周三: 正则/模糊搜索 ✅
├── 周四: 重复文件检测 ✅
└── 周五: 文件压缩支持 ✅

Week 6: ✅
├── 周一: 批量重命名/文件合并 ✅
├── 周二: 全文搜索/多条件搜索 ✅
├── 周三: 搜索索引管理 ✅
├── 周四: 集成测试完善 ✅
└── 周五: 最终验证 + 文档更新 ✅
```

---

## 3. 优先级矩阵

### 必须完成 (MUST)
- [x] 路径沙箱化
- [x] 结构化错误处理
- [x] 分级日志系统
- [x] 单元测试覆盖（47项全部通过）

### 强烈推荐 (SHOULD)
- [x] 操作审计
- [x] 权限控制
- [x] 异步IO
- [x] 缓存机制
- [x] 集成测试（8项通过）

### 可选实现 (COULD)
- [ ] 文件监听
- [ ] 断点续传
- [ ] AI集成
- [ ] 云存储

---

## 4. 成功标准

### 第一阶段验收 ✅
- [x] 路径遍历攻击被阻止
- [x] 敏感文件被保护
- [x] 所有操作可审计
- [x] 错误响应标准化
- [x] 日志可追溯

### 第二阶段验收 ✅
- [x] 并发支持 >= 20 (MAX_CONCURRENT_OPS=20)
- [x] 缓存命中率 >= 33% (实测可达33%+)
- [x] 响应时间 < 50ms（缓存命中）
- [x] 最大文件支持 >= 10MB (分块读取支持更大文件)

### 第三阶段验收 ✅
- [x] 工具数量从12个增加到29个 (+142%)
- [x] 实现6大类17个新功能
- [x] 所有新增工具通过集成测试
- [x] 完整的搜索能力（全文/正则/模糊/索引）
- [x] 全面的文件分析（类型/编码/重复/内容）

### 最终验收（第四阶段）✅
- [x] 单元测试体系完善（47项全部通过）
- [x] 集成测试体系完善（8项通过：5新工具 + 3回归）
- [x] 可观测性完整实现（健康检查/性能指标/告警系统）
- [x] 配置管理完整实现（dev/test/prod + 动态热更新）
- [x] 企业级特性完整实现（工具总数达33个）
- [x] 修复关键Bug（server.py handler加载 + observability.py死锁）
- [ ] 代码覆盖率 >= 80%（待量化统计）
- [ ] CI/CD配置（待后续实现）