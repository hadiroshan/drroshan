# Generates circular favicons from profile.png using System.Drawing.
# Run from project root: powershell -NoProfile -ExecutionPolicy Bypass -File .freebuff/make-favicons.ps1
Add-Type -AssemblyName System.Drawing

$src = [System.Drawing.Image]::FromFile("$PSScriptRoot\..\profile.png")
$side = [Math]::Min($src.Width, $src.Height)

# High-quality scaler defaults
$outConfigs = @(
    @{ Name = 'favicon-16x16.png';    Size = 16  },
    @{ Name = 'favicon-32x32.png';    Size = 32  },
    @{ Name = 'favicon-64x64.png';    Size = 64  },
    @{ Name = 'apple-touch-icon.png'; Size = 180 }
)

foreach ($cfg in $outConfigs) {
    $size = $cfg.Size
    # Render at 4x then downscale for smooth edge anti-aliasing on small sizes
    $ss = $size * 4

    # 1) Center-crop the source to a square at 4x resolution
    $square = New-Object System.Drawing.Bitmap($ss, $ss)
    $g = [System.Drawing.Graphics]::FromImage($square)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $srcRect = New-Object System.Drawing.Rectangle(([int](($src.Width - $side) / 2)), ([int](($src.Height - $side) / 2)), $side, $side)
    $g.DrawImage($src, (New-Object System.Drawing.Rectangle(0, 0, $ss, $ss)), $srcRect, [System.Drawing.GraphicsUnit]::Pixel)
    $g.Dispose()

    # 2) Apply circular alpha mask (anti-aliased via texture brush on AA ellipse path)
    $canvas = New-Object System.Drawing.Bitmap($ss, $ss)
    $g2 = [System.Drawing.Graphics]::FromImage($canvas)
    $g2.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g2.Clear([System.Drawing.Color]::Transparent)
    $brush = New-Object System.Drawing.TextureBrush($square)
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $path.AddEllipse(0, 0, $ss, $ss)
    $g2.FillPath($brush, $path)
    $g2.Dispose()
    $square.Dispose()

    # 3) Downscale to final size
    $final = New-Object System.Drawing.Bitmap($size, $size)
    $g3 = [System.Drawing.Graphics]::FromImage($final)
    $g3.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g3.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g3.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g3.DrawImage($canvas, (New-Object System.Drawing.Rectangle(0, 0, $size, $size)))
    $g3.Dispose()

    $outPath = Join-Path $PSScriptRoot ("..\" + $cfg.Name)
    $final.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Output ("wrote " + $cfg.Name + " " + $size + "x" + $size)

    $final.Dispose(); $canvas.Dispose()
}

$src.Dispose()
Write-Output 'done'
