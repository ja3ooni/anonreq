"""Post-restoration token verification package.

Provides ``ResponseScanner`` for detecting residual ``[TYPE_N]`` tokens in
response text, and ``ScanStage`` / ``StreamScanStage`` pipeline stages that
execute warn-only scans after restoration (AG-17, D-143).
"""
