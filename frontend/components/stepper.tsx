type StepperProps = {
  steps: string[];
  current: number;
};

export function Stepper({ steps, current }: StepperProps) {
  return (
    <div className="flex w-full items-center">
      {steps.map((label, idx) => {
        const active = idx === current;
        const completed = idx < current;
        const isLast = idx === steps.length - 1;

        return (
          <div
            key={label}
            className={`${isLast ? "flex-none" : "flex-1"} flex items-center`}
          >
            <div
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-xs font-semibold sm:h-9 sm:w-9 sm:text-sm ${
                active
                  ? "border-zinc-900 bg-zinc-900 text-white shadow-sm"
                  : completed
                    ? "border-zinc-500 bg-zinc-500 text-white"
                    : "border-zinc-300 bg-white text-zinc-500"
              }`}
            >
              {idx + 1}
            </div>
            {!isLast && (
              <div className="mx-2 h-[3px] flex-1 rounded-full bg-zinc-200 sm:mx-3">
                <div
                  className={`h-[3px] w-full rounded-full transition-all ${
                    completed ? "bg-zinc-500" : active ? "bg-zinc-400" : "bg-zinc-200"
                  }`}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
