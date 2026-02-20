import Link from "next/link";
import { UserButton } from "@clerk/nextjs";

const cards = [
  {
    title: "Task Board",
    href: "/task-board",
    desc: "Assistant-only tasks with status tracking.",
  },
  {
    title: "Calendar",
    href: "/calendar",
    desc: "Scheduled tasks + cron jobs (assistant-only).",
  },
  {
    title: "Memory",
    href: "/memory",
    desc: "Browse and search memories (documents).",
  },
  {
    title: "AI Model Usage",
    href: "/models",
    desc: "Usage overview + rate limit events.",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Mission Control</h1>
          <p className="text-muted-foreground mt-2 max-w-2xl">
            Single-user dashboard for assistant tasks, schedules, memories, and
            model usage.
          </p>
        </div>
        <UserButton />
      </div>

      <div className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-2">
        {cards.map((c) => (
          <Link
            key={c.href}
            href={c.href}
            className="rounded-xl border p-5 hover:bg-muted/30 transition"
          >
            <div className="text-lg font-medium">{c.title}</div>
            <div className="text-sm text-muted-foreground mt-2">{c.desc}</div>
          </Link>
        ))}
      </div>

      <div className="mt-10 text-sm text-muted-foreground">
        <div>
          Next.js + Convex + Clerk. Deploy on Vercel for access from anywhere.
        </div>
      </div>
    </main>
  );
}
