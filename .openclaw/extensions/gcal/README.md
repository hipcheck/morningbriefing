# gcal OpenClaw plugin

Local plugin that registers an **optional** agent tool named `gcal` for Google Calendar.

## Tool: `gcal`

Operations:
- `list_calendars`
- `list_events`
- `create_event`
- `update_event`
- `delete_event`

### Example calls (shape)

List calendars:
```json
{ "op": "list_calendars" }
```

List events (next week):
```json
{
  "op": "list_events",
  "calendarId": "primary",
  "timeMin": "2026-02-13T00:00:00Z",
  "timeMax": "2026-02-20T00:00:00Z",
  "maxResults": 50
}
```

Create an event:
```json
{
  "op": "create_event",
  "summary": "Dentist",
  "start": { "dateTime": "2026-02-14T09:00:00-05:00" },
  "end": { "dateTime": "2026-02-14T09:30:00-05:00" }
}
```

Update an event:
```json
{
  "op": "update_event",
  "eventId": "abc123def456",
  "location": "123 Main St"
}
```

Delete an event:
```json
{ "op": "delete_event", "eventId": "abc123def456" }
```

## Setup

See [SETUP.md](./SETUP.md).
