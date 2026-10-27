"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { DevicesPage } from "@/platforms/sms/components/devices/devices-page";

function WithParams() {
  const params = useSearchParams();
  return <DevicesPage enroll={params.get("enroll") === "1"} />;
}

export default function SmsDevicesPage() {
  return <Suspense><WithParams /></Suspense>;
}
