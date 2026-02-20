import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  tasks: defineTable({
    title: v.string(),
    status: v.union(
      v.literal("todo"),
      v.literal("in_progress"),
      v.literal("blocked"),
      v.literal("done")
    ),
    notes: v.optional(v.string()),
    createdAt: v.number(),
    updatedAt: v.number(),
  }).index("by_status", ["status"]),

  scheduledItems: defineTable({
    kind: v.union(v.literal("cron"), v.literal("scheduled_task")),
    title: v.string(),
    schedule: v.string(),
    nextRunAt: v.optional(v.number()),
    source: v.optional(v.string()),
    createdAt: v.number(),
    updatedAt: v.number(),
  }).index("by_nextRunAt", ["nextRunAt"]),

  memoryDocs: defineTable({
    title: v.string(),
    body: v.string(),
    source: v.optional(v.string()), // e.g. MEMORY.md, memory/2026-02-20.md
    updatedAt: v.number(),
  }).searchIndex("search_body", { searchField: "body", filterFields: ["source"] }),

  modelEvents: defineTable({
    model: v.string(),
    kind: v.union(v.literal("call"), v.literal("rate_limit"), v.literal("error")),
    meta: v.optional(v.any()),
    createdAt: v.number(),
  }).index("by_model", ["model"]),
});
