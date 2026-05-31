# app/routers/convert.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.utils.markdown import md_to_html

router = APIRouter(prefix="/convert", tags=["格式转换"])

class MarkdownBody(BaseModel):
    content: str

class ConvertResult(BaseModel):
    html: str

@router.post("/md-to-html", response_model=ConvertResult, summary="Markdown 文本转 HTML")
async def convert_md_text(body: MarkdownBody):
    """直接传入 Markdown 字符串，返回转换后的 HTML"""
    html = md_to_html(body.content)
    return ConvertResult(html=html)

@router.post("/md-file-to-html", response_model=ConvertResult, summary="上传 .md 文件转 HTML")
async def convert_md_file(file: UploadFile = File(...)):
    """上传 .md 文件，返回转换后的 HTML"""
    if not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="只支持 .md 文件")
    content = await file.read()
    try:
        md_text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码必须为 UTF-8")
    html = md_to_html(md_text)
    return ConvertResult(html=html)
