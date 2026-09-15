@echo off
REM SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
REM Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
REM Tous droits réservés / All rights reserved.
REM Composant du démonstrateur « moteur-rapprochement ».
REM Reproduction, modification ou redistribution interdites sans autorisation écrite.

REM ============================================================================
REM  lancer_ci.bat  --  Le job d'oracles, joue ICI et MAINTENANT.
REM
REM  Ce depot n'a aucun remote : .github/workflows/oracles.yml ne sera pas
REM  execute tant qu'il n'en aura pas un. Ce fichier joue LES MEMES ETAPES, par
REM  le meme tools/job_ci.py, pour que « job vert » soit un fait constate et non
REM  une promesse posee a cote d'un YAML que rien ne lance.
REM
REM  Usages :
REM    lancer_ci.bat                -> profil complet (tests/ en entier ; exige
REM                                    les packs de fixtures/ et Node)
REM    lancer_ci.bat complet rejeu  -> profil complet sur un CHECKOUT NU de HEAD,
REM                                    extrait hors du depot.
REM ============================================================================

@setlocal
title Job d'oracles -- moteur-rapprochement
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   [ERREUR] .venv introuvable a la racine du depot.
  echo   Lancez install.bat d'abord, puis relancez ce fichier.
  echo.
  pause
  exit /b 1
)

set "PROFIL=%~1"
if "%PROFIL%"=="" set "PROFIL=complet"

set "REJEU="
if /i "%~2"=="rejeu" set "REJEU=--repetition"

echo.
echo   ==================================================================
echo     Job d'oracles -- profil %PROFIL% %REJEU%
echo   ==================================================================
echo.

".venv\Scripts\python.exe" tools\job_ci.py --profil %PROFIL% %REJEU%
set "CODE=%ERRORLEVEL%"

echo.
if "%CODE%"=="0" (
  echo   [VERT] Le job est passe.
) else (
  echo   [ROUGE] Le job a echoue -- code %CODE%. La cause est imprimee ci-dessus.
)
echo.
pause
exit /b %CODE%
