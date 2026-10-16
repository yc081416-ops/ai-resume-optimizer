# AI 简历优化助手

上传简历 + 粘贴目标岗位 JD，一键调用 DeepSeek 大模型输出结构化优化建议。
目标用户：正在找实习的大学生。

## 功能

- 简历上传与解析：支持 **PDF / DOCX / TXT**，单个文件 ≤ 5MB，解析后显示「已成功读取 X 字」
- JD 输入：多行文本框 + 实时字数统计
- 一键分析：调用 DeepSeek（`deepseek-chat`）输出 5 个部分的结构化建议
  （匹配度评分 / 缺失关键词 / 经历优化建议 / 改写示例 / 投递建议）
- 结果展示与导出：Markdown 渲染，支持下载为 `.md` 文件
- 全中文界面，解析失败、Key 无效、网络超时等情况均有中文提示，页面不会崩溃

## 目录结构

```
.
├── app.py                          # 主程序（Streamlit 单文件）
├── requirements.txt                # 依赖清单
├── README.md
└── .streamlit/
    └── secrets.toml.example        # API Key 配置示例（复制为 secrets.toml 使用）
```

## 一、本地运行

### 1. 准备环境

需要 Python 3.9 及以上版本。

```bash
# 建议使用虚拟环境
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 API Key

任选一种方式（详见下方第三节）。

### 4. 启动

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

## 二、部署到 Streamlit Cloud

1. 把项目（`app.py`、`requirements.txt`、`README.md`）推送到 GitHub 仓库。
   **不要提交 `.streamlit/secrets.toml`**，只提交 `secrets.toml.example`。
2. 打开 <https://share.streamlit.io>，用 GitHub 账号登录。
3. 点击 **New app** → 选择仓库、分支，Main file path 填 `app.py` → **Deploy**。
4. 部署完成后进入 **Settings → Secrets**，粘贴以下内容并保存（保存后应用会自动重启）：

   ```toml
   DEEPSEEK_API_KEY = "sk-你的真实Key"
   ```

5. 回到应用页面，侧边栏会显示「已检测到 API Key（来源：Streamlit secrets）」，即可直接使用。

> 依赖安装较慢：Streamlit Cloud 会根据 `requirements.txt` 自动安装依赖，首次部署需要等几分钟。

## 三、配置 API Key

代码中**没有任何硬编码的 API Key**。程序按以下优先级自动读取：

| 优先级 | 方式 | 适用场景 |
| --- | --- | --- |
| 1 | Streamlit secrets（`.streamlit/secrets.toml` 中的 `DEEPSEEK_API_KEY`） | 本地开发、Streamlit Cloud 部署 |
| 2 | 环境变量 `DEEPSEEK_API_KEY` | 本地命令行 / 服务器 |
| 3 | 侧边栏密码框手动输入 | 临时试用，不想落盘保存 |

**方式 1：secrets.toml**

```bash
# 复制示例文件
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

然后编辑 `.streamlit/secrets.toml`：

```toml
DEEPSEEK_API_KEY = "sk-你的真实Key"
```

**方式 2：环境变量**

```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "sk-你的真实Key"

# macOS / Linux
export DEEPSEEK_API_KEY="sk-你的真实Key"
```

**方式 3：侧边栏手动输入**

启动后在页面左侧侧边栏的密码框中填入 Key 即可（只保存在当前会话内存中，刷新页面后需重新输入）。

> 申请 Key：登录 <https://platform.deepseek.com> → API Keys → 创建新的 API Key。

## 四、常见问题

| 现象 | 原因与处理 |
| --- | --- |
| 「文件解析失败，请检查文件格式」 | 文件为扫描版（图片型）PDF，或文件损坏。可换 DOCX / TXT，或使用可复制文字的 PDF |
| 「API Key 无效或已过期」 | Key 填写错误或已被删除，请到 DeepSeek 平台重新创建 |
| 「请求超时」/「网络连接失败」 | 网络不通或被代理拦截，检查网络后重试 |
| 「请求过于频繁或账户余额不足」 | 去 DeepSeek 平台检查账户余额，稍后重试 |
| 提示未配置 API Key | 按第三节任选一种方式配置后重试 |

## 五、说明

- 模型：`deepseek-chat`，接口地址 `https://api.deepseek.com`（OpenAI 兼容）
- 单次分析耗时通常在 20～60 秒，请耐心等待加载动画完成
- 第 4 部分「改写示例」只优化表达，不编造简历中不存在的数据与经历
