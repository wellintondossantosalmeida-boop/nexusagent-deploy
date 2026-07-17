from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from middleware.auth import get_current_user

router = APIRouter()

class NavigateRequest(BaseModel):
    url: str

class SearchRequest(BaseModel):
    query: str

@router.post("/navigate")
async def navigate(req: NavigateRequest, user=Depends(get_current_user)):
    from services.browser_auto import browser
    result = await browser.navigate(req.url)
    return result

@router.post("/extract")
async def extract(req: NavigateRequest, user=Depends(get_current_user)):
    from services.browser_auto import browser
    result = await browser.extract_content(req.url)
    return result

@router.post("/search")
async def search(req: SearchRequest, user=Depends(get_current_user)):
    from services.browser_auto import browser
    result = await browser.search(req.query)
    return result
