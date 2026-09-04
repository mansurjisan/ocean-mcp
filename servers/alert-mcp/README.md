# alert-mcp

<!-- mcp-name: io.github.oceanmodeling/alert-mcp -->

MCP server for CORAL threshold alerting. Monitors NOAA CO-OPS stations and triggers alerts when observed values cross user-defined thresholds.

## Tools

| Tool | Description |
|------|-------------|
| `coral_create_alert` | Create a threshold alert for a CO-OPS station |
| `coral_list_alerts` | List all active and paused alerts |
| `coral_check_alerts` | Manually trigger a check cycle on all active alerts |
| `coral_pause_alert` | Pause an alert |
| `coral_resume_alert` | Resume a paused alert |
| `coral_delete_alert` | Delete an alert |
| `coral_get_alert_history` | Show trigger history for an alert |

## Usage

```bash
# Install
pip install -e .

# Run
alert-mcp
# or
python -m alert_mcp
```

## Development

```bash
pip install -e ".[dev]"
pytest
```
