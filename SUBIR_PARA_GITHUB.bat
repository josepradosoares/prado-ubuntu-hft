@echo off
title PRADO INSTITUTIONAL HFT - ENVIAR PARA O GITHUB
echo ===================================================================
echo   ENVIANDO PROJETO PRADO-UBUNTU-HFT PARA O SEU GITHUB
echo   Repositorio: https://github.com/josepradosoares/prado-ubuntu-hft.git
echo ===================================================================
cd /d "C:\Projeto\Prado\prado-ubuntu-hft"
git remote remove origin 2>nul
git remote add origin https://github.com/josepradosoares/prado-ubuntu-hft.git
git branch -M main
echo.
echo Iniciando login e envio (se abrir a janela do GitHub no navegador, clique em Authorize)...
git push -u origin main
echo.
echo ===================================================================
echo   PROCESSO FINALIZADO!
echo ===================================================================
pause
