@echo off
chcp 65001 > nul
cd /d C:\Users\after\devicebrief\pipeline

rem .env から環境変数を読み込む
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    if not "%%a"=="" if not "%%b"=="" set %%a=%%b
)

echo [%date% %time%] パイプライン開始 >> pipeline_run.log
python collect.py                  >> pipeline_run.log 2>&1
python generate.py --max 30        >> pipeline_run.log 2>&1
python audit_loop.py               >> pipeline_run.log 2>&1
echo [%date% %time%] パイプライン完了 >> pipeline_run.log
