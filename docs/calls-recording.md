# Call recording: why v1 records no audio, and the legitimate path

**OCM v1 does not record call audio.** The Calls platform stores call *metadata* only (number, times, result, SIM,
outcome and notes). This page explains why, what must never be built instead, and how recording can be added properly
later.

## Why the phone app cannot record

- **Android blocks it.** Since Android 10 the voice-call audio source (`MediaRecorder.AudioSource.VOICE_CALL`,
  `VOICE_UPLINK`, `VOICE_DOWNLINK`) requires `CAPTURE_AUDIO_OUTPUT`, a permission only system apps (signed with the
  platform key or privileged on the system image) can hold. Being the default phone app does not grant it.
- **Google Play bans the workarounds.** Recording calls through the Accessibility API is explicitly prohibited by the
  Accessibility policy, and apps that do it are removed. The `play` flavor must pass review; the `private` (MDM) flavor
  follows the same rules so both behave identically.
- **The workarounds are unreliable and unlawful-looking anyway.** Speakerphone + microphone recording captures only
  the near side clearly, depends on volume and room noise, breaks with Bluetooth and earpiece routing, and gives the
  other party no notice. It would also make the app look exactly like the stalkerware that Play's monitoring-app
  policy targets.

**Not to be built, ever:** microphone or speaker tricks during a call, Accessibility-service capture, root-only
capture, OEM private APIs, or anything that records without the other party being told.

## The legitimate future path: record in the network, with announced consent

Route company calls through a **cloud PBX / SIP provider that records server-side**:

1. The company gets numbers (DIDs) from a licensed Tanzanian provider with a hosted PBX, or a SIP trunk into a PBX the
   company controls.
2. Customers call the company number; the PBX plays a **recording announcement** ("This call may be recorded for
   quality and training") before connecting, and the caller can choose not to proceed. Outbound calls play the same
   announcement to the customer.
3. The PBX rings the staff member (on a SIP app, a desk phone, or forwarded to the company SIM) and records the call on
   the server. Nothing on the Android phone records anything.
4. OCM pulls the recordings and call detail records through the provider's API (or webhooks) into a future
   `modules/calls` provider adapter, linked to the same `CallRecord`/`Customer` by number and time. Recordings are
   stored encrypted (like MMS media under `SMS_DATA_KEYS`), with their own retention period, access permission
   (`calls.listen`, granted per phone/office) and an audit event on every playback and download.

That is a separate project (VoIP/SIP calling is out of scope for v1), but the data model already leaves room for it:
recordings attach to a `CallRecord` and never change how carrier calls on the phone work.

## Legal notes for Tanzania (to verify with counsel)

These are points to raise with the company's lawyer before any recording is switched on. They are **not legal advice**
and must be confirmed against the current texts and regulations:

- **Constitution, Article 16:** the right to privacy of a person's communications. Recording is an interference that
  needs a lawful basis.
- **Electronic and Postal Communications Act (EPOCA, 2010) and its regulations:** interception or recording of
  communications is restricted; check whether a party to the call recording it for business purposes, with notice, is
  permitted, and what the TCRA rules for service providers require of a hosted PBX operator.
- **Personal Data Protection Act, 2022 and its regulations (PDPC):** a recording is personal data of the customer and
  of the employee. Points to settle: registration of the company as a data controller/processor, the lawful basis
  (consent vs. legitimate interest), notice (the announcement and the privacy policy), purpose limitation (quality,
  training, disputes), retention period, data subject access to recordings, security measures, and cross-border
  transfer if the provider stores recordings outside Tanzania.
- **Cybercrimes Act, 2015:** check offences around unlawful interception and access, so that only authorised staff can
  reach recordings.
- **Employment and Labour Relations Act:** employees must be told that their work calls are recorded (contract or
  written policy), separate from the customer announcement.
- **Sector rules:** banks, mobile-money agents and insurers may have their own recording or retention obligations
  (BoT, TIRA).

Until counsel signs off, keep the v1 position: metadata only, disclosed in the store listing, the in-app monitoring
notice and the privacy policy ([play-store.md](play-store.md)).
