# -*- coding: utf-8 -*-
"""
AI 简历优化助手（v2）
----------------------
v1 功能：上传简历（PDF / DOCX / TXT）+ 粘贴目标岗位 JD → DeepSeek 输出结构化优化建议。

v2 增量：
- V2-1 JD 支持图片 OCR（pytesseract + tesseract-ocr chi_sim）
- V2-2 界面重构：顶部头图 + 输入区双列 + 居中大按钮 + 结果全宽
- V2-3 结果展示：全宽渲染、小节分隔、末尾下载
- V2-4 主题配色：明亮 / 暗黑 / 柔和，CSS 变量即时切换
- V2-5 实用功能：会话内历史记录 + 多岗位对比表
- V2-6 准确性：JD 结构化 → 逐项对比两步走，引用原文，分项加权打分

运行方式：streamlit run app.py

注意：本文件严禁硬编码任何 API Key。
API Key 的读取优先级：Streamlit secrets > 环境变量 > 侧边栏手动输入。
"""

import io
import os
import re
from datetime import datetime

import streamlit as st

# ============================================================
# 常量配置
# ============================================================
APP_TITLE = "AI 简历优化助手"
APP_TAGLINE = "上传简历 + 粘贴目标岗位 JD，两步对比分析，给出有依据的优化建议"
MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024
SUPPORTED_TYPES = ["pdf", "docx", "txt"]
JD_IMAGE_TYPES = ["jpg", "jpeg", "png", "webp"]
MAX_JD_SLOTS = 5
HISTORY_LIMIT = 20

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_TIMEOUT = 180.0
TEMPERATURE = 0.3

MODE_SINGLE = "单岗位分析"
MODE_COMPARE = "多岗位对比"
INPUT_TEXT = "粘贴文本"
INPUT_IMAGE = "上传图片"

# OCR：优先中英文混合，缺语言包时逐级降级
OCR_LANG_CANDIDATES = ["chi_sim+eng", "chi_sim", "eng"]
OCR_CONFIG = "--psm 6"

OCR_FAIL_MSG = "未能从图片中识别出文字，请换一张更清晰的截图或改用文本粘贴"

# ============================================================
# 主题配置（V2-4）：三套配色，通过 CSS 变量注入
# ============================================================
THEMES = {
    "明亮": {
        "bg": "#f4f7fb",
        "surface": "#ffffff",
        "text": "#1f2937",
        "muted": "#6b7280",
        "primary": "#2563eb",
        "primary_hover": "#1d4ed8",
        "on_primary": "#ffffff",
        "border": "#e3e8ef",
        "soft": "#eef4ff",
        "shadow": "0 1px 3px rgba(16,24,40,.06), 0 8px 24px rgba(16,24,40,.05)",
        "hero_from": "#e8f0ff",
        "hero_to": "#f7fafe",
        "hero_text": "#1e3a8a",
        "hero_muted": "#3f5d97",
    },
    "暗黑": {
        "bg": "#0f1115",
        "surface": "#181b22",
        "text": "#e8eaed",
        "muted": "#9aa3af",
        "primary": "#6d8dff",
        "primary_hover": "#89a3ff",
        "on_primary": "#0b1020",
        "border": "#2b303b",
        "soft": "#1e232d",
        "shadow": "0 1px 3px rgba(0,0,0,.5), 0 10px 28px rgba(0,0,0,.35)",
        "hero_from": "#1c2437",
        "hero_to": "#141821",
        "hero_text": "#dbe4ff",
        "hero_muted": "#a8b3cc",
    },
    "柔和": {
        "bg": "#fbf6f1",
        "surface": "#fffdfa",
        "text": "#3d3733",
        "muted": "#857a70",
        "primary": "#c2704a",
        "primary_hover": "#a95c3a",
        "on_primary": "#ffffff",
        "border": "#ecdfd3",
        "soft": "#fdf1e7",
        "shadow": "0 1px 3px rgba(120,90,60,.06), 0 8px 24px rgba(120,90,60,.07)",
        "hero_from": "#fbe8d8",
        "hero_to": "#fdf6ef",
        "hero_text": "#8a4a26",
        "hero_muted": "#a3663f",
    },
}
DEFAULT_THEME = "明亮"


