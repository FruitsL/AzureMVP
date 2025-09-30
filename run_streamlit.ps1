# Streamlit 앱 실행 PowerShell 스크립트
$env:PYTHONPATH = "$PSScriptRoot"

# 가상환경이 있으면 활성화
if (Test-Path "$PSScriptRoot\.venv\Scripts\Activate.ps1") {
    & "$PSScriptRoot\.venv\Scripts\Activate.ps1"
}

streamlit run "$PSScriptRoot\app.py"
