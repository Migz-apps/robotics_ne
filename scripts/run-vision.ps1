param([Parameter(Mandatory=$true)][string]$Name, [int]$CameraIndex = -1)
. "$PSScriptRoot\activate.ps1"
$args = @("--name", $Name)
if ($CameraIndex -ge 0) { $args += "--camera-index", $CameraIndex }
python -m src.vision_node @args
