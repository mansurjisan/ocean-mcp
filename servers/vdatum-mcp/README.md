# vdatum-mcp

MCP server for vertical datum conversions using [coastalmodeling-vdatum](https://github.com/oceanmodeling/coastalmodeling-vdatum).

Converts elevations between NAVD88, MLLW, MLW, MHW, MHHW, LMSL, xGEOID20b, IGLD85, and LWD.

## Tools

| Tool | Description |
|------|-------------|
| `vdatum_convert` | Convert elevation values between vertical datums |
| `vdatum_list_datums` | List all supported vertical datums |

## Installation

```bash
pip install -e .
```

## Example Queries via CORAL

```
Convert 1.5 meters from NAVD88 to MLLW at The Battery (40.7, -74.0)
What vertical datums are supported?
Convert these water levels from MLLW to NAVD88: lat 30,26,27.5 lon -80,-75,-77.5 z 0.5,1.0,0.3
```
