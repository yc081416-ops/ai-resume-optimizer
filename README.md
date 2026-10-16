# AI 简历优化助手

上传简历 + 粘贴（或截图识别）目标岗位 JD，一键调用 DeepSeek 大模型输出**有依据**的结构化优化建议。
目标用户：正在找实习的大学生。

## 功能

### 核心分析
- **两步走分析**：① 先从 JD 提取「核心要求清单」（硬技能 / 经验要求 / 学历 / 加分项）；② 基于清单与简历**逐项对比**，给出「满足 / 部分满足 / 缺失」判定。
- **引用原文**：每条建议都引用简历或 JD 的原文片段，杜绝没有依据的空话，不编造简历中不存在的经历和数据。
- **分项加权打分**：技能匹配（40%）+ 经历匹配（40%）+ 学历与行业（20%），加权汇总总分，`temperature=0.3` 优先稳定。
- 输出 5 个部分：匹配度评分 / 缺失关键词 / 经历优化建议 / 改写示例 / 投递建议。

### 输入
- **简历**：上传 PDF / DOCX / TXT，单个文件 ≤ 5MB，解析后显示「已成功读取 X 字」。
- **JD 两种输入方式**（可切换）：
  1. **粘贴文本**：多行文本框 + 实时字数统计；
  2. **上传图片**：支持 JPG / PNG / WEBP（≤ 5MB），自动 **OCR** 识别文字并填入文本框，识别结果**可手动修改**。

### 结果与实用功能
- 结果**全宽**展示，5 个部分之间自动插入分隔线，阅读节奏清晰。
- 一键**下载为 Markdown 文件**，或直接全选复制。
- **历史记录**：本次会话内每次分析自动保存（时间 + JD 前 20 字摘要 + 总分），侧边栏可回看、删除、清空；**刷新页面后清空**。
- **多岗位对比**：一份简历 + 最多 5 个 JD 逐个分析，输出对比表（岗位 / 总分 / 分项分 / 一句话建议），按总分排序，帮用户决定先投哪个。
- **主题配色**：明亮 / 暗黑 / 柔和三套，侧边栏即时切换，无需刷新页面。
- 全中文界面，解析失败、OCR 失败、Key 无效、网络超时等情况均有中文提示，页面不会崩溃。

## 目录结构

```
.
├── app.py                  # 主程序（Streamlit 单文件）
├── requirements.txt        # Python 依赖
├── packages.txt            # apt 依赖（OCR 引擎，Streamlit Cloud 自动安装）
├── README.md
└── secrets.toml.example    # API Key 配置示例（复制为 .streamlit/secrets.toml 使用）
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

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 安装 OCR 引擎（仅「上传图片识别 JD」功能需要）

`pytesseract` 只是 Python 封装，还需要系统安装 **tesseract-ocr** 及**中文语言包 chi-sim**。

- **Windows**：下载并安装 [tesseract-ocr-w64 安装包](https://github.com/UB-Mannheim/tesseract/wiki)，
  安装向导中**必须勾选 Chinese (Simplified) 语言包**。若装在默认路径 `C:\Program Files\Tesseract-OCR\`，
  程序会自动找到；装在别处时设置环境变量 `TESSERACT_CMD` 指向 `tesseract.exe` 即可。
- **macOS**：`brew install tesseract tesseract-lang`
- **Ubuntu / Debian**：`sudo apt install tesseract-ocr tesseract-ocr-chi-sim`

> 未安装 OCR 引擎时，应用不会崩溃：选择「上传图片」会提示去安装，改用「粘贴文本」即可正常使用全部分析功能。

### 4. 配置 API Key

任选一种方式（详见下方第三节）。

### 5. 启动

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

## 二、部署到 Streamlit Cloud

1. 把项目（`app.py`、`requirements.txt`、`packages.txt`、`README.md`）推送到 GitHub 仓库。
   **不要提交 `.streamlit/secrets.toml`**，只提交 `secrets.toml.example`。
2. 打开 <https://share.streamlit.io>，用 GitHub 账号登录。
3. 点击 **New app** → 选择仓库、分支，Main file path 填 `app.py` → **Deploy**。
4. 部署时 Streamlit Cloud 会自动执行：
   - `packages.txt` → `tesseract-ocr`、`tesseract-ocr-chi-sim`（OCR 引擎 + 中文语言包）
   - `requirements.txt` → Python 依赖
5. 部署完成后进入 **Settings → Secrets**，粘贴以下内容并保存（保存后应用会自动重启）：

   ```toml
   DEEPSEEK_API_KEY = "sk-你的真实Key"
   ```

6. 回到应用页面，侧边栏会显示「已检测到 API Key（来源：Streamlit secrets）」，即可直接使用。

> 首次部署需要几分钟（要装系统包 + Python 依赖）。修改 `packages.txt` 后需要 **Reboot app** 才会重新执行 apt 安装。

## 三、配置 API Key

代码中**没有任何硬编码的 API Key**。程序按以下优先级自动读取：

| 优先级 | 方式 | 适用场景 |
| --- | --- | --- |
| 1 | Streamlit secrets（`.streamlit/secrets.toml` 中的 `DEEPSEEK_API_KEY`） | 本地开发、Streamlit Cloud 部署 |
| 2 | 环境变量 `DEEPSEEK_API_KEY` | 本地命令行 / 服务器 |
| 3 | 侧边栏密码框手动输入 | 临时试用，不想落盘保存 |

**方式 1：secrets.toml**

```bash
mkdir -p .streamlit
cp secrets.toml.example .streamlit/secrets.toml
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

