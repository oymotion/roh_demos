@echo off
setlocal

:: ================= 配置区域 =================
cd /d "%~dp0"

:: 1. 你的主 Python 脚本文件名 (例如 main.py)
set MAIN_SCRIPT=.\\glove_ctrled_rohand\\glove_ctrled_hand.py

:: 2. 生成的 exe 文件名 (不带后缀，留空则默认与脚本同名)
set EXE_NAME=GloveCtrlHand

:: 3. 是否带有控制台窗口? (如果你是 GUI 程序选 True，命令行工具选 False)
:: True = 无黑框 (适合 PyQT, TKinter 等界面程序)
:: False = 有黑框 (适合命令行脚本, print 输出可见)
set NO_CONSOLE=False

:: 4. 是否打包成单文件? (True=生成一个单独的exe, False=生成文件夹)
set ONE_FILE=True

:: 5. 图标文件路径 (例如 icon.ico，如果没有留空即可)
set ICON_PATH=C:\\workspace\\OYMotionGit\\logo\\logo.ico

:: ===========================================

echo [INFO] 开始打包 %MAIN_SCRIPT% ...

set SEARCH_PATH=.

:: 构建基础命令
set CMD_STR=pyinstaller "%MAIN_SCRIPT%" --name "%EXE_NAME%" --clean --onefile --console --paths "%SEARCH_PATH%" --hidden-import common --workpath ./temp --distpath ./dist --specpath ./temp

:: 处理 EXE 名称
if not "%EXE_NAME%"=="" (
    set CMD_STR=%CMD_STR% --name "%EXE_NAME%"
)

:: 处理控制台窗口
if /i "%NO_CONSOLE%"=="True" (
    set CMD_STR=%CMD_STR% --noconsole
) else (
    set CMD_STR=%CMD_STR% --console
)

:: 处理单文件模式
if /i "%ONE_FILE%"=="True" (
    set CMD_STR=%CMD_STR% --onefile
) else (
    set CMD_STR=%CMD_STR% --onedir
)

:: 处理图标
if not "%ICON_PATH%"=="" (
    if exist "%ICON_PATH%" (
        set CMD_STR=%CMD_STR% --icon "%ICON_PATH%"
    ) else (
        echo [WARN] 图标文件未找到，将使用默认图标...
    )
)

:: 执行命令
echo [INFO] 执行命令: %CMD_STR%
echo.
%CMD_STR%

:: 检查结果
if %errorlevel% equ 0 (
    echo.
    echo ==========================================
    echo [SUCCESS] 打包成功!
    echo 文件位置: %~dp0dist\%EXE_NAME%.exe
    echo ==========================================
    
    :: 可选：打包完成后清理临时文件 (temp 文件夹)
    :: rmdir /s /q temp
    
    pause
) else (
    echo.
    echo [ERROR] 打包失败，请检查上方错误信息。
    pause
)

endlocal