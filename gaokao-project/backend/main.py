from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client
from dotenv import load_dotenv
import os
import re

load_dotenv()

app = FastAPI()

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGINS],
    allow_methods=["*"],
    allow_headers=["*"],
)

sb = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

LEVEL_MAP = {"A": "D", "B": "C", "C": "B", "D": "A"}
SUBJECT_MAP = {
    "chinese":   "语文",
    "math":      "数学",
    "english":   "英语",
    "physics":   "物理",
    "chemistry": "化学",
    "biology":   "生物",
    "politics":  "政治",
    "history":   "历史",
    "geography": "地理",
}


class SubmitRequest(BaseModel):
    name: str
    wx_name: str = ""
    phone: str = ""
    province: str = ""
    school_type: str = ""
    chinese: str = ""
    math: str = ""
    english: str = ""
    physics: str = "E"
    chemistry: str = "E"
    biology: str = "E"
    politics: str = "E"
    history: str = "E"
    geography: str = "E"
    problems: str = ""
    channels: str = ""
    invest: str = ""
    budget: str = ""
    force: bool = False  # True = 覆盖更新已有数据


@app.post("/api/submit")
async def submit(data: SubmitRequest):
    # 基础验证
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="姓名不能为空")
    if not data.province.strip():
        raise HTTPException(status_code=400, detail="省份不能为空")
    if not data.phone.strip():
        raise HTTPException(status_code=400, detail="手机号不能为空")
    phone = data.phone.strip()
    if not re.match(r"^1[3-9]\d{9}$", phone):
        raise HTTPException(status_code=400, detail="请填写正确的11位手机号")

    # 六选三校验：物理/化学/生物/政治/历史/地理中恰好选 3 门
    elective_fields = [data.physics, data.chemistry, data.biology,
                       data.politics, data.history, data.geography]
    elective_count = sum(1 for v in elective_fields if v and v != "E")
    if elective_count != 3:
        raise HTTPException(status_code=400, detail="请选择恰好 3 门选考科目")

    name    = data.name.strip()
    wx_name = data.wx_name.strip() or name
    phone   = data.phone.strip()

    # 计算选科组合（只存单字）
    elective_char = {
        "physics": "物", "chemistry": "化", "biology": "生",
        "politics": "政", "history": "历", "geography": "地",
    }
    subjects_str = "".join(
        char for key, char in elective_char.items()
        if getattr(data, key) not in ("", "E")
    )

    # 检查是否已存在
    try:
        existing = sb.table("students").select("id").eq("name", name).eq("phone", phone).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查重查询失败: {str(e)}")

    if existing.data:
        student_id = existing.data[0]["id"]

        if not data.force:
            # 已存在但没有 force，返回 409 让前端提示用户
            raise HTTPException(status_code=409, detail="ALREADY_EXISTS")

        # force=True：覆盖更新 students 表
        sb.table("students").update({
            "subjects":       subjects_str,
            "wx_name":        wx_name,
            "phone":          phone,
            "push_count":     0,
            "last_push_date": None,
        }).eq("id", student_id).execute()

        # 删除旧的 assessments，重新写入
        sb.table("assessments").delete().eq("student_id", student_id).execute()

    else:
        # 全新写入
        student_res = sb.table("students").insert({
            "name":    name,
            "wx_name": wx_name,
            "phone":   phone,
            "subjects": subjects_str,
        }).execute()
        student_id = student_res.data[0]["id"]

    # 写入 assessments
    assessments = []
    for key, label in SUBJECT_MAP.items():
        val = getattr(data, key)
        if val and val != "E":
            assessments.append({
                "student_id": student_id,
                "subject":    label,
                "level":      LEVEL_MAP.get(val, val),
            })
    if assessments:
        sb.table("assessments").insert(assessments).execute()

    return {"success": True, "student_id": student_id}


@app.get("/")
def root():
    return {"status": "ok", "ALLOWED_ORIGINS": ALLOWED_ORIGINS}