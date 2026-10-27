# SMS platform — handoff (session paused at the usage limit, 2026-10-27)

Branch `feature/sms-platform`. All work so far is committed.

## Done and verified
- Backend (`modules/devices`, `modules/sms`): all milestones 1–3. pytest green (old + new; ~230 tests), coverage 87 %
  on new services/API, `makemigrations --check` clean, `spectacular --validate` clean (Gmail schema unchanged),
  `check --deploy` clean under prod; prod refuses missing/dev/shared `SMS_DATA_KEYS` and the simulator.
- Admin UI (milestone 4): typecheck + lint clean; `e2e/sms.spec.ts` passes on all 4 Playwright projects.
- Flutter app (milestones 5–6): `flutter analyze` clean, 28 Dart tests pass; Kotlin layer compiles
  (`flutter build apk --debug` OK); 9 Kotlin (Robolectric) tests pass.
- Docs: sms-mobile.md, mobile/README.md, decisions 19–38, architecture, security, deployment, README; nginx, compose,
  .env.example.

## Left to do (in order)
1. Security review: an identification pass was started; filter its findings (confidence ≥ 8) and fix any real ones.
2. Release APK: `flutter build apk --release` / `./gradlew --no-daemon assembleRelease` failed (see log; the Gradle
   daemon is killed for memory on this 8 GB box during R8 — retry with more RAM or `org.gradle.workers.max=1`).
3. Full Playwright suite (Gmail + SMS) in one run with only the dev servers up (an earlier full run was invalidated
   when the Next dev server was killed); confirm Gmail E2E unchanged.
4. Performance: run `perf.py` (100k messages on one phone) and record timings; add indexes if any endpoint is slow.
5. Commit the new SMS screenshots in docs/screenshots/; emulator walkthrough screenshots (docs/screenshots/sms-mobile-*)
   and the `adb emu sms send` integration test need an emulator (not available here).
6. Rewrite docs/status.md as the final report (merge this file into it).
