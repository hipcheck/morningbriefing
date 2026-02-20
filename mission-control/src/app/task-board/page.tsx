type TaskStatus = "todo" | "in_progress" | "blocked" | "done";

type Task = {
  id: string;
  title: string;
  status: TaskStatus;
  updatedAt: string;
  notes?: string;
};

// TODO: Replace with Convex query.
const mock: Task[] = [
  {
    id: "t1",
    title: "Set up Convex (interactive configure)",
    status: "blocked",
    updatedAt: new Date().toISOString(),
    notes: "Needs `npx convex dev --once --configure=new` run locally.",
  },
  {
    id: "t2",
    title: "Add Clerk keys + restrict signups/allowlist",
    status: "todo",
    updatedAt: new Date().toISOString(),
  },
];

const statusLabel: Record<TaskStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  blocked: "Blocked",
  done: "Done",
};

export default function TaskBoardPage() {
  return (
    <main className="min-h-screen p-8">
      <div className="flex items-end justify-between gap-6">
        <div>
          <h1 className="text-2xl font-semibold">Task Board</h1>
          <p className="text-sm text-muted-foreground mt-2 max-w-2xl">
            Assistant-only tasks (isolated from your Obsidian tasks). This board
            should reflect everything the assistant is working on.
          </p>
        </div>
        <button
          className="rounded-lg border px-3 py-2 text-sm hover:bg-muted/30"
          disabled
          title="Hook up Convex first"
        >
          + New task (soon)
        </button>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-4">
        {(Object.keys(statusLabel) as TaskStatus[]).map((s) => (
          <section key={s} className="rounded-xl border p-4">
            <div className="font-medium">{statusLabel[s]}</div>
            <div className="mt-3 space-y-3">
              {mock
                .filter((t) => t.status === s)
                .map((t) => (
                  <div key={t.id} className="rounded-lg border p-3">
                    <div className="text-sm font-medium">{t.title}</div>
                    {t.notes ? (
                      <div className="text-xs text-muted-foreground mt-2">
                        {t.notes}
                      </div>
                    ) : null}
                    <div className="text-xs text-muted-foreground mt-2">
                      Updated {new Date(t.updatedAt).toLocaleString()}
                    </div>
                  </div>
                ))}
              {mock.filter((t) => t.status === s).length === 0 ? (
                <div className="text-xs text-muted-foreground">No tasks</div>
              ) : null}
            </div>
          </section>
        ))}
      </div>

      <div className="mt-10 text-sm text-muted-foreground">
        Next step: wire this to Convex so tasks update in real time.
      </div>
    </main>
  );
}
