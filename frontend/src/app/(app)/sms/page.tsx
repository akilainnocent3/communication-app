import { redirect } from "next/navigation";

export default function SmsHome() {
  redirect("/sms/inbox");
}
