Add-Type -AssemblyName System.Drawing

$root = 'C:\Users\14166\Desktop\MC_32\robotcup\xunbao'
$nodeSource = Get-ChildItem -LiteralPath $root -Recurse -Filter '*.jpg' | Where-Object { $_.Length -eq 243608 } | Select-Object -First 1
$ruleSource = Get-ChildItem -LiteralPath $root -Recurse -Filter '*.png' | Where-Object { $_.Length -eq 556950 } | Select-Object -First 1
if ($null -eq $nodeSource -or $null -eq $ruleSource) { throw 'Map source images were not found.' }
$red = [System.Drawing.Brushes]::Red
$white = [System.Drawing.Brushes]::White
$caption = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(215,226,181))

function Save-NodeMap {
    $dst = Join-Path $nodeSource.DirectoryName 'map_nodes_P6_P8_swapped.jpg'
    $image = [System.Drawing.Bitmap]([System.Drawing.Image]::FromFile($nodeSource.FullName))
    $g = [System.Drawing.Graphics]::FromImage($image)
    $g.FillRectangle($white, 320, 430, 82, 84)
    $g.FillRectangle($white, 120, 820, 83, 86)
    $f = [System.Drawing.Font]::new('Microsoft YaHei', 48, [System.Drawing.FontStyle]::Regular)
    $g.DrawString('P8', $f, $red, 332, 438)
    $g.DrawString('P6', $f, $red, 132, 828)
    $image.Save($dst, [System.Drawing.Imaging.ImageFormat]::Jpeg)
    $f.Dispose(); $g.Dispose(); $image.Dispose()
}

function Save-RuleMap {
    $dst = Join-Path $ruleSource.DirectoryName 'map_rules_P6_P8_swapped.png'
    $image = [System.Drawing.Bitmap]([System.Drawing.Image]::FromFile($ruleSource.FullName))
    $g = [System.Drawing.Graphics]::FromImage($image)
    $g.FillRectangle($caption, 421, 383, 79, 65)
    $g.FillRectangle($caption, 232, 677, 83, 61)
    $f = [System.Drawing.Font]::new('Microsoft YaHei', 28, [System.Drawing.FontStyle]::Regular)
    $g.DrawString('P8', $f, $red, 448, 397)
    $g.DrawString('P6', $f, $red, 260, 690)
    $image.Save($dst, [System.Drawing.Imaging.ImageFormat]::Png)
    $f.Dispose(); $g.Dispose(); $caption.Dispose(); $image.Dispose()
}

Save-NodeMap
Save-RuleMap
Write-Output 'created'
