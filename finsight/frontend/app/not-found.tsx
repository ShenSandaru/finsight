import Link from "next/link";
import { FileQuestion, ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center p-6 text-center">
      <div className="rounded-full bg-muted p-4 text-muted-foreground mb-4">
        <FileQuestion className="h-8 w-8" aria-hidden="true" />
      </div>
      <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
        404 — Research View Not Found
      </h1>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        The requested report, document, or conversational session does not exist or has been removed.
      </p>
      <div className="mt-6">
        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow transition hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Overview
        </Link>
      </div>
    </div>
  );
}
