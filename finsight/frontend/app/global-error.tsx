"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-950 text-slate-50 flex items-center justify-center p-6 antialiased">
        <div className="max-w-md w-full rounded-lg border border-slate-800 bg-slate-900 p-8 text-center shadow-xl">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-950/50 text-red-500 mb-4">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100">
            Critical Application Error
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            A critical system error prevented FinSight from initializing.
          </p>
          <div className="mt-6">
            <button
              onClick={() => reset()}
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <RefreshCw className="h-4 w-4" />
              Reload Application
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
