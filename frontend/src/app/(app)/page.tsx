"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { platformEntry } from "@/components/shell/active-platform";
import { useSession } from "@/components/shell/session-provider";
import { readStored } from "@/lib/storage";
import { visiblePlatforms } from "@/platforms/registry";

/** "/" goes to the last used platform (its last visited page) or the first one the user may open. */
export default function Home() {
  const router = useRouter();
  const { me } = useSession();
  useEffect(() => {
    const platforms = visiblePlatforms(me?.platforms as { key: string; order: number }[] | undefined).filter((platform) => platform.status === "active");
    const last = readStored<string>("cm:last-platform", "");
    const target = platforms.find((platform) => platform.key === last) ?? platforms[0];
    router.replace(target ? platformEntry(target) : "/settings/preferences");
  }, [me, router]);
  return null;
}
