type ScheduledItem = {
  id: string;
  kind: "cron" | "scheduled_task";
  title: string;
  schedule: string;
  nextRun?: string;
};

// TODO: Replace with Convex + OpenClaw cron ingestion.
const mock: ScheduledItem[] = [
  {
    id: "c1",
    kind: "cron",
    title: "(Example) Daily briefing 7:50am ET",
    schedule: "cron: 50 7 * * * America/New_York",
  },
  {
    id: "c2",
    kind: "scheduled_task",
    title: "(Example) Follow up: reply to hoogahealth with a video",
    schedule: "manual",
  },
];

export default function CalendarPage() {
  return (
    <main className="min-h-screen p-8">
      <h1 className="text-2xl font-semibold">Calendar</h1>
      <p className="text-sm text-muted-foreground mt-2 max-w-2xl">
        All assistant scheduled tasks and cron jobs should live here. Anytime you
        ask the assistant to schedule something (assistant-only), it should show
        up in this calendar.
      </p>

      <div className="mt-8 rounded-xl border">
        <div className="grid grid-cols-12 border-b px-4 py-3 text-xs text-muted-foreground">
          <div className="col-span-2">Type</div>
          <div className="col-span-5">Title</div>
          <div className="col-span-5">Schedule</div>
        </div>
        {mock.map((item) => (
          <div
            key={item.id}
            className="grid grid-cols-12 px-4 py-3 border-b last:border-b-0"
          >
            <div className="col-span-2 text-sm">{item.kind}</div>
            <div className="col-span-5 text-sm font-medium">{item.title}</div>
            <div className="col-span-5 text-sm text-muted-foreground">
              {item.schedule}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-10 text-sm text-muted-foreground">
        Next step: automatically ingest OpenClaw cron jobs and display next run
        times.
      </div>
    </main>
  );
}
