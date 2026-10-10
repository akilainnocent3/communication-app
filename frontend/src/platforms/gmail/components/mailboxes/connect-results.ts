/** Friendly copy for the `?result=` codes the OAuth callback redirects with (admin page and public connect page). */
export type ConnectResult = { tone: "success" | "error" | "warning"; title: string; body: string; retry: boolean };

export function connectResult(code: string | null, params: URLSearchParams, expected?: string): ConnectResult | null {
  switch (code) {
    case null:
    case "":
      return null;
    case "connected":
      return { tone: "success", title: "Mailbox connected", body: "The inbox is syncing now. New mail appears within a minute.", retry: false };
    case "wrong_account":
      return {
        tone: "error",
        title: "That was a different account",
        body: `You signed in as ${params.get("signed_in_as") || "another account"}, but this link is for ${expected || "a different mailbox"}. Try again and choose the right account.`,
        retry: true,
      };
    case "missing_scopes":
      return {
        tone: "warning",
        title: "Some permissions were not allowed",
        body: "Google showed checkboxes and at least one was left unticked. Try again and leave every box ticked so the mailbox can be read and managed.",
        retry: true,
      };
    case "denied":
      return { tone: "warning", title: "Connection cancelled", body: "Access was not allowed on the Google screen. Nothing was connected. You can try again at any time.", retry: true };
    case "expired":
    case "invalid_state":
      return { tone: "warning", title: "The sign-in took too long", body: "For safety, each attempt is only valid for a short time. Start again.", retry: true };
    case "invite_inactive":
      return { tone: "error", title: "This link can't be used any more", body: "It was already used, revoked or has expired. Ask your administrator for a new link.", retry: false };
    default:
      return { tone: "error", title: "Couldn't connect the mailbox", body: "Google returned an error. Try again; if it keeps failing, contact your administrator.", retry: true };
  }
}
