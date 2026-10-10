import { redirect } from "next/navigation";

export default function GmailHome() {
  redirect("/gmail/inbox");
}
