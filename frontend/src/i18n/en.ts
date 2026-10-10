/**
 * Every user-facing string lives here so another language (Swahili first) can be added by providing a second
 * object with the same shape and choosing it in `i18n/index.ts`.
 */
export const en = {
  brand: { name: "Communication Manager", short: "CM", tagline: "Every company channel, one place." },
  common: {
    retry: "Retry", cancel: "Cancel", save: "Save", saving: "Saving…", saved: "Saved", delete: "Delete", edit: "Edit",
    close: "Close", back: "Back", add: "Add", create: "Create", confirm: "Confirm", loading: "Loading…", search: "Search",
    copy: "Copy", copied: "Copied", undo: "Undo", done: "Done", next: "Next", optional: "optional", soon: "Soon",
    yes: "Yes", no: "No", none: "None", all: "All", never: "Never", offline: "You're offline. Changes will fail until the connection returns.",
    noPermission: "You don't have permission to see this page.",
  },
  auth: {
    title: "Sign in", subtitle: "Use your company account to manage every channel.", email: "Email address", password: "Password",
    otp: "6-digit code", otpHint: "Open your authenticator app and enter the current code.", submit: "Sign in", submitting: "Signing in…",
    signOut: "Sign out", signingOut: "Signing out…", sessionExpired: "Your session ended. Sign in again to continue.",
  },
  shell: {
    openMenu: "Open sidebar menu", closeMenu: "Close sidebar", toggleSidebar: "Toggle sidebar", quickAccess: "Open quick access",
    theme: "Toggle colour theme", palette: "Search and commands", palettePlaceholder: "Type a command or search…", paletteEmpty: "No matching commands.",
    platformSwitched: (name: string) => `Switched to ${name}`, comingSoon: (name: string) => `${name} is coming soon`, home: "Communication Manager home",
    settings: "SETTINGS", searchMenu: "Search menu", noMenuMatch: (q: string) => `No menu items match “${q}”.`,
    preferences: "Preferences", account: "Account menu",
  },
  platforms: {
    gmail: { name: "Gmail", description: "Company and office mailboxes" },
    sms: { name: "SMS", description: "Bulk and two-way text messages" },
    calls: { name: "Calls", description: "Call logs and recordings" },
    media: { name: "Media", description: "Social media inboxes" },
  },
} as const;

export type Messages = typeof en;
