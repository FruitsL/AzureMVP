# Streamlit 앱 실행 PowerShell 스크립트
$env:PYTHONPATH = "$PSScriptRoot"
streamlit run "$PSScriptRoot\streamlit\main.py"
