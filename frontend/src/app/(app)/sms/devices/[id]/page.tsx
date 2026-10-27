"use client";

import { useParams } from "next/navigation";
import { DeviceDetailPage } from "@/platforms/sms/components/devices/device-detail";

export default function SmsDevicePage() {
  const { id } = useParams<{ id: string }>();
  return <DeviceDetailPage id={id} />;
}
