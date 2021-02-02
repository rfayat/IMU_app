cd C:\Users\gdugue\Documents\code\IMU_app;
& "C:\Program Files\Mozilla Firefox\firefox.exe" -width 1000 -height 600 http://127.0.0.1:8000/;
uvicorn IMU_app.main:app --reload;