def build_css(theme_name: str) -> str:
    """把主题配置渲染成一段 CSS（变量 + 组件样式）。"""
    theme = THEMES.get(theme_name, THEMES[DEFAULT_THEME])
    return """
<style>
:root {{
  --bg: {bg};
  --surface: {surface};
  --text: {text};
  --muted: {muted};
  --primary: {primary};
  --primary-hover: {primary_hover};
  --on-primary: {on_primary};
  --border: {border};
  --soft: {soft};
  --shadow: {shadow};
  --hero-from: {hero_from};
  --hero-to: {hero_to};
  --hero-text: {hero_text};
  --hero-muted: {hero_muted};
}}

/* ---------- 页面基底 ---------- */
.stApp, [data-testid="stAppViewContainer"] {{
  background: var(--bg) !important;
  color: var(--text) !important;
}}
[data-testid="stHeader"] {{ background: transparent !important; }}
[data-testid="stSidebar"] {{
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] * {{ color: var(--text) !important; }}
[data-testid="stSidebar"] hr {{ border-color: var(--border) !important; }}
.block-container {{ padding-top: 2.1rem !important; padding-bottom: 3rem !important; max-width: 1250px; }}

/* ---------- 文字颜色（跟随主题，保证对比度） ---------- */
h1, h2, h3, h4, h5, h6 {{ color: var(--text) !important; }}
[data-testid="stMarkdownContainer"] * {{ color: var(--text); }}
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label {{ color: var(--text) !important; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {{ color: var(--muted) !important; }}
[data-testid="stRadio"] label, [data-testid="stRadio"] label * {{ color: var(--text) !important; }}
[data-testid="stCheckbox"] label * {{ color: var(--text) !important; }}

/* ---------- 顶部头图 ---------- */
.hero {{
  background: linear-gradient(135deg, var(--hero-from) 0%, var(--hero-to) 100%);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 26px 30px 22px;
  margin-bottom: 20px;
  box-shadow: var(--shadow);
}}
.hero h1 {{
  margin: 0 !important;
  font-size: 2.05rem !important;
  font-weight: 800 !important;
  letter-spacing: .5px;
  color: var(--hero-text) !important;
}}
.hero p {{
  margin: 9px 0 0 !important;
  font-size: 1rem;
  color: var(--hero-muted) !important;
}}
.hero-tags {{ margin-top: 14px; }}
.hero-tag {{
  display: inline-block;
  margin: 0 8px 6px 0;
  padding: 3px 11px;
  border-radius: 999px;
  font-size: .8rem;
  background: var(--surface);
  color: var(--hero-text) !important;
  border: 1px solid var(--border);
}}

/* ---------- 区块小标题 ---------- */
.sec-title {{
  margin: 0 0 2px 1px;
  font-size: 1.06rem;
  font-weight: 700;
  color: var(--text) !important;
}}
.sec-sub {{
  margin: 0 0 12px 1px;
  font-size: .84rem;
  color: var(--muted) !important;
}}

/* ---------- 卡片（st.container(border=True)） ---------- */
[data-testid="stVerticalBlockBorderWrapper"] {{
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 16px !important;
  box-shadow: var(--shadow) !important;
}}

/* ---------- 按钮 ---------- */
.stButton > button, .stDownloadButton > button {{
  background: var(--surface) !important;
  color: var(--text) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
  border-color: var(--primary) !important;
  color: var(--primary) !important;
}}
[data-testid="stBaseButton-primary"],
.stButton > button[kind="primary"] {{
  background: var(--primary) !important;
  border: 1px solid var(--primary) !important;
  font-weight: 700 !important;
  letter-spacing: .5px;
  box-shadow: 0 6px 18px rgba(0,0,0,.10);
}}
[data-testid="stBaseButton-primary"] *,
.stButton > button[kind="primary"] * {{ color: var(--on-primary) !important; }}
[data-testid="stBaseButton-primary"]:hover,
.stButton > button[kind="primary"]:hover {{ background: var(--primary-hover) !important; }}

/* ---------- 输入控件 ---------- */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input {{
  background: var(--surface) !important;
  color: var(--text) !important;
  border-radius: 10px !important;
}}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {{ color: var(--muted) !important; opacity: .85; }}
[data-testid="stFileUploaderDropzone"] {{
  background: var(--soft) !important;
  border: 1px dashed var(--border) !important;
  border-radius: 12px !important;
}}
[data-testid="stFileUploaderDropzone"] * {{ color: var(--text) !important; background: transparent !important; }}
[data-testid="stFileUploaderDropzone"] button {{
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  color: var(--text) !important;
}}
[data-testid="stFileUploaderFile"] {{ background: var(--soft) !important; border-radius: 10px !important; }}
[data-testid="stFileUploaderFile"] * {{ color: var(--text) !important; background: transparent !important; }}

/* ---------- 折叠面板 ---------- */
[data-testid="stExpander"] {{
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  overflow: hidden;
}}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * {{ color: var(--text) !important; }}
[data-testid="stExpander"] summary:hover {{ color: var(--primary) !important; }}

/*
  提示框：Streamlit 用的是半透明语义色底，会跟页面底色叠加。
  文字必须跟随主题文字色，否则暗黑主题下会出现「深字叠深底」不可读。
*/
[data-testid="stAlert"] {{ border-radius: 12px !important; }}
[data-testid="stAlert"] *,
[data-testid="stAlert"] p,
[data-testid="stAlert"] [data-testid="stMarkdownContainer"] * {{ color: var(--text) !important; }}

/* 运行状态容器（多岗位对比的进度块）同样跟随主题 */
[data-testid="stStatusWidget"],
[data-testid="stStatus"] {{
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
}}
[data-testid="stStatusWidget"] *,
[data-testid="stStatus"] * {{ color: var(--text) !important; }}

/* ---------- 代码块 / 表格 / 分隔线 ---------- */
code, pre, [data-testid="stCode"] * {{ color: var(--text) !important; background: var(--soft) !important; }}
[data-testid="stTable"] table, [data-testid="stTable"] th, [data-testid="stTable"] td {{
  color: var(--text) !important;
  border-color: var(--border) !important;
}}
[data-testid="stTable"] thead th {{ background: var(--soft) !important; font-weight: 600; }}
[data-testid="stTable"] tbody tr {{ background: var(--surface) !important; }}
hr {{ border-color: var(--border) !important; }}
</style>
""".format(**theme)


# ============================================================
# 简历文件解析（v1 逻辑保持不变）
# ============================================================
def _parse_pdf(file_bytes: bytes) -> str:
    """解析 PDF 文件为纯文本。"""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _parse_docx(file_bytes: bytes) -> str:
    """
    解析 DOCX 文件为纯文本。

    按文档顺序提取所有 w:p 段落（含文本框、形状内的段落——很多中文简历模板
    把文字放在文本框里，document.paragraphs 抓不到），并去掉连续重复行。
    """
    import docx
    from docx.oxml.ns import qn

    document = docx.Document(io.BytesIO(file_bytes))
    lines = []
    for p in document.element.iter(qn("w:p")):
        txt = "".join(e.text for e in p.iter(qn("w:t")) if e.text).strip()
        if txt and txt != (lines[-1] if lines else None):
            lines.append(txt)
    return "\n".join(lines)


def _parse_txt(file_bytes: bytes) -> str:
    """解析 TXT 文件为纯文本，自动尝试常见中文编码。"""
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk", "utf-16"):
        try:
            return file_bytes.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError("无法识别文本编码")


def parse_resume(uploaded_file) -> str:
    """
    根据扩展名解析上传的简历文件，返回纯文本。

    解析失败时抛出 ValueError，由上层统一转为中文提示。
    """
    name = uploaded_file.name or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""

    if ext not in SUPPORTED_TYPES:
        raise ValueError("不支持的文件格式，请上传 PDF / DOCX / TXT 文件")

    file_bytes = uploaded_file.getvalue()
    if not file_bytes:
        raise ValueError("文件内容为空")

    if ext == "pdf":
        text = _parse_pdf(file_bytes)
    elif ext == "docx":
        text = _parse_docx(file_bytes)
    else:
        text = _parse_txt(file_bytes)

    text = text.replace("\x00", "").strip()
    if not text:
        raise ValueError("未能从文件中提取到文字，可能是扫描件或空文件")
    return text


