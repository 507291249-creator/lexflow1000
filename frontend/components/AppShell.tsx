import { TopNavigation } from "@/components/TopNavigation";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-app">
      <TopNavigation />
      <main className="mx-auto max-w-[1920px] px-4 py-5 sm:px-6">{children}</main>
    </div>
  );
}
