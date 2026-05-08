# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**重要：始终使用中文回复用户。所有对话、说明、代码注释等内容均使用中文。**

**工作流程：每次用户要求改动代码时，先分析需求并给出实现方案，待用户确认后再动手改代码，不要直接修改。**

## Repository structure

This working directory contains **one independent Git repository** and one subdirectory within a larger repo:

| Directory | Git | Remote | Deploy |
|---|---|---|---|
| `frontend/` | 独立 `.git` | `qlftng/gaokao-frontend` | Netlify（自动部署） |
| `backend/` | 随父级 `C:\Users\Lenovo` 仓库一起推送 | `qlftng/gaokao-backend` | Render（Root Directory = `gaokao-project/backend`） |

父级仓库根目录在 `C:\Users\Lenovo`，remote 为 `qlftng/gaokao-backend`。`backend/` 下的代码变更需在父级仓库中提交推送。

## Tech stack

- **Frontend**: Vue 3 (SFC, `<script setup>`), Vite, Axios — single-page survey form
- **Backend**: FastAPI + Uvicorn, writes to Supabase via service key. Requires `python-multipart` for file uploads
- **Database**: Supabase — tables `students` (含 `screenshot_url` 列), `assessments`, `study_plans`, `push_logs`, `templates` with RLS enabled
- **Storage**: Supabase Storage — bucket `screenshots`（非公开，通过 service key 访问）
- **Push system**: Flask + pywinauto + pyautogui + pyperclip, local SQLite for logs and precheck state

## Important: two copies of main.py

`gaokao-project/backend/main.py` — **生产后端**，Render 部署的就是这个（Root Directory 设为 `gaokao-project/backend`），从环境变量读取 `ALLOWED_ORIGINS`。

`gaokao-project/main.py`（仓库根目录）— **仅开发调试用**，硬编码 `allow_origins=["*"]`，不部署。

**更新 `backend/main.py` 后要确认 Render 重新部署成功。** 如果改动涉及新依赖（如 `python-multipart`），需同步更新 `backend/requirements.txt`。

## Requirements

- `backend/requirements.txt` — fastapi, uvicorn, supabase, python-dotenv, **python-multipart**
- `requirements.txt`（根目录）— 全量依赖，含 flask, pyautogui, pywinauto, pyperclip, pillow, requests 供 `control_panel.py` 使用

## Development commands

**Frontend** (`cd frontend`):
```bash
npm install            # install dependencies
npm run dev            # start Vite dev server (hot reload, port 5173)
npm run build          # production build to dist/
npm run preview        # preview production build locally
```

**Backend** (`cd backend`):
```bash
pip install -r requirements.txt   # install deps (includes python-multipart)
uvicorn main:app --reload         # start dev server on localhost:8000
```

**Push control panel** (run from repo root, requires Python 3.12):
```bash
pip install -r requirements.txt   # install full deps
py -3.12 control_panel.py         # launch web control panel (port 5000), auto-opens browser
py -3.12 import_plans.py          # import study plans from MD files into Supabase
py -3.12 verify_plans.py          # check study_plans completeness (9×4×21 = 756)
py -3.12 verify_content.py        # compare MD source with DB for mismatches
py -3.12 keep_alive.py            # ping Render backend every 14min to prevent free-tier sleep
```

## Architecture

### Survey flow

1. User fills survey: name, wx_name（带 `?` 引导提示）, phone（11 位手机号校验）, province（31 省下拉菜单，不含港澳台）, school type, 6 subject levels, problems, channels, invest, budget
2. 可选上传微信主页截图（Q1 和 Q2 之间的截图卡片），前端本地预览，非必填
3. Frontend 提交时：先 POST 截图到 `/api/upload-screenshot` → 拿到 URL → 再 POST `/api/submit`
4. Backend `/api/submit` 校验 name + province + phone + 六选三（恰好3门），reverses ABCD levels via `LEVEL_MAP` (A→D, B→C, C→B, D→A)
5. 查重用 **name + phone**（非 wx_name），已存在且无 `force` 返回 409
6. Frontend 收到 409 显示覆盖按钮，用户点击后 `force: true` 重新提交，更新 students 并替换旧 assessments
7. 成功 → AI 动画页（3 步，3.5s）→ 成功页（长按二维码 + "重新填写"）

### Screenshot upload (`/api/upload-screenshot`)

- 前端选择图片 → 预览缩略图 → 提交时先上传到 Supabase Storage
- 后端校验：仅 JPG/PNG/WebP，最大 5MB
- 文件命名：`{uuid}.jpg`，存入 Supabase Storage bucket `screenshots`
- `screenshot_url` 写入 students 表，force 更新时也会更新

### Subject selection constraints (frontend `selectElective`)

选考科目（Q7-Q12）采用**六选三**约束：

- 物理、化学、生物、政治、历史、地理中恰好选择 3 门
- 超过 3 门时弹出 toast 提示，不做静默清空

后端 `/api/submit` 也做同样校验（`elective_count != 3 → 400`）。

实现采用"下一状态"模式：先构建 `next = { ...form.value, [key]: value }`，在纯对象上跑规则，通过后一次性 `form.value = next`。

### Key design decisions

- **Level reversal** (`backend/main.py`): The survey uses A=worst/D=best for user-facing options, but stores inverted values so D=top in the database.
- **Elective subjects default to `"E"`**: Fields `physics` through `geography` default to `"E"` ("not selected"). Any value other than `"E"` is treated as an active elective.
- **Multi-select fields** (`problems`, `channels`, `invest`): Frontend stores arrays, joined to comma-separated strings before POST.
- **查重键 name + phone**: 后端用 `name + phone` 查重（非 wx_name），phone 保证唯一性。
- **覆盖更新（force）**: 已存在且无 `force` → 409。`force: true` → 更新 students 所有字段（含 wx_name, screenshot_url），删除旧 assessments 后重新写入。
- **选科组合缩写**: Backend computes `subjects` field (e.g., "物化生") and stores it in `students` table.
- **防重复提交**: 提交按钮 `loading` 状态锁定，防止重复点击。

