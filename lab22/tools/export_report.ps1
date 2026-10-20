# Экспорт готового DOCX в PDF установленным Microsoft Word.
# Не требуется для запуска верификатора или тестов.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$docxPath = Join-Path $projectRoot 'output\LR1_variant3.docx'
$pdfPath = Join-Path $projectRoot 'output\LR1_variant3.pdf'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $report = $word.Documents.Open($docxPath, $false, $true)
    try {
        $report.Repaginate()
        $report.ExportAsFixedFormat($pdfPath, 17)
        Write-Output "PDF: $pdfPath"
        Write-Output "Pages: $($report.ComputeStatistics(2))"
    }
    finally {
        $report.Close(0)
    }
}
finally {
    $word.Quit()
}
