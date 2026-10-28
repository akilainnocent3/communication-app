# SMS — performance and background reliability

Budgets, how they are measured, and the results so far. Numbers here are measured, never estimated, unless a row
says "estimate". Rows still marked **not measured** need a machine with the Android SDK and an emulator (or a phone);
the method for each is given so anyone can fill them in.

## Admin API (server)

`backend/scripts/perf_sms.py`: one phone with 100 000 messages in 2 500 conversations (biggest thread 6 419
messages), 20 runs per endpoint after a warm-up, p95 by nearest rank. Budget: **≤ 300 ms p95**.

Environment: GitHub Codespace, 4 vCPU (AMD EPYC 7763), 16 GB RAM, PostgreSQL 16.15 in Docker on the same machine,
requests through the in-process DRF test client (no HTTP server), 2026-10-28.

| Endpoint | p50 ms | p95 ms | Max ms | SQL queries |
|---|---:|---:|---:|---:|
| Conversations, all phones (inbox) | 32 | 37 | 39 | 6 |
| Conversations, one phone | 36 | 39 | 39 | 8 |
| Conversations, page 2 (cursor) | 35 | 42 | 108 | 7 |
| Conversations, unread | 28 | 39 | 48 | 6 |
| Conversations, awaiting reply | 29 | 45 | 49 | 6 |
| Conversations, starred | 100 | 132 | 146 | 5 |
| Conversations, search by name | 18 | 19 | 19 | 7 |
| Conversations, search by number | 29 | 31 | 38 | 7 |
| Conversations, date range + has MMS | 9 | 12 | 13 | 5 |
| Open biggest thread (6 419 msgs) | 40 | 43 | 71 | 8 |
| Messages, newest page of biggest thread | 29 | 32 | 41 | 5 |
| Messages, older page (cursor) | 28 | 32 | 46 | 5 |
| Search inside a thread (20 msgs) | 18 | 19 | 20 | 6 |
| Search inside the biggest thread | 20 | 28 | 61 | 4 |
| Dashboard, 30 days | 190 | 224 | 231 | 12 |
| Dashboard, 365 days | 191 | 205 | 227 | 12 |
| Phone: claim outbox | 8 | 11 | 111 | 6 |
| Phone: sync 200 new messages (200 new numbers) | 3 262 | 3 467 | 3 480 | — |

Before → after for the two endpoints that were changed (decision 57):

| Endpoint | Before p50 / p95 | After p50 / p95 | Change |
|---|---:|---:|---|
| Search inside the biggest thread | 552 / 659 ms | 20 / 28 ms | scan `(id, ciphertext)` only, load the matches |
| Phone: sync 200 new messages | 3 880 / 3 992 ms | 3 262 / 3 467 ms | one-aggregate conversation refresh (7 → 4 queries), SIM look-up memoised per batch |

Every admin endpoint is within budget. The phone sync batch is not an admin endpoint: 3.5 s is the worst case (200
events that each create a new conversation, only during backfill) and is far inside the phone's 60 s read timeout; a
live incoming SMS is one event.

## APK size

Budget: release APK for arm64-v8a **≤ 25 MB**.

| Build | arm64-v8a size | How measured |
|---|---:|---|
| Before: universal release APK, 2026-10-28 07:22 (before decision 47) | ~32.8 MB (estimate) | sum of the entries an arm64 split would contain, from `unzip -v` of the universal APK; everything stored uncompressed, including ML Kit's bundled `libbarhopper_v3.so` (4.9 MB) |
| After: unbundled ML Kit model (decision 47) + compressed native libraries (decision 58) | ~15.5 MB (estimate) | the same entries without `libbarhopper_v3.so`, native libraries deflated with `gzip -6` |
| After, built with `flutter build apk --release --split-per-abi` | **not measured** | `ls -l build/app/outputs/flutter-apk/app-arm64-v8a-release.apk` |

What the arm64 libraries weigh (from the universal build): `libflutter.so` 11.8 MB (5.5 MB deflated), `libapp.so`
(the Dart code) 6.6 MB (2.5 MB), `libsqlcipher.so` 5.2 MB (2.3 MB), `classes.dex` 4.1 MB (stored).

## Phone (needs the Android SDK and an emulator)

Reference: emulator with 2 GB RAM, API 34, x86_64, seeded with 300 conversations and 20 000 messages
(`SeedReceiver`, see mobile/README.md), profile build.

| Measure | Budget | Before | After | Method |
|---|---|---|---|---|
| Cold start → conversation list visible | ≤ 800 ms | not measured | not measured | `adb shell am start -W`, plus `cm.perf first-list` in logcat |
| Tap a conversation → first messages | ≤ 150 ms, no spinner with a cache | not measured | not measured | `cm.perf chat-open` in logcat |
| List and chat scrolling | no frame > 16 ms | not measured | not measured | DevTools frame chart, profile build, fling the list and a 2 000-message chat |
| Memory, UI open | ≤ 120 MB PSS | not measured | not measured | `adb shell dumpsys meminfo com.kilimanjaro.communicationmanager.sms` |
| Memory, service only (UI swiped away) | ≤ 40 MB PSS | not measured | not measured | the same, after swiping the app from recents |
| Incoming SMS → visible in the admin | ≤ 5 s | not measured | not measured | `adb emu sms send`, watch the admin conversation list |

## Background matrix

For every row: an incoming SMS (`adb emu sms send`) must reach the server, and an admin reply must be sent.
Emulators: API 29, 31, 33, 34, 35/36.

| Scenario | How | API 29 | 31 | 33 | 34 | 35/36 |
|---|---|---|---|---|---|---|
| App in the background | press Home | not run | not run | not run | not run | not run |
| Swiped from recents | recents → swipe | not run | not run | not run | not run | not run |
| Doze | `adb shell dumpsys deviceidle force-idle` | not run | not run | not run | not run | not run |
| Standby bucket "rare" | `adb shell am set-standby-bucket <pkg> rare` | not run | not run | not run | not run | not run |
| Reboot | `adb reboot` | not run | not run | not run | not run | not run |
| Network off → on | `adb shell svc data disable` / `enable` (and wifi) | not run | not run | not run | not run | not run |
| Process killed | `adb shell am kill <pkg>` | not run | not run | not run | not run | not run |
| Force stop (expected to fail) | `adb shell am force-stop <pkg>` | nothing arrives until the app is opened; documented limit | | | | |