def extract_resume_text(uploaded_file) -> tuple[bool, str]:
    """
    安全解析入口。

    返回 (是否成功, 文本或错误信息)。
    """
    try:
        return True, parse_resume(uploaded_file)
    except Exception:
        return False, "文件解析失败，请检查文件格式"


def file_size(uploaded_file) -> int:
    """获取上传文件大小（字节）。"""
    size = getattr(uploaded_file, "size", None)
    if size is None:
        try:
            size = len(uploaded_file.getvalue())
        except Exception:
            size = 0
    return size or 0


# ============================================================
# 图片 OCR（V2-1）
# ============================================================
def find_tesseract_cmd() -> str:
    """
    定位 tesseract 可执行文件。

    优先级：环境变量 TESSERACT_CMD > 常见安装路径 > PATH。找不到返回空串。
    """
    import shutil

    env_cmd = os.getenv("TESSERACT_CMD", "").strip()
    if env_cmd and os.path.exists(env_cmd):
        return env_cmd

    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
        os.path.expanduser("~/.local/bin/tesseract"),
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/opt/homebrew/bin/tesseract",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path

    return shutil.which("tesseract") or ""


def _preprocess_image(img):
    """OCR 前预处理：转灰度，过小的图放大，提升截图识别率。"""
    from PIL import Image

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    gray = img.convert("L") if img.mode == "RGB" else img

    width, height = gray.size
    if width and width < 1000:
        scale = min(3.0, 1000.0 / width)
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        gray = gray.resize((int(width * scale), int(height * scale)), resample)
    return gray


def _clean_ocr_text(text: str) -> str:
    """清理 OCR 结果：去掉空行与行首行尾空白。"""
    text = (text or "").replace("\x0c", "\n").replace("\x00", "")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def ocr_image(uploaded_file) -> tuple[bool, str]:
    """
    对上传的 JD 截图做 OCR。

    返回 (是否成功, 识别文本或中文错误提示)。任何异常都不会抛到页面。
    """
    try:
        import pytesseract
        from PIL import Image, UnidentifiedImageError
    except Exception:
        return False, "缺少 OCR 依赖，请先执行 pip install -r requirements.txt"

    try:
        cmd = find_tesseract_cmd()
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd

        try:
            img = Image.open(io.BytesIO(uploaded_file.getvalue()))
            img.load()
            gray = _preprocess_image(img)
        except (UnidentifiedImageError, OSError, ValueError):
            return False, OCR_FAIL_MSG

        text = ""
        last_error = None
        for lang in OCR_LANG_CANDIDATES:
            try:
                text = pytesseract.image_to_string(gray, lang=lang, config=OCR_CONFIG)
                break
            except pytesseract.TesseractError as exc:
                last_error = exc
                message = str(exc).lower()
                # 语言包缺失时降级到下一档语言，其余错误直接抛出
                if "lang" in message or "tessdata" in message or "failed loading" in message:
                    continue
                raise
        else:
            if last_error is not None:
                raise last_error

        text = _clean_ocr_text(text)
        if not text:
            return False, OCR_FAIL_MSG
        return True, text
    except Exception as exc:  # noqa: BLE001 - 统一转为中文提示，保证页面不崩溃
        name = type(exc).__name__
        if "TesseractNotFound" in name:
            return False, (
                "未检测到 tesseract-ocr 引擎。本地请先安装 tesseract-ocr（含中文语言包 chi_sim），"
                "或在 Streamlit Cloud 上通过 packages.txt 自动安装。"
            )
        message = str(exc).lower()
        if "chi_sim" in message or "tessdata" in message or "failed loading" in message:
            return False, "OCR 缺少中文语言包 chi-sim，请安装后重试（apt: tesseract-ocr-chi-sim）。"
        return False, OCR_FAIL_MSG


# ============================================================
# API Key 读取（优先级：secrets > 环境变量 > 手动输入）
# ============================================================
def _valid(key) -> bool:
    return bool(key) and isinstance(key, str) and key.strip() != "" and not key.strip().startswith("sk-xxx")


def _from_secrets() -> str:
    """
    从 Streamlit secrets 读取 Key。

    注意：直接访问 st.secrets 时，若本地不存在 secrets.toml，
    Streamlit 会在页面上渲染一段英文错误提示。因此这里先用官方的
    load_if_toml_exists() 探测（它不会报错），再取值。
    """
    secrets = getattr(st, "secrets", None)
    if secrets is None:
        return ""
    try:
        if not secrets.load_if_toml_exists():
            # 没有任何 secrets.toml，静默跳过，不打扰用户
            return ""
        return secrets.get("DEEPSEEK_API_KEY", "") or ""
    except Exception:
        return ""


def resolve_api_key(manual_key: str = "") -> tuple[str, str]:
    """
    按优先级获取 API Key。

    返回 (key, 来源说明)。key 为空字符串表示未配置。
    """
    key = _from_secrets()
    if _valid(key):
        return key.strip(), "Streamlit secrets"

    key = os.getenv("DEEPSEEK_API_KEY", "")
    if _valid(key):
        return key.strip(), "环境变量"

    if _valid(manual_key):
        return manual_key.strip(), "侧边栏手动输入"

    return "", ""


# ============================================================
# Prompt 模板（V2-6：两步走）
# ============================================================
JD_EXTRACT_PROMPT = """你是一位资深招聘顾问。请从下面的职位描述（JD）中提取「核心要求清单」，供后续与候选人简历逐项对比使用。

【JD 原文】
{jd_text}

要求：
1. 只提取 JD 中真实出现的要求，不得补充 JD 里没有的内容，不得推测。
2. 每条要求后用括号标注 JD 原文片段（不超过 20 字）作为依据。
3. 按以下四个分组输出（中文，Markdown 格式），某组没有内容时写「无」：

## 硬技能
## 经验要求
## 学历要求
## 加分项
"""