## 四、使用说明

### 单岗位分析
1. 左侧上传简历，右侧粘贴 JD（或切到「上传图片」上传 JD 截图，识别后可修改）；
2. 点击页面中间的 **「开始分析」**；
3. 结果全宽展示，可展开「岗位核心要求清单」查看第一步提取结果，末尾可下载 `.md` 文件。

### 多岗位对比
1. 侧边栏把「分析模式」切到 **多岗位对比**；
2. 设置岗位数量（2–5 个），逐个填写岗位名称与 JD；
3. 点击 **「开始对比分析」**，等待逐个分析完成；
4. 得到对比表（岗位 / 总分 / 分项分 / 一句话建议，按总分排序）+ 每个岗位的完整分析。

> 多岗位对比每个岗位需要 2 次模型调用，岗位越多耗时越长，请耐心等待进度提示。

### 历史记录
每次分析自动记入侧边栏「历史记录」（最多保留最近 20 条）。可展开查看摘要、点「查看完整结果」回看、点「删除」单条移除。**历史记录仅存于当前会话，刷新页面后清空。**

### 主题配色
侧边栏「主题配色」可在 **明亮 / 暗黑 / 柔和** 之间切换，切换即时生效，无需刷新。

## 五、常见问题

| 现象 | 原因与处理 |
| --- | --- |
| 「未能从图片中识别出文字…」 | 截图太模糊 / 无文字 / 格式异常。换一张更清晰的截图，或改用「粘贴文本」 |
| 「未检测到 tesseract-ocr 引擎」 | 本地未安装 OCR 引擎，或安装了但不在默认路径。按第一节第 3 步安装，或设置 `TESSERACT_CMD` |
| 「OCR 缺少中文语言包 chi-sim」 | 安装 tesseract 时没勾选中文包。Windows 重新运行安装包勾选 Chinese (Simplified)，Linux 装 `tesseract-ocr-chi-sim` |
| 「文件解析失败，请检查文件格式」 | 文件为扫描版（图片型）PDF，或文件损坏。可换 DOCX / TXT，或使用可复制文字的 PDF |
| 「API Key 无效或已过期」 | Key 填写错误或已被删除，请到 DeepSeek 平台重新创建 |
| 「请求超时」/「网络连接失败」 | 网络不通或被代理拦截，检查网络后重试 |
| 「请求过于频繁或账户余额不足」 | 去 DeepSeek 平台检查账户余额，稍后重试 |
| 对比表里分数显示「-」 | 该次分析模型没按约定输出分数行，可点开下方该岗位的完整分析查看正文 |
| 提示未配置 API Key | 按第三节任选一种方式配置后重试 |

## 六、说明

- 模型：`deepseek-chat`，接口地址 `https://api.deepseek.com`（OpenAI 兼容），`temperature=0.3`
- 单岗位分析耗时通常在 30～90 秒（两次模型调用），请耐心等待加载动画完成
- 第 4 部分「改写示例」只优化表达，不编造简历中不存在的数据与经历；缺失的数字用「X」占位
- 单文件上传上限：简历与 JD 截图均为 5MB
