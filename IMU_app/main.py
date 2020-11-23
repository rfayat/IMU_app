"""
Main code for the application for data acquisition.

Author: Romain Fayat, November 2020
"""
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates/")


@app.get("/")
async def dashboard(request: Request):
    "Return the main dashboard"
    return templates.TemplateResponse("dashboard.html",
                                      context={"request": request})
