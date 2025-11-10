::reset_vault.bat "G:\obsidian\RAW_VAULT"

::Borra y recrea la carpeta Conversaciones/.
::Borra _index.md, la carpeta _tags/ y _import_manifest.json.
::Deja limpio el vault, pero sin tocar Dashboard.md, Guia.md, etc.

@echo off
:: Resetear Conversaciones/ y archivos auxiliares en un Vault

if "%~1"=="" (
  echo Uso: reset_vault.bat RUTA_AL_VAULT
  echo Ejemplo: reset_vault.bat "G:\obsidian\RAW_VAULT"
  exit /b 1
)

set VAULT=%~1

echo OJO  Esto va a BORRAR las notas en "%VAULT%\Conversaciones"
echo.
pause

echo Borrando contenido de Conversaciones...
rmdir /S /Q "%VAULT%\Conversaciones"
mkdir "%VAULT%\Conversaciones"

echo Eliminando índices antiguos...
del "%VAULT%\_index.md" 2>nul
rmdir /S /Q "%VAULT%\_tags" 2>nul

echo Eliminando manifiestos antiguos...
del "%VAULT%\_import_manifest.json" 2>nul

echo HECHO Vault reseteado en: %VAULT%
pause