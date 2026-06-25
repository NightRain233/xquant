export type DashboardMode = "report" | "paper";

type ModeTabsProps = {
  mode: DashboardMode;
  onModeChange: (mode: DashboardMode) => void;
};

const tabs: Array<{ id: DashboardMode; label: string }> = [
  { id: "report", label: "研究汇报" },
  { id: "paper", label: "纸面跟踪" }
];

export function ModeTabs({ mode, onModeChange }: ModeTabsProps) {
  return (
    <div className="inline-grid grid-cols-2 gap-1 border border-ink/15 bg-paper p-1">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`min-h-10 px-4 text-sm font-medium transition active:translate-y-px ${
            mode === tab.id ? "bg-ink text-paper" : "text-ink/65 hover:bg-ink/5"
          }`}
          type="button"
          onClick={() => onModeChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