ANALYSIS_PROMPT = """你是一位资深招聘顾问，擅长简历优化。请基于下面的「简历原文」「JD 原文」和「核心要求清单」，逐项对比后输出结构化建议。

【简历原文】
{resume_text}

【JD 原文】
{jd_text}

【核心要求清单】
{checklist}

分析要求（必须严格遵守）：
1. 逐项核对：对清单中的每一条要求，给出「满足 / 部分满足 / 缺失」判定，并引用简历中的原文片段作为依据。简历里确实没有的写「简历未提及」，严禁编造。
2. 引用原文：每条建议都必须引用简历或 JD 的原文片段，禁止没有依据的空话。
3. 分项打分：技能匹配（权重 40%）、经历匹配（权重 40%）、学历与行业（权重 20%），各项 0-100 分；
   总分 = 技能×0.4 + 经历×0.4 + 学历行业×0.2，四舍五入取整。

请严格按以下结构输出（中文，Markdown 格式）：

## 1. 匹配度评分
先用表格列出三个分项：技能匹配（40%）、经历匹配（40%）、学历与行业（20%），给出各自得分与加权分，最后给出总分（0-100）。
再用 2-3 句话说明理由，理由中必须引用简历或 JD 的原文。

## 2. 缺失关键词
列出 JD 中出现但简历中缺失/薄弱的 5-8 个关键词，按重要性排序。每个关键词后用括号标注它在 JD 中的原文出处。

## 3. 经历优化建议
针对简历中的每段经历，指出问题（空话/缺数字/缺结果/与岗位无关），并给出改写方向。
每条格式：**原文问题**（引用简历原句） → **改写建议**。
判定为「缺失」的要求也要单列一条，并说明可以在哪段经历中补齐。

## 4. 改写示例
挑选简历中最需要改的一段经历，给出完整改写版本（保留真实信息，只优化表达；不要编造数据或经历；简历中没有的数字一律用「X」占位）。

## 5. 投递建议
基于总分，给出是否建议投递的明确结论 + 投递前必须改的 Top 3。

最后另起一行，输出下面这个机器可读区块（用于生成对比表，必须原样输出、不要放进代码块、不要改动键名）：

<!--SCORES
技能匹配: 分数
经历匹配: 分数
学历与行业: 分数
总分: 分数
一句话建议: 不超过 25 字的投递建议
-->
"""

SYSTEM_PROMPT = (
    "你是一位资深招聘顾问，服务对象是正在找实习的大学生。"
    "你的建议必须具体、可操作，严格基于用户提供的简历与 JD 原文，"
    "每一条结论都要能对应到原文片段，严禁编造简历中不存在的数字、项目或经历。"
)

SCORE_BLOCK_RE = re.compile(r"<!--\s*SCORES(.*?)-->", re.S | re.I)


def build_extract_prompt(jd_text: str) -> str:
    """第一步：JD → 核心要求清单。"""
    return JD_EXTRACT_PROMPT.replace("{jd_text}", jd_text)


def build_analysis_prompt(resume_text: str, jd_text: str, checklist: str) -> str:
    """第二步：逐项对比 + 结构化建议。"""
    return (
        ANALYSIS_PROMPT.replace("{resume_text}", resume_text)
        .replace("{jd_text}", jd_text)
        .replace("{checklist}", checklist or "（未提取到清单，请直接依据 JD 原文逐项核对）")
    )


# ============================================================
# 结果解析与排版
# ============================================================
def strip_score_block(report: str) -> str:
    """去掉机器可读的 SCORES 区块，返回可直接展示的正文。"""
    return SCORE_BLOCK_RE.sub("", report or "").rstrip()


def _grab_score(text: str, keys) -> int:
    """
    从文本中抓取某个分项的分数。

    先尝试「键：分数」这种最可靠的写法；失败后逐行扫描，
    跳过含权重/公式的行（避免把 40% 或公式里的系数当成得分），
    取该行最后一个不以 % 结尾的整数（表格行最后一个数字才是得分）。
    """
    for key in keys:
        match = re.search(r"%s\s*[:：]\s*\**\s*(\d{1,3})" % re.escape(key), text)
        if match:
            value = int(match.group(1))
            if 0 <= value <= 100:
                return value

        for line in text.splitlines():
            if key not in line:
                continue
            if "权重" in line or "×" in line or "四舍五入" in line or line.count("%") > 1:
                continue
            numbers = [
                int(number)
                for number in re.findall(r"(\d{1,3})(?![\d.])(?!\s*%)", line)
            ]
            numbers = [number for number in numbers if 0 <= number <= 100]
            if numbers:
                return numbers[-1]
    return None


def parse_scores(report: str) -> dict:
    """
    从分析结果里解析分项得分与总分。

    优先读 SCORES 区块，读不到再退回正文正则；总分缺失时按权重计算。
    """
    report = report or ""
    block_match = SCORE_BLOCK_RE.search(report)
    block = block_match.group(1) if block_match else report

    skill = _grab_score(block, ["技能匹配", "技能"])
    experience = _grab_score(block, ["经历匹配", "经历"])
    education = _grab_score(block, ["学历与行业", "学历", "行业"])
    total = _grab_score(block, ["总分", "综合得分", "总体评分", "匹配度"])

    if total is None and None not in (skill, experience, education):
        total = round(skill * 0.4 + experience * 0.4 + education * 0.2)

    advice = ""
    advice_match = re.search(r"一句话建议\s*[:：]\s*(.+)", block)
    if advice_match:
        advice = advice_match.group(1).strip().strip("*` ").splitlines()[0][:60]
    if not advice:
        # 退回第 5 部分的第一句实质内容
        tail = report.split("## 5.", 1)
        if len(tail) > 1:
            for line in tail[1].splitlines():
                cleaned = line.strip().lstrip("#*- ").strip()
                if len(cleaned) > 6:
                    advice = cleaned[:60]
                    break

    return {"skill": skill, "experience": experience, "education": education, "total": total, "advice": advice}


def format_report(report: str) -> str:
    """在 5 个小节之间插入分隔线，保持阅读节奏（V2-3）。"""
    lines = (report or "").splitlines()
    out = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^#{2,4}\s*\d+[\.、]", stripped) and any(item.strip() for item in out):
            out.extend(["", "---", ""])
        out.append(line)
    return "\n".join(out)


