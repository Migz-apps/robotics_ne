param(
    [Parameter(Mandatory = $true)]
    [string]$Name
)
. "$PSScriptRoot\activate.ps1"
python -m src.follow_track.vision_node --name $Name
