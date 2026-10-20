// The top of every page: a huge condensed title on the left,
// one sentence about the page on the right (under it on phones).
export default function PageTitle({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between sm:gap-10">
      <h1 className="display">{title}</h1>
      <p className="max-w-md text-muted sm:pb-2 sm:text-right">{children}</p>
    </header>
  );
}