# ============================================================
# DeepSeek 调用
# ============================================================
def _friendly_error(exc: Exception) -> str:
    """把 SDK 异常翻译成中文提示。"""
    try:
        from openai import (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            AuthenticationError,
            BadRequestError,
            NotFoundError,
            PermissionDeniedError,
            RateLimitError,
        )
    except Exception:
        return "AI 分析失败：{}".format(exc)

    # 注意：APITimeoutError 是 APIConnectionError 的子类，需先判断
    if isinstance(exc, APITimeoutError):
        return "请求超时：DeepSeek 接口响应过慢，请稍后重试。"
    if isinstance(exc, AuthenticationError):
        return "API Key 无效或已过期，请检查 DEEPSEEK_API_KEY 是否正确。"
    if isinstance(exc, PermissionDeniedError):
        return "API Key 无访问权限，请确认账号状态或更换 Key。"
    if isinstance(exc, RateLimitError):
        return "请求过于频繁或账户余额不足，请稍后重试或检查 DeepSeek 账户余额。"
    if isinstance(exc, NotFoundError):
        return "接口地址或模型不存在，请确认 base_url 与模型名称（deepseek-chat）正确。"
    if isinstance(exc, BadRequestError):
        return "请求参数有误，可能是简历或 JD 内容过长，请精简后重试。"
    if isinstance(exc, APIConnectionError):
        return "网络连接失败：无法访问 DeepSeek 接口，请检查网络或代理设置。"
    if isinstance(exc, APIStatusError):
        return "接口返回错误（HTTP {}），请稍后重试。".format(getattr(exc, "status_code", "未知"))
    return "AI 分析失败：{}".format(exc)


def call_deepseek(api_key: str, prompt: str) -> tuple[bool, str]:
    """
    调用 DeepSeek Chat API。

    返回 (是否成功, 结果 Markdown 或中文错误提示)。
    """
    try:
        from openai import OpenAI
    except Exception:
        return False, "缺少 openai 依赖，请先执行 pip install -r requirements.txt"

    try:
        client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, timeout=DEEPSEEK_TIMEOUT)
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=TEMPERATURE,
            stream=False,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            return False, "AI 未返回内容，请稍后重试。"
        return True, content
    except Exception as exc:  # noqa: BLE001 - 统一转为中文提示，保证页面不崩溃
        return False, _friendly_error(exc)


def analyze_one(api_key: str, resume_text: str, jd_text: str) -> dict:
    """
    两步分析单个岗位（V2-6）。

    返回 dict：ok / error / checklist / report / scores
    """
    ok, checklist = call_deepseek(api_key, build_extract_prompt(jd_text))
    if not ok:
        return {
            "ok": False,
            "error": "第一步（提取岗位核心要求）失败：" + checklist,
            "checklist": "",
            "report": "",
            "scores": {},
        }

    ok, report = call_deepseek(api_key, build_analysis_prompt(resume_text, jd_text, checklist))
    if not ok:
        return {
            "ok": False,
            "error": "第二步（逐项对比分析）失败：" + report,
            "checklist": checklist,
            "report": "",
            "scores": {},
        }

    return {
        "ok": True,
        "error": "",
        "checklist": checklist,
        "report": strip_score_block(report),
        "scores": parse_scores(report),
    }


# ============================================================
# 小工具
# ============================================================
def wide_kwargs(func) -> dict:
    """
    适配不同 Streamlit 版本的撑满宽度参数。

    新版用 width="stretch"，旧版用 use_container_width=True。
    """
    import inspect

    try:
        if "width" in inspect.signature(func).parameters:
            return {"width": "stretch"}
    except (TypeError, ValueError):
        pass
    return {"use_container_width": True}


def jd_summary(jd_text: str, length: int = 20) -> str:
    """取 JD 前 N 个字符作为历史记录摘要。"""
    text = re.sub(r"\s+", " ", (jd_text or "").strip())
    return text[:length] if text else "（空）"


def now_stamp() -> tuple[str, str]:
    """返回 (显示时间, 文件名时间戳)。"""
    now = datetime.now()
    return now.strftime("%H:%M:%S"), now.strftime("%Y%m%d_%H%M%S")


def add_history(name: str, jd_text: str, report: str, scores: dict, checklist: str) -> None:
    """把一次分析结果写入会话内历史记录（V2-5）。"""
    display, stamp = now_stamp()
    st.session_state.history.insert(
        0,
        {
            "name": name,
            "time": display,
            "ts": stamp,
            "summary": jd_summary(jd_text),
            "score": (scores or {}).get("total"),
            "report": report,
            "checklist": checklist,
            "advice": (scores or {}).get("advice", ""),
        },
    )
    del st.session_state.history[HISTORY_LIMIT:]


# ============================================================
# 会话状态
# ============================================================
def init_state() -> None:
    st.session_state.setdefault("resume_text", "")
    st.session_state.setdefault("resume_msg", None)
    st.session_state.setdefault("weak_resume", False)
    st.session_state.setdefault("result", "")
    st.session_state.setdefault("result_error", "")
    st.session_state.setdefault("analyzed_at", "")
    st.session_state.setdefault("result_source", "")
    st.session_state.setdefault("jd_checklist", "")
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("compare_results", [])
    st.session_state.setdefault("compare_error", "")
    st.session_state.setdefault("theme_name", DEFAULT_THEME)
    st.session_state.setdefault("mode", MODE_SINGLE)
    st.session_state.setdefault("jd_input_mode", INPUT_TEXT)
    for index in range(1, MAX_JD_SLOTS + 1):
        st.session_state.setdefault("cmp_input_mode_%d" % index, INPUT_TEXT)


# ============================================================
# 侧边栏
# ============================================================
def render_sidebar() -> str:
    """渲染侧边栏（模式 / 主题 / Key / 历史），返回手动输入的 API Key。"""
    with st.sidebar:
        st.markdown("#### 分析模式")
        st.radio("分析模式", [MODE_SINGLE, MODE_COMPARE], key="mode", label_visibility="collapsed")

        st.divider()
        st.markdown("#### 主题配色")
        st.radio("主题配色", list(THEMES.keys()), key="theme_name", label_visibility="collapsed")
        st.caption("切换即时生效，无需刷新页面。")

        st.divider()
        st.markdown("#### API Key")
        auto_key, source = resolve_api_key()
        if auto_key:
            st.success("已检测到 API Key（来源：{}）".format(source))
        else:
            st.warning("未检测到 API Key，请在下方手动填写。")

        manual_key = st.text_input(
            "DeepSeek API Key",
            type="password",
            placeholder="sk-xxxxxxxx",
            help="仅在未配置 secrets / 环境变量时需要填写，Key 只保存在当前会话内存中。",
        )

        st.caption("读取优先级：")
        st.caption("1. Streamlit secrets")
        st.caption("2. 环境变量 DEEPSEEK_API_KEY")
        st.caption("3. 本输入框手动填写")
    return manual_key


