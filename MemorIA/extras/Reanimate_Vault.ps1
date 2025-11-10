Set-Location "G:\GHU Codexsphere\obsidian\MERGED_VAULT\Conversaciones"
Get-ChildItem -Recurse -Filter *.bak | ForEach-Object {
    $newName = $_.FullName -replace '\.bak$',''
    Move-Item -Force $_.FullName $newName
}
