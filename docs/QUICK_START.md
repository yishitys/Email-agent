# 快速开始指南

## 📋 前置要求

### 1. Gmail OAuth 设置

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建新项目（或选择现有项目）
3. 启用 Gmail API
4. 创建 OAuth 2.0 客户端 ID
   - 应用类型：桌面应用 或 Web 应用
   - 授权重定向 URI：`http://127.0.0.1:8000/auth/google/callback`
5. 下载 `credentials.json` 并放到项目根目录

### 2. AI API Key

**选项 A：使用 Claude API（推荐）**
1. 访问 [Anthropic Console](https://console.anthropic.com/)
2. 创建 API key
3. 复制 API key

**选项 B：使用 OpenAI API**
1. 访问 [OpenAI Platform](https://platform.openai.com/)
2. 创建 API key
3. 复制 API key

---

## 🚀 快速开始

### 步骤 1: 安装依赖

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境 (Windows)
.venv\Scripts\activate

# 激活虚拟环境 (Linux/Mac)
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 步骤 2: 配置环境变量

1. 复制示例配置：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件：

**使用 Claude API：**
```env
# AI 提供商
AI_PROVIDER=claude

# Claude API Key
ANTHROPIC_API_KEY=your_actual_claude_api_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# 应用配置
APP_BASE_URL=http://127.0.0.1:8000
LOG_LEVEL=INFO
```

**使用 OpenAI API：**
```env
# AI 提供商
AI_PROVIDER=openai

# OpenAI API Key
OPENAI_API_KEY=your_actual_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

# 应用配置
APP_BASE_URL=http://127.0.0.1:8000
LOG_LEVEL=INFO
```

### 步骤 3: 放置 Gmail 凭据

将下载的 `credentials.json` 放到项目根目录：
```
email-agent/
  ├── credentials.json  ← 放这里
  ├── .env
  ├── app/
  └── ...
```

### 步骤 4: Gmail 授权

1. 启动 Web 服务器：
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

2. 在浏览器中访问：
```
http://127.0.0.1:8000/auth/google
```

3. 按照提示完成 Google 授权

4. 授权成功后，可以关闭服务器（Ctrl+C）

### 步骤 5: 生成第一份报告

```bash
# 生成今天的报告
python scripts/generate_report.py

# 生成指定日期的报告
python scripts/generate_report.py --date 2026-01-30

# 生成最近 24 小时的报告
python scripts/generate_report.py --hours 24
```

---

## 📊 查看报告

### 方法 1: 使用 Python 脚本

创建 `view_report.py`：
```python
from datetime import date
from app.db.report_store import SkillReportStore

# 查看今天的报告
report = SkillReportStore.get_report_by_date(date.today())

if report:
    print(f"报告日期: {report['date']}")
    print(f"\n今日重点:")
    for i, h in enumerate(report['summary']['highlights'], 1):
        print(f"  {i}. {h}")

    print(f"\n待办事项:")
    for i, t in enumerate(report['summary']['todos'], 1):
        print(f"  {i}. {t}")
else:
    print("今天还没有报告")
```

### 方法 2: 使用 SQLite 客户端

```bash
# 使用 sqlite3 命令行
sqlite3 data/reports.db

# 查询所有报告
SELECT id, date, created_at FROM reports;

# 查询特定报告的内容
SELECT summary_json FROM reports WHERE date = '2026-01-30';
```

---

## 🔧 常见问题

### Q: 授权失败怎么办？

**A:** 检查以下几点：
1. `credentials.json` 是否在正确位置
2. 重定向 URI 是否匹配（必须是 `http://127.0.0.1:8000/auth/google/callback`）
3. Gmail API 是否已启用

重新授权：
```bash
# 删除旧的 token
rm data/token.json

# 重新启动服务器并访问授权页面
uvicorn app.main:app --host 127.0.0.1 --port 8000
# 然后访问 http://127.0.0.1:8000/auth/google
```

### Q: Claude API 调用失败？

**A:** 检查：
1. API key 是否正确配置在 `.env` 中
2. API key 是否有效（没有过期）
3. 网络连接是否正常

测试 API key：
```python
from anthropic import Anthropic
client = Anthropic(api_key="your_api_key")
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=100,
    messages=[{"role": "user", "content": "Hello"}]
)
print(response.content[0].text)
```

### Q: 没有拉取到邮件？

**A:** 可能原因：
1. 指定日期范围内确实没有邮件
2. Gmail 权限不足（需要 `gmail.readonly`）
3. 过滤条件太严格

尝试使用 `--hours 168` 拉取最近一周的邮件：
```bash
python scripts/generate_report.py --hours 168
```

### Q: 如何切换 AI 提供商？

**A:** 修改 `.env` 中的 `AI_PROVIDER`：
```env
# 使用 Claude
AI_PROVIDER=claude

# 或使用 OpenAI
AI_PROVIDER=openai
```

---

## 📝 配置说明

### AI 提供商对比

| 特性 | Claude | OpenAI |
|------|--------|--------|
| 模型 | claude-3-5-sonnet-20241022 | gpt-4o-mini / gpt-4o |
| 上下文 | 200K tokens | 128K tokens |
| 成本 | $3/$15 per 1M tokens | $0.15/$0.60 per 1M tokens |
| 推荐 | ✅ 更强大 | 更便宜 |

### 推荐配置

**开发/测试环境：**
```env
AI_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini  # 便宜
LOG_LEVEL=DEBUG
```

**生产环境：**
```env
AI_PROVIDER=claude
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022  # 更准确
LOG_LEVEL=INFO
```

---

## 🎯 下一步

系统现在已经可以完全使用了！

可选的增强功能：
- [ ] Web UI 界面
- [ ] API 端点
- [ ] 导出为 Markdown/HTML
- [ ] 定时任务（自动生成）
- [ ] 邮件通知

享受你的智能邮件日报系统！ 🎊