def render_history() -> None:
    """
    侧边栏历史记录：回看 / 删除（V2-5）。

    注意：本函数必须在分析逻辑之后调用——Streamlit 是按调用顺序渲染的，
    若放在侧边栏前半段，刚完成的这次分析要等下一次交互才会出现在列表里。
    """
    with st.sidebar:
        st.divider()
        st.markdown("#### 历史记录")
        st.caption("仅保存在当前会话（最多 {} 条），刷新页面后清空。".format(HISTORY_LIMIT))

        history = st.session_state.history
        if not history:
            st.caption("暂无记录，完成一次分析后会自动保存。")
            return

        for index, item in enumerate(list(history)):
            score = item.get("score")
            label = "{} · {} · {}分".format(item["time"], item["summary"], score if score is not None else "-")
            with st.expander(label, expanded=False):
                st.caption("岗位：{}".format(item.get("name") or "未命名岗位"))
                st.caption("JD 摘要：{}".format(item["summary"]))
                st.caption("总分：{}".format(score if score is not None else "未解析"))
                if item.get("advice"):
                    st.caption("建议：{}".format(item["advice"]))
                if st.button("查看完整结果", key="hist_view_%d" % index, **wide_kwargs(st.button)):
                    st.session_state.result = item.get("report", "")
                    st.session_state.jd_checklist = item.get("checklist", "")
                    st.session_state.result_error = ""
                    st.session_state.analyzed_at = item.get("ts", "")
                    st.session_state.result_source = "历史记录（{}）".format(item["time"])
                    st.rerun()
                if st.button("删除", key="hist_del_%d" % index, **wide_kwargs(st.button)):
                    st.session_state.history.pop(index)
                    st.rerun()

        if st.button("清空历史记录", key="hist_clear", **wide_kwargs(st.button)):
            st.session_state.history = []
            st.rerun()


# ============================================================
# 输入区
# ============================================================
def render_hero() -> None:
    """顶部标题区（V2-2）。"""
    st.markdown(
        """
<div class="hero">
  <h1>{title}</h1>
  <p>{tagline}</p>
  <div class="hero-tags">
    <span class="hero-tag">PDF / DOCX / TXT 解析</span>
    <span class="hero-tag">JD 截图 OCR</span>
    <span class="hero-tag">分项打分</span>
    <span class="hero-tag">多岗位对比</span>
    <span class="hero-tag">三套主题</span>
  </div>
</div>
""".format(title=APP_TITLE, tagline=APP_TAGLINE),
        unsafe_allow_html=True,
    )


