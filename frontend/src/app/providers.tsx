"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { RouterProvider } from "react-aria-components";
import { ApiError } from "@/services/api/client";
import { startNavigationPending } from "@/components/shell/navigation-pending";

declare module "react-aria-components" {
  interface RouterConfig {
    routerOptions: NonNullable<Parameters<ReturnType<typeof useRouter>["push"]>[1]>;
  }
}

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: true,
        // Client errors (403, 404, validation) never get better by retrying.
        retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
      },
    },
  });
}

export default function Providers({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [queryClient] = useState(makeClient);
  // react-aria links and menu items with `href` navigate client-side through the App Router.
  return (
    <RouterProvider navigate={(href, options) => { startNavigationPending(href); router.push(href, options); }}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </RouterProvider>
  );
}
