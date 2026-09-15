@echo off
REM SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
REM Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
REM Tous droits réservés / All rights reserved.
REM Composant du démonstrateur « moteur-rapprochement ».
REM Reproduction, modification ou redistribution interdites sans autorisation écrite.

setlocal enableextensions
chcp 65001 >nul
cd /d "%~dp0"

REM ============================================================
REM  moteur-rapprochement -- installeur environnement DEV
REM  Double-clic : bootstrap uv -> Python cible -> venv isole
REM               -> lock a hashes -> install exacte -> verif.
REM  Cree .venv et requirements.lock DANS ce dossier.
REM  NB : configure CETTE machine.
REM  Reseau requis a l'installation ; runtime ensuite offline.
REM ============================================================

set "PYVER=3.12"
set "VENV_DIR=.venv"
set "REQ=requirements.txt"
set "LOCK=requirements.lock"
set "PYEXE=%CD%\%VENV_DIR%\Scripts\python.exe"

echo ============================================================
echo   Installation environnement DEV -- moteur-rapprochement
echo   Dossier      : %CD%
echo   Python cible : %PYVER%   Manager : uv   Env isole : %VENV_DIR%
echo ============================================================
echo.

if not exist "%REQ%" (
  echo [ECHEC] %REQ% introuvable dans %CD%.
  echo   Place install.bat et %REQ% dans le meme dossier, puis relance.
  goto end_fail
)

REM --- 0) Installation PROPRE au bon endroit ---------------------------------
REM  .venv est cree DANS %CD% = la racine du repo de build.
REM  Les commandes documentees ^(.venv\Scripts\python ...^) l'attendent ICI.
REM  On purge un %VENV_DIR% local preexistant pour une reinstall propre.
if exist "%VENV_DIR%" (
  echo [0/6] Suppression du %VENV_DIR% preexistant dans %CD% ^(reinstall propre^)...
  rmdir /s /q "%VENV_DIR%"
)
echo.

REM --- 1) Bootstrap uv --------------------------------------------------------
set "UV="
where uv >nul 2>&1 && set "UV=uv"
if not defined UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not defined UV if exist "%USERPROFILE%\.cargo\bin\uv.exe" set "UV=%USERPROFILE%\.cargo\bin\uv.exe"
if defined UV goto uv_ready

echo [1/6] uv introuvable : installation de uv...
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
where uv >nul 2>&1 && set "UV=uv"
if not defined UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not defined UV if exist "%USERPROFILE%\.cargo\bin\uv.exe" set "UV=%USERPROFILE%\.cargo\bin\uv.exe"
if not defined UV goto uv_fail

:uv_ready
echo [1/6] uv : %UV%
"%UV%" --version
if errorlevel 1 goto uv_fail
echo.

REM --- 2) Python cible gere par uv -------------------------------------------
echo [2/6] Python %PYVER% (installe/verifie par uv)...
"%UV%" python install %PYVER%
if errorlevel 1 goto py_fail
echo.

REM --- 3) Environnement virtuel isole ----------------------------------------
echo [3/6] Creation de l'environnement isole %VENV_DIR%...
"%UV%" venv --python %PYVER% "%VENV_DIR%"
if errorlevel 1 goto venv_fail
echo.

REM --- 4) Lock reproductible (versions exactes + hashes) ---------------------
if exist "%LOCK%" (
  echo [4/6] %LOCK% deja present : reutilise tel quel ^(reproductibilite^).
  goto do_sync
)
echo [4/6] Resolution + generation du lock a hashes ^(%LOCK%^)...
"%UV%" pip compile "%REQ%" --generate-hashes --output-file "%LOCK%" --python "%PYEXE%"
if errorlevel 1 goto lock_fail
echo.

:do_sync
REM --- 5) Installation exacte depuis le lock ---------------------------------
echo [5/6] Installation exacte depuis %LOCK% ^(verification des hashes^)...
"%UV%" pip sync "%LOCK%" --python "%PYEXE%"
if errorlevel 1 goto sync_fail
echo.

REM --- 6) Verification des imports cles --------------------------------------
echo [6/6] Verification des imports...
"%PYEXE%" -c "import sys,splink,duckdb,pandas,numpy,sklearn,scipy,networkx,streamlit,pytest;print('  python    '+sys.version.split()[0]);print('  splink    '+splink.__version__);print('  duckdb    '+duckdb.__version__);print('  pandas    '+pandas.__version__);print('  numpy     '+numpy.__version__);print('  sklearn   '+sklearn.__version__);print('  scipy     '+scipy.__version__);print('  networkx  '+networkx.__version__);print('  streamlit '+streamlit.__version__)"
if errorlevel 1 goto verify_fail

echo.
echo ============================================================
echo   OK -- environnement pret.
echo   Activation dans un terminal :
echo       call "%CD%\%VENV_DIR%\Scripts\activate.bat"
echo   Lock reproductible ecrit : %CD%\%LOCK%
echo ============================================================
echo.
pause
exit /b 0

:uv_fail
echo.
echo [ECHEC] Installation de uv impossible.
echo   Cause probable : pas d'acces reseau, ou PowerShell bloque par une politique.
echo   Piste : verifier la connexion internet puis relancer ce .bat.
echo   Manuel : https://docs.astral.sh/uv/getting-started/installation/
goto end_fail

:py_fail
echo.
echo [ECHEC] Installation de Python %PYVER% par uv impossible.
echo   Cause probable : reseau. Verifier la connexion puis relancer.
goto end_fail

:venv_fail
echo.
echo [ECHEC] Creation de l'environnement virtuel impossible.
goto end_fail

:lock_fail
echo.
echo [ECHEC] Resolution des dependances impossible.
echo   Cause frequente : splink==4.0.16 incompatible avec Python %PYVER%.
echo   Remede : rouvrir ce .bat, remplacer  set "PYVER=%PYVER%"  par  set "PYVER=3.11"  puis relancer.
echo   (sinon transmettre l'erreur exacte ci-dessus)
goto end_fail

:sync_fail
echo.
echo [ECHEC] Installation depuis le lock impossible ^(reseau ou hash^).
goto end_fail

:verify_fail
echo.
echo [ECHEC] Un import a echoue apres installation ^(voir l'erreur ci-dessus^).
goto end_fail

:end_fail
echo.
pause
exit /b 1