def render_resume_card() -> None:
    """左列：简历上传与解析（v1 功能保持不变）。"""
    st.markdown('<div class="sec-title">① 简历</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sec-sub">支持 PDF / DOCX / TXT，单个文件 ≤ {} MB</div>'.format(MAX_FILE_SIZE_MB),
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "上传简历文件",
        type=SUPPORTED_TYPES,
        accept_multiple_files=False,
        key="resume_upload",
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        size = file_size(uploaded_file)
        if size > MAX_FILE_SIZE:
            st.session_state.resume_text = ""
            st.session_state.resume_msg = None
            st.error("文件过大（{:.1f} MB），请上传不超过 {} MB 的文件。".format(size / 1024 / 1024, MAX_FILE_SIZE_MB))
        else:
            signature = (uploaded_file.name, size)
            if st.session_state.get("_resume_signature") != signature:
                ok, text_or_error = extract_resume_text(uploaded_file)
                st.session_state["_resume_signature"] = signature
                if ok:
                    st.session_state.resume_text = text_or_error
                    st.session_state.weak_resume = len(text_or_error) < 200
                    st.session_state.resume_msg = "已成功读取 {} 字".format(len(text_or_error))
                else:
                    st.session_state.resume_text = ""
                    st.session_state.resume_msg = text_or_error

    if st.session_state.resume_text:
        st.success("已成功读取 {} 字".format(len(st.session_state.resume_text)))
        with st.expander("查看解析出的简历文本", expanded=False):
            if st.session_state.weak_resume:
                st.warning("提示：文本内容较少，可能是扫描版 PDF（图片型），建议改用 DOCX / TXT 或可复制文字的 PDF。")
            st.text_area(
                "简历原文",
                st.session_state.resume_text,
                height=200,
                disabled=True,
                label_visibility="collapsed",
            )
    elif st.session_state.resume_msg:
        st.error("文件解析失败，请检查文件格式")
        with st.expander("失败详情", expanded=False):
            st.write(st.session_state.resume_msg)


def render_jd_image_ocr(slot_key: str, target_key: str) -> str:
    """
    渲染 JD 图片上传 + OCR，识别结果写入 target_key 对应的会话状态。

    返回 "" 或 "ok:字数" 或 "err:提示"。
    """
    uploaded_image = st.file_uploader(
        "上传 JD 截图",
        type=JD_IMAGE_TYPES,
        accept_multiple_files=False,
        key=slot_key,
        label_visibility="collapsed",
        help="支持 JPG / PNG / WEBP，≤ {} MB".format(MAX_FILE_SIZE_MB),
    )

    if uploaded_image is None:
        return ""

    size = file_size(uploaded_image)
    if size > MAX_FILE_SIZE:
        st.error("图片过大（{:.1f} MB），请上传不超过 {} MB 的图片。".format(size / 1024 / 1024, MAX_FILE_SIZE_MB))
        return ""

    signature = (uploaded_image.name, size)
    signature_key = "_ocr_signature_" + slot_key
    if st.session_state.get(signature_key) == signature:
        # 同一张图已经识别过，避免每次 rerun 重复 OCR
        return ""

    with st.spinner("正在识别图片文字…"):
        ok, text_or_error = ocr_image(uploaded_image)
    st.session_state[signature_key] = signature

    if ok:
        st.session_state[target_key] = text_or_error
        return "ok:{}".format(len(text_or_error))
    return "err:" + text_or_error


def render_single_jd_card() -> None:
    """右列：单岗位 JD 输入（粘贴文本 / 上传图片二选一）。"""
    st.markdown('<div class="sec-title">② 目标岗位 JD</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">粘贴文本或上传 JD 截图，识别结果可手动修改</div>', unsafe_allow_html=True)

    mode = st.radio(
        "JD 输入方式",
        [INPUT_TEXT, INPUT_IMAGE],
        key="jd_input_mode",
        horizontal=True,
        label_visibility="collapsed",
    )

    if mode == INPUT_IMAGE:
        result = render_jd_image_ocr("jd_image", "jd_text")
        if result.startswith("ok:"):
            st.success("已从图片识别出 {} 字，可在下方修改后分析。".format(result.split(":", 1)[1]))
        elif result.startswith("err:"):
            st.error(result.split(":", 1)[1])
        else:
            st.caption("上传 JD 截图后会自动识别并填入下方文本框。")

    jd_text = st.text_area(
        "目标岗位 JD",
        placeholder="在此粘贴目标岗位的职位描述（JD）",
        height=232,
        key="jd_text",
        label_visibility="collapsed",
    )
    st.caption("JD 字数：{} 字".format(len(jd_text.strip()) if jd_text else 0))


def render_compare_jd_card() -> list:
    """右列：多岗位对比的 JD 输入（最多 5 个，逐个粘贴 / 上传）。"""
    st.markdown('<div class="sec-title">② 目标岗位（最多 {} 个）</div>'.format(MAX_JD_SLOTS), unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">逐个填写岗位，分析后生成对比表</div>', unsafe_allow_html=True)

    count = st.number_input(
        "参与对比的岗位数量",
        min_value=2,
        max_value=MAX_JD_SLOTS,
        step=1,
        key="cmp_count",
    )

    slots = []
    for index in range(1, int(count) + 1):
        key_name = "cmp_name_%d" % index
        st.session_state.setdefault(key_name, "")
        with st.expander(
            "岗位 {}：{}".format(index, st.session_state[key_name] or "未命名"),
            expanded=(index == 1),
        ):
            name = st.text_input(
                "岗位名称",
                key=key_name,
                placeholder="例如：字节跳动 · 后端开发实习生",
            )
            input_mode = st.radio(
                "JD 输入方式",
                [INPUT_TEXT, INPUT_IMAGE],
                key="cmp_input_mode_%d" % index,
                horizontal=True,
                label_visibility="collapsed",
            )
            if input_mode == INPUT_IMAGE:
                result = render_jd_image_ocr("cmp_image_%d" % index, "cmp_jd_%d" % index)
                if result.startswith("ok:"):
                    st.success("已识别 {} 字，可修改后分析。".format(result.split(":", 1)[1]))
                elif result.startswith("err:"):
                    st.error(result.split(":", 1)[1])
            jd_text = st.text_area(
                "JD 文本",
                placeholder="在此粘贴该岗位的职位描述（JD）",
                height=150,
                key="cmp_jd_%d" % index,
                label_visibility="collapsed",
            )
            st.caption("JD 字数：{} 字".format(len(jd_text.strip()) if jd_text else 0))
        slots.append({"index": index, "name": name.strip() or "岗位 {}".format(index), "jd": jd_text.strip()})

    return slots


# ============================================================
# 结果区
# ============================================================
def render_result_area() -> None:
    """全宽结果区（V2-3）。"""
    st.markdown('<div class="sec-title">③ 分析结果</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">分项打分 + 逐项对比，每条建议都引用原文</div>', unsafe_allow_html=True)

    if st.session_state.result_error:
        st.error("分析未完成：" + st.session_state.result_error.split("\n")[0])
        if "\n" in st.session_state.result_error:
            with st.expander("查看详细说明", expanded=True):
                st.markdown(st.session_state.result_error)

    result = st.session_state.result
    if not result:
        if not st.session_state.result_error:
            st.info("上传简历并填写 JD 后，点击上方的「开始分析」即可生成优化建议。")
        return

    if st.session_state.result_source:
        st.caption("结果来源：{}".format(st.session_state.result_source))

    if st.session_state.jd_checklist:
        with st.expander("查看 AI 提取的岗位核心要求清单（第一步）", expanded=False):
            st.markdown(st.session_state.jd_checklist)

    with st.container(border=True):
        st.markdown(format_report(result))

    st.divider()
    st.download_button(
        label="下载为 Markdown 文件",
        data=result.encode("utf-8"),
        file_name="简历优化建议_{}.md".format(st.session_state.analyzed_at or "result"),
        mime="text/markdown",
        **wide_kwargs(st.download_button),
    )
    st.caption("也可以直接在上方结果区域全选复制。")


def render_compare_table() -> None:
    """多岗位对比表（V2-5）。"""
    if st.session_state.compare_error:
        st.error("分析未完成：" + st.session_state.compare_error)

    results = st.session_state.compare_results
    if not results:
        return

    import pandas as pd

    def cell(value):
        return value if value is not None else "-"

    rows = []
    for item in results:
        scores = item.get("scores") or {}
        rows.append(
            {
                "岗位": item["name"],
                "总分": cell(scores.get("total")),
                "技能匹配(40%)": cell(scores.get("skill")),
                "经历匹配(40%)": cell(scores.get("experience")),
                "学历与行业(20%)": cell(scores.get("education")),
                "一句话建议": scores.get("advice") or "-",
            }
        )

    def sort_key(row):
        value = row["总分"]
        return (value == "-", -(value if value != "-" else 0))

    st.markdown('<div class="sec-title">③ 多岗位对比结果</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">按总分从高到低排序，可据此决定先投哪个</div>', unsafe_allow_html=True)
    st.table(pd.DataFrame(sorted(rows, key=sort_key)))
    st.caption("各岗位完整分析：")
    for item in results:
        scores = item.get("scores") or {}
        total = scores.get("total")
        with st.expander("{}　总分：{}".format(item["name"], total if total is not None else "未解析"), expanded=False):
            if item.get("checklist"):
                with st.expander("岗位核心要求清单", expanded=False):
                    st.markdown(item["checklist"])
            if item.get("report"):
                st.markdown(format_report(item["report"]))
            else:
                st.warning(item.get("error", "该岗位未生成结果"))


# ============================================================
# 分析流程
# ============================================================
def _require_api_key(manual_key: str, error_key: str) -> str:
    """校验 API Key，缺失时写入错误提示并返回空串。"""
    api_key, _source = resolve_api_key(manual_key)
    if not api_key:
        st.session_state[error_key] = (
            "未配置 API Key。请通过以下任一方式配置：\n\n"
            "1. 在 `.streamlit/secrets.toml` 中设置 `DEEPSEEK_API_KEY`\n"
            "2. 设置环境变量 `DEEPSEEK_API_KEY`\n"
            "3. 在左侧侧边栏手动输入 API Key"
        )
    return api_key


def run_single(manual_key: str) -> None:
    """单岗位分析：两步走 + 历史记录。"""
    resume_text = st.session_state.resume_text
    jd_text = (st.session_state.get("jd_text") or "").strip()

    if not resume_text:
        st.session_state.result_error = "请先上传并成功解析一份简历（支持 PDF / DOCX / TXT，≤ {} MB）。".format(
            MAX_FILE_SIZE_MB
        )
        return
    if not jd_text:
        st.session_state.result_error = "请先粘贴目标岗位的 JD，或上传 JD 截图完成识别。"
        return

    api_key = _require_api_key(manual_key, "result_error")
    if not api_key:
        return

    with st.spinner("AI 正在分析，请稍候…"):
        outcome = analyze_one(api_key, resume_text, jd_text)

    st.session_state.jd_checklist = outcome.get("checklist", "")

    if not outcome["ok"]:
        st.session_state.result = ""
        st.session_state.result_error = outcome["error"]
        return

    st.session_state.result = outcome["report"]
    st.session_state.result_error = ""
    _, stamp = now_stamp()
    st.session_state.analyzed_at = stamp
    st.session_state.result_source = "本次分析 · {}".format(jd_summary(jd_text, 20))
    add_history("未命名岗位", jd_text, outcome["report"], outcome.get("scores", {}), outcome.get("checklist", ""))


def run_compare(manual_key: str, slots: list) -> None:
    """多岗位对比：逐个两步分析 + 汇总对比表。"""
    resume_text = st.session_state.resume_text
    valid = [slot for slot in slots if slot["jd"]]

    if not resume_text:
        st.session_state.compare_error = "请先上传并成功解析一份简历（支持 PDF / DOCX / TXT，≤ {} MB）。".format(
            MAX_FILE_SIZE_MB
        )
        return
    if len(valid) < 2:
        st.session_state.compare_error = "多岗位对比至少需要 2 个岗位的 JD，请补全后重试。"
        return

    api_key = _require_api_key(manual_key, "compare_error")
    if not api_key:
        return

    st.session_state.compare_results = []
    st.session_state.result = ""
    st.session_state.result_error = ""
    st.session_state.compare_error = ""

    progress = st.progress(0.0, text="准备开始…")
    results = []
    with st.status("正在进行多岗位对比分析…", expanded=True) as status:
        for position, slot in enumerate(valid, start=1):
            progress.progress((position - 1) / len(valid), text="正在分析：{}".format(slot["name"]))
            st.write("🔍 正在分析「{}」…".format(slot["name"]))
            outcome = analyze_one(api_key, resume_text, slot["jd"])
            item = {
                "name": slot["name"],
                "jd": slot["jd"],
                "ok": outcome["ok"],
                "error": outcome.get("error", ""),
                "checklist": outcome.get("checklist", ""),
                "report": outcome.get("report", ""),
                "scores": outcome.get("scores", {}),
            }
            results.append(item)
            if outcome["ok"]:
                total = item["scores"].get("total")
                st.write("✅ 「{}」完成，总分：{}".format(slot["name"], total if total is not None else "未解析"))
                add_history(
                    slot["name"], slot["jd"], item["report"], item["scores"], item["checklist"]
                )
            else:
                st.write("⚠️ 「{}」失败：{}".format(slot["name"], item["error"]))
        progress.progress(1.0, text="全部完成")
        ok_count = sum(1 for item in results if item["ok"])
        status.update(label="分析完成（成功 {} / {} 个岗位）".format(ok_count, len(valid)), state="complete")

    st.session_state.compare_results = results
    if not any(item["ok"] for item in results):
        st.session_state.compare_error = "所有岗位都分析失败，请检查 API Key 或网络后重试。"


# ============================================================
# 主流程
# ============================================================
def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")
    init_state()

    # 主题 CSS 必须在页面渲染前注入（V2-4）
    st.markdown(build_css(st.session_state.get("theme_name", DEFAULT_THEME)), unsafe_allow_html=True)

    render_hero()
    manual_key = render_sidebar()

    mode = st.session_state.get("mode", MODE_SINGLE)

    # 输入区双列：左简历 / 右 JD（V2-2）
    left, right = st.columns([1, 1], gap="large")
    with left:
        with st.container(border=True):
            render_resume_card()
    slots = []
    with right:
        with st.container(border=True):
            if mode == MODE_SINGLE:
                render_single_jd_card()
            else:
                slots = render_compare_jd_card()

    # 居中大按钮（V2-2）
    st.write("")
    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        label = "开始分析" if mode == MODE_SINGLE else "开始对比分析"
        clicked = st.button(label, type="primary", **wide_kwargs(st.button))

    st.write("")
    if mode == MODE_SINGLE:
        if clicked:
            st.session_state.result = ""
            st.session_state.result_error = ""
            st.session_state.result_source = ""
            st.session_state.compare_results = []
            run_single(manual_key)
        render_result_area()
    else:
        if clicked:
            run_compare(manual_key, slots)
        render_compare_table()
        render_result_area()

    # 历史记录放在最后渲染，保证刚完成的这次分析立刻出现在侧边栏（V2-5）
    render_history()


if __name__ == "__main__":
    main()
