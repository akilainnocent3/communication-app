"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ErrorIcon } from "@/components/ui/icons";
import { connectResult } from "@/platforms/gmail/components/mailboxes/connect-results";
import { ConnectFrame } from "../connect-ui";

/** Where the OAuth callback lands when it cannot tell which link started the sign-in (tampered or expired state). */
export default function ConnectResultPage() {
  return <Suspense fallback={<ConnectFrame>{null}</ConnectFrame>}><Result /></Suspense>;
}

function Result() {
  const params = useSearchParams();
  const result = connectResult(params.get("result") || "error", params);
  return (
    <ConnectFrame>
      <div role="status" className="flex flex-col items-center py-10 text-center">
        <span className="flex size-20 items-center justify-center rounded-full bg-error-500/10 text-error-500"><ErrorIcon size={44} /></span>
        <h1 className="mt-5 text-2xl font-semibold text-text-primary">{result?.title}</h1>
        <p className="mt-2 max-w-sm text-sm text-text-secondary">{result?.body} Open the connect link you were sent again to retry.</p>
      </div>
    </ConnectFrame>
  );
}
