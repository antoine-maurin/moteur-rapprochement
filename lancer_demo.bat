@echo off
REM SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
REM Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
REM Tous droits réservés / All rights reserved.
REM Composant du démonstrateur « moteur-rapprochement ».
REM Reproduction, modification ou redistribution interdites sans autorisation écrite.

REM ============================================================================
REM  lancer_demo.bat  --  Demo Concordance (moteur de rapprochement de fiches)
REM  A placer a la RACINE du depot moteur-rapprochement (a cote du dossier .venv).
REM  Lance les 3 surfaces en local, 100%% hors ligne, sur http://localhost:7860
REM ============================================================================

title Demo Concordance -- rapprochement de fiches
cd /d "%~dp0"

REM --- Determinisme identique au deploiement ---
set PYTHONHASHSEED=0

REM --- Verifier le venv ---
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   [ERREUR] .venv introuvable a la racine du depot.
  echo   Placez ce fichier a la racine du projet moteur-rapprochement,
  echo   a cote du dossier .venv, puis relancez-le.
  echo.
  pause
  exit /b 1
)

REM --- Verifier le lanceur (les surfaces vivent sur la branche build/UI) ---
if not exist "serveur.py" (
  echo.
  echo   [ERREUR] serveur.py introuvable.
  echo   Les surfaces de demo sont sur la branche build/UI. Depuis le depot :
  echo.
  echo       git checkout build/UI
  echo.
  echo   puis relancez ce fichier.
  echo.
  pause
  exit /b 1
)

echo.
echo   ==================================================================
echo     Demo Concordance -- moteur de rapprochement de fiches
echo     100%% hors ligne, sur votre machine. Aucune donnee ne sort.
echo   ==================================================================
echo.
echo     Adresse  : http://localhost:7860
echo     Vitrine  : /            Salle des machines : /salle-des-machines
echo     Bac a sable : /bac-a-sable
echo.
echo     Le navigateur va s'ouvrir dans quelques secondes.
echo     Fermez cette fenetre (ou Ctrl+C) pour arreter la demo.
echo.

REM --- Ouvrir le navigateur apres 2s, sans bloquer le demarrage du serveur ---
start "" /b powershell -NoProfile -Command "Start-Sleep -Seconds 2; Start-Process 'http://localhost:7860'" >nul 2>&1

REM --- Lancer le serveur (bloque cette fenetre tant que la demo tourne) ---
".venv\Scripts\python.exe" serveur.py

echo.
echo   Serveur arrete.
pause
