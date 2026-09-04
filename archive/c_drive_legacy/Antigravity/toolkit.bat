@echo off
setlocal

set TARGET=%1
shift

if "%TARGET%"=="browser" (
    echo [Antigravity Toolkit] Launching Browser E2E Agent...
    python .agents\plugins\antigravity-toolkit\scripts\browser_agent.py %1 %2
    goto :EOF
)

if "%TARGET%"=="audit" (
    echo [Antigravity Toolkit] Launching A11y/CWV Auditor...
    python .agents\plugins\antigravity-toolkit\scripts\a11y_auditor.py %1
    goto :EOF
)

echo.
echo ==============================================
echo   Antigravity Toolkit - Ease of Access CLI
echo ==============================================
echo.
echo Usage:
echo   toolkit browser "<objective>" "<url>"  - Runs the autonomous browser agent
echo   toolkit audit "<url>"                  - Runs the Lighthouse a11y auditor
echo.
echo Example:
echo   toolkit browser "Click the login button" "http://localhost:3000"
echo   toolkit audit "http://localhost:3000"
echo.
