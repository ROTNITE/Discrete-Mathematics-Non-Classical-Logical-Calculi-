# Экспорт отчёта через отдельный экземпляр установленного Microsoft Word.
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$docxPath = Join-Path $taskRoot 'output\LR2_variant3.docx'
$pdfPath = Join-Path $taskRoot 'output\LR2_variant3.pdf'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $report = $word.Documents.Open($docxPath, $false, $true, $false)
    try {
        $report.Repaginate()
        $report.ExportAsFixedFormat($pdfPath, 17)
        Write-Output ('PDF pages: ' + $report.ComputeStatistics(2))
        Write-Output ('PDF: ' + $pdfPath)
    }
    finally { $report.Close(0) }
}
finally { $word.Quit() }