### File map

- `backend/main.py` — FastAPI app, CORS, Supabase client, `/api/submit`, `/api/upload-screenshot`, root health check
- `frontend/src/App.vue` — single SFC: template, script (selectElective, submitForm, upload), styles
- `frontend/src/main.js` — Vue app entry point
- `frontend/style.css` — global base styles
- `control_panel.py` — **唯一推送控制台**：Flask + React 内嵌 UI，整合检索、发送、报告、重复检测全部功能
- `import_plans.py` — 从科目 MD 文件解析学习计划批量写入 Supabase `study_plans`
- `verify_plans.py` — 校验 study_plans 完整性（9科×4档×21天 = 756条）
- `verify_content.py` — 对比 MD 原文与数据库内容，揪出错位/截断/跨档重复
- `keep_alive.py` — 每 14 分钟 ping Render 后端防止休眠

### WeChat Work push system (control_panel.py)

`control_panel.py` 是推送系统的唯一入口，整合了所有功能（替代了旧的 push_all / wxwork_sender / precheck_wxwork / scan_wxwork）。

**数据库：**
- `push_log.db` — 推送日志（push_log + warmup_log），可随意清除
- `precheck.db` — 联系人检索状态（precheck_state），勿删

**完整操作流程：**

```
1. 重复检测 → 检查 wx_name 是否有重复，程序生成唯一备注名建议，人工确认后自动写入 Supabase
2. 检索未检 → 企微搜索新增学生的备注名 → 结果写入 precheck.db
3. 查看报告 → 搜不到的人标红，操作人员去 Supabase 修正 wx_name 后重检
4. 开始发送 → do_send 自动查 precheck.db，只发送 found=1 的人
   → 未检 / 搜不到的自动跳过，控制台打印跳过名单
```

**重复微信名处理：**
- `/api/duplicates/detect` — 查询所有学生，按 wx_name 分组，找出重复
- 自动生成唯一备注名：`姓名 + 手机号后4位`（无分隔符，避用下划线等 OCR 易错字符）
- 冲突解决：后4位不够就用后6位
- 人工确认后通过 `/api/duplicates/fix` 批量写入 Supabase

**联系人检索（has_contact_result）：**
- 搜索下拉区域截图 → 统计白色像素占比（R>200, G>200, B>200）
- 白色像素 > 60% → 判为搜到联系人
- 搜索异常也视为搜不到

**发送验证机制：**

每条消息 Enter 后，用标记值验证法确认消息是否真正发出：
```python
pyperclip.copy("___SENT___")    # 设标记
Ctrl+A → Ctrl+C                  # 全选输入框
if pyperclip.paste() != "___SENT___":  # 标记被覆盖 = 输入框有文字
    return False
```
空输入框 Ctrl+A 选不到东西，Ctrl+C 不覆盖剪贴板，标记值不变 → 发送成功。

**Supabase 重试：** 所有查询通过 `supa_query(lambda: ..., retries=3)` 包装，间歇性 SSL 断连自动重试 3 次，间隔 2 秒。

**SQLite 损坏自愈：** `get_conn()` 和 `get_precheck_conn()` 在打开数据库前先检测文件完整性，损坏则自动删除重建。

**Push day mechanics:**
- 每个学生 `push_count`（0–20），每天 +1。第 21 天后排除。
- `last_push_date` 防同天重复发送。
- 发送间隔 3–5s 随机延迟，每 10 人插入 20–40s 长停顿防风控。
- 每日需要"预热确认"（手动操作企微 ~10 分钟）后才可发送。
- 发送失败立即停止，操作人员修复后续发。

**Hardware assumptions:** 企微全屏 1920×1080，所有坐标硬编码至此分辨率。

## Environment variables

No production URLs or secrets are hardcoded — both frontend and backend read from environment variables with localhost defaults.

### Backend (`backend/main.py`)

| Variable | Where | Purpose |
|---|---|---|
| `ALLOWED_ORIGINS` | Render env vars | CORS origin (frontend URL) |
| `SUPABASE_URL` | `.env` / Render env vars | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | `.env` / Render env vars | Supabase service role key (bypasses RLS) |

### Frontend (`frontend/src/App.vue`)

| Variable | Where | Purpose |
|---|---|---|
| `API_URL` | 代码中硬编码 | Backend API URL (`https://gaokao-backend.onrender.com`) |

**注意**：当前 API_URL 在 `App.vue:289` 硬编码。如改为 `import.meta.env.VITE_API_URL`，Netlify 需要重新 build 才能注入新值。

## CORS / deploy notes

生产 CORS 在 Render 的 `ALLOWED_ORIGINS` 环境变量控制，值需匹配 Netlify 前端域名。

**Render 部署配置：**
- **Root Directory**: `gaokao-project/backend`（关键！否则 Render 会部署根目录的旧版 main.py）
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

Render 免费计划 15 分钟无请求休眠，`keep_alive.py` 每 14 分钟 ping 一次防止冷启动。

Supabase 免费版有间歇性 SSL 断连（`Server disconnected`），代码中 `supa_query` 已处理重试，不影响功能。

Supabase Storage 免费计划 1GB，1000 张截图约 250MB。

Netlify 连接 GitHub 后每次 push 自动部署。

The `.env` file (backend) is gitignored and contains local Supabase credentials only. Render gets these via its own environment variables.
