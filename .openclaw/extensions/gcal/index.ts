import { google } from "googleapis";
import { Type } from "@sinclair/typebox";

type ToolResult = { content: Array<{ type: "text"; text: string }> };

type GcalPluginConfig = {
  clientId: string;
  clientSecret: string;
  redirectUri: string;
  refreshToken: string;
  calendarId?: string;
  scopes?: string[];
};

function getPluginConfig(api: any): GcalPluginConfig {
  // Preferred: some OpenClaw builds expose plugin config directly
  const direct = api?.pluginConfig;
  if (direct && typeof direct === "object") return direct as GcalPluginConfig;

  // Fallback: read from the global config tree
  const id = (api?.plugin?.id ?? api?.id ?? "gcal") as string;
  const fromGlobal = api?.config?.plugins?.entries?.[id]?.config;
  if (fromGlobal && typeof fromGlobal === "object") return fromGlobal as GcalPluginConfig;

  // Last resort: try gcal explicitly
  const fromGlobal2 = api?.config?.plugins?.entries?.gcal?.config;
  if (fromGlobal2 && typeof fromGlobal2 === "object") return fromGlobal2 as GcalPluginConfig;

  return {} as any;
}

function assertConfig(cfg: GcalPluginConfig) {
  const missing: string[] = [];
  for (const k of ["clientId", "clientSecret", "redirectUri", "refreshToken"] as const) {
    if (!cfg?.[k]) missing.push(k);
  }
  if (missing.length) {
    throw new Error(
      `gcal plugin is not configured. Missing: ${missing.join(", ")}. Configure under plugins.entries.gcal.config.`,
    );
  }
}

async function getCalendarClient(cfg: GcalPluginConfig) {
  assertConfig(cfg);

  const oauth2 = new google.auth.OAuth2({
    clientId: cfg.clientId,
    clientSecret: cfg.clientSecret,
    redirectUri: cfg.redirectUri,
  });

  oauth2.setCredentials({ refresh_token: cfg.refreshToken });

  // googleapis will auto-refresh access tokens as needed.
  const calendar = google.calendar({ version: "v3", auth: oauth2 });
  return calendar;
}

function ok(data: unknown): ToolResult {
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
}

function pick<T extends object>(obj: T, keys: Array<keyof T>) {
  const out: any = {};
  for (const k of keys) {
    if ((obj as any)[k] !== undefined) out[k] = (obj as any)[k];
  }
  return out as Partial<T>;
}

export const id = "gcal";

