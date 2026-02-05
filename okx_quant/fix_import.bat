@echo off
chcp 65001 >nul
echo ========================================
echo 清理 Python 缓存并修复导入问题
echo ========================================
echo.

echo 正在清理缓存...
for /d /r %%d in (__pycache__) do @if exist "%%d" (
    echo   删除: %%d
    rd /s /q "%%d"
)

for /r %%f in (*.pyc) do @if exist "%%f" (
    echo   删除: %%f
    del /q "%%f"
)

echo.
echo 缓存清理完成！
echo.

echo 测试模块导入...
python fix_import.py

if errorlevel 1 (
    echo.
    echo ❌ 测试失败，请检查上面的错误信息
    pause
    exit /b 1
) else (
    echo.
    echo ✅ 修复成功！
    echo.
    echo 现在可以运行: python main.py
    pause
)
