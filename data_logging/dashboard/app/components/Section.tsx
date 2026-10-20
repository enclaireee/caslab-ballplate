// One panel: a small label on top, then the content.
// On phones the panel runs edge to edge (-mx-4 cancels the page padding).
// "right" is optional extra content on the right of the label.
export default function Section({
  title,
  right,
  children,
}: {
  title: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="-mx-4 min-w-0 border-y border-line bg-panel p-4 sm:mx-0 sm:border sm:p-5">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="label">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}