export default function register(api: any) {
  api.registerTool(
    {
      name: "gcal",
      description:
        "Google Calendar read/write. Ops: list_calendars, list_events, create_event, update_event, delete_event.",
      parameters: Type.Object({
        op: Type.Union(
          [
            Type.Literal("list_calendars"),
            Type.Literal("list_events"),
            Type.Literal("create_event"),
            Type.Literal("update_event"),
            Type.Literal("delete_event"),
          ],
          { description: "Operation to perform" },
        ),

        // Common
        calendarId: Type.Optional(
          Type.String({ description: "Calendar ID (defaults to plugin config calendarId or 'primary')" }),
        ),

        // list_events
        timeMin: Type.Optional(Type.String({ description: "RFC3339 timeMin filter" })),
        timeMax: Type.Optional(Type.String({ description: "RFC3339 timeMax filter" })),
        q: Type.Optional(Type.String({ description: "Free text search" })),
        maxResults: Type.Optional(Type.Integer({ minimum: 1, maximum: 2500 })),
        singleEvents: Type.Optional(Type.Boolean({ description: "Expand recurring events" })),
        orderBy: Type.Optional(
          Type.Union([Type.Literal("startTime"), Type.Literal("updated")], {
            description: "Sort order",
          }),
        ),

        // create/update
        eventId: Type.Optional(Type.String({ description: "Event ID (required for update/delete)" })),
        summary: Type.Optional(Type.String()),
        description: Type.Optional(Type.String()),
        location: Type.Optional(Type.String()),
        start: Type.Optional(
          Type.Object({
            dateTime: Type.Optional(Type.String({ description: "RFC3339 date-time" })),
            date: Type.Optional(Type.String({ description: "All-day date (YYYY-MM-DD)" })),
            timeZone: Type.Optional(Type.String()),
          }),
        ),
        end: Type.Optional(
          Type.Object({
            dateTime: Type.Optional(Type.String({ description: "RFC3339 date-time" })),
            date: Type.Optional(Type.String({ description: "All-day date (YYYY-MM-DD)" })),
            timeZone: Type.Optional(Type.String()),
          }),
        ),
        attendees: Type.Optional(
          Type.Array(
            Type.Object({
              email: Type.String(),
              displayName: Type.Optional(Type.String()),
              optional: Type.Optional(Type.Boolean()),
            }),
          ),
        ),
        reminders: Type.Optional(
          Type.Object({
            useDefault: Type.Optional(Type.Boolean()),
            overrides: Type.Optional(
              Type.Array(
                Type.Object({
                  method: Type.Union([Type.Literal("email"), Type.Literal("popup")]),
                  minutes: Type.Integer({ minimum: 0 }),
                }),
              ),
            ),
          }),
        ),
      }),

      async execute(_id: string, params: any): Promise<ToolResult> {
        const cfg = getPluginConfig(api);
        const calendar = await getCalendarClient(cfg);
        const calendarId = params.calendarId ?? cfg.calendarId ?? "primary";

        switch (params.op) {
          case "list_calendars": {
            const resp = await calendar.calendarList.list({});
            const items = (resp.data.items ?? []).map((c) =>
              pick(c, ["id", "summary", "timeZone", "accessRole", "primary"] as any),
            );
            return ok({ calendars: items });
          }

          case "list_events": {
            const resp = await calendar.events.list({
              calendarId,
              timeMin: params.timeMin,
              timeMax: params.timeMax,
              q: params.q,
              maxResults: params.maxResults,
              singleEvents: params.singleEvents ?? true,
              orderBy: params.orderBy ?? "startTime",
            });
            const items = (resp.data.items ?? []).map((e) =>
              pick(e, ["id", "status", "htmlLink", "summary", "description", "location", "start", "end", "updated", "created", "attendees"] as any),
            );
            return ok({ calendarId, events: items, nextPageToken: resp.data.nextPageToken });
          }

          case "create_event": {
            if (!params.summary) throw new Error("create_event requires summary");
            if (!params.start) throw new Error("create_event requires start");
            if (!params.end) throw new Error("create_event requires end");

            const resp = await calendar.events.insert({
              calendarId,
              requestBody: {
                summary: params.summary,
                description: params.description,
                location: params.location,
                start: params.start,
                end: params.end,
                attendees: params.attendees,
                reminders: params.reminders,
              },
            });

            return ok({ created: pick(resp.data, ["id", "htmlLink", "summary", "start", "end"] as any) });
          }

          case "update_event": {
            if (!params.eventId) throw new Error("update_event requires eventId");

            const requestBody: any = {
              summary: params.summary,
              description: params.description,
              location: params.location,
              start: params.start,
              end: params.end,
              attendees: params.attendees,
              reminders: params.reminders,
            };
            // Remove undefined so patch is clean
            Object.keys(requestBody).forEach((k) => requestBody[k] === undefined && delete requestBody[k]);

            const resp = await calendar.events.patch({
              calendarId,
              eventId: params.eventId,
              requestBody,
            });

            return ok({ updated: pick(resp.data, ["id", "htmlLink", "summary", "start", "end", "updated"] as any) });
          }

          case "delete_event": {
            if (!params.eventId) throw new Error("delete_event requires eventId");
            await calendar.events.delete({ calendarId, eventId: params.eventId });
            return ok({ deleted: true, calendarId, eventId: params.eventId });
          }

          default:
            throw new Error(`Unknown op: ${params.op}`);
        }
      },
    },
    // Side-effecting tool; require explicit allowlisting
    { optional: true },
  );
}
