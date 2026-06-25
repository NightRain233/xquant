import { ShieldAlert } from "lucide-react";
import type { RiskNote } from "../data/types";

type RiskReviewPanelProps = {
  notes: RiskNote[];
};

export function RiskReviewPanel({ notes }: RiskReviewPanelProps) {
  return (
    <section className="border border-ink/15 bg-paper p-5">
      <div className="flex items-center gap-2">
        <ShieldAlert size={18} strokeWidth={1.8} className="text-amber-800" />
        <h2 className="text-xl font-semibold tracking-tight">风险复核</h2>
      </div>
      <div className="mt-5 space-y-4">
        {notes.map((note) => (
          <article key={note.title} className="border-t border-ink/10 pt-4">
            <h3 className="text-sm font-semibold">{note.title}</h3>
            <p className="mt-2 text-sm leading-6 text-ink/65">{note.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
