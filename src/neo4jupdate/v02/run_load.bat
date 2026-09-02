@echo off
REM Neo4j Data Loader Script
REM Cau hinh cac tham so ket noi Neo4j truoc khi chay

setlocal

REM Cau hinh Neo4j connection
set NEO4J_URI=bolt://localhost:7687
set NEO4J_USERNAME=neo4j
set NEO4J_PASSWORD=your_password_here
set NEO4J_DATABASE=neo4j

REM Duong dan den thu muc chua du lieu CSV
set DATA_DIR=..\..\data\synthetic\v2\raw

REM Chay script Python
python load_data.py ^
    --uri %NEO4J_URI% ^
    --username %NEO4J_USERNAME% ^
    --password %NEO4J_PASSWORD% ^
    --database %NEO4J_DATABASE% ^
    --data-dir %DATA_DIR%

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Data loading failed!
    pause
    exit /b %errorlevel%
)

echo.
echo [SUCCESS] Data loaded successfully!
pause
