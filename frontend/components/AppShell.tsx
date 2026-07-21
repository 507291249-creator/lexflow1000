import { TopNavigation } from "@/components/TopNavigation";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-app flex flex-col">
      <TopNavigation />
      <main className="flex-1 mx-auto w-full max-w-[1920px] px-6 py-4 md:px-8">{children}</main>
    </div>
  );
}
