from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sb = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

# 选项反转映射（用户选A=最差，存库时反转为D级）
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

@app.post("/api/submit")
async def submit(data: SubmitRequest):
    # 基础验证
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="姓名不能为空")
    if not data.province.strip():
        raise HTTPException(status_code=400, detail="省份不能为空")

    # 计算选科组合
    selected_subjects = []
    for key, label in SUBJECT_MAP.items():
        val = getattr(data, key)
        if val and val != "E":
            selected_subjects.append(label)

    subjects_str = "、".join(selected_subjects)

    # 写入 students 表
    student_res = sb.table("students").insert({
        "name":        data.name.strip(),
        "wx_name":     data.wx_name.strip() or data.name.strip(),
        "subjects":    subjects_str,
    }).execute()

    student_id = student_res.data[0]["id"]

    # 写入 assessments 表（各科级别，反转后存入）
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
    return {"status": "ok"}