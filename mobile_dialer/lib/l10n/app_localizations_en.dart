// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'Phone';

  @override
  String get companyApp => 'Phone';

  @override
  String get onboardingTitle => 'Make this the phone\'s SMS app';

  @override
  String get onboardingBody =>
      'This company phone\'s text messages are managed by your company. To receive and send SMS, this app must be the default SMS app.';

  @override
  String get setDefault => 'Set as default SMS app';

  @override
  String get permissionsTitle => 'Allow access';

  @override
  String get permissionsBody =>
      'The app needs these permissions to receive, store and send text messages, show who is writing, and notify you.';

  @override
  String get permissionSms => 'Text messages (receive, read, send)';

  @override
  String get permissionContacts =>
      'Contacts (names of people who write to you)';

  @override
  String get permissionPhone => 'Phone and SIM (which SIM a message uses)';

  @override
  String get permissionNotifications => 'Notifications (new messages)';

  @override
  String get grant => 'Allow';

  @override
  String get continueLabel => 'Continue';

  @override
  String get batteryTitle => 'Keep call records flowing';

  @override
  String get batteryBody =>
      'Some phones stop apps in the background. Turn off battery optimisation for this app so call records and call-backs are never delayed.';

  @override
  String get batterySamsung =>
      'On Samsung: Settings → Battery → Background usage limits → Never sleeping apps → add OCM.';

  @override
  String get batteryOpen => 'Open battery settings';

  @override
  String get enrollTitle => 'Connect to your company';

  @override
  String get enrollBody =>
      'Scan the QR code your administrator shows you, tap the link they sent, or type the 8-character code.';

  @override
  String get scanQr => 'Scan QR code';

  @override
  String get enterCode => 'Enter code';

  @override
  String get codeLabel => 'Enrollment code';

  @override
  String get serverLabel => 'Company server';

  @override
  String get untrustedServer =>
      'This QR code points to a server this app is not allowed to use. Ask your administrator.';

  @override
  String get noticeTitle => 'Monitoring notice';

  @override
  String get noticeAccept => 'I understand and accept';

  @override
  String get noticeDecline => 'Not now';

  @override
  String get enrolling => 'Connecting this phone…';

  @override
  String enrolled(String code) {
    return 'This phone is connected as $code.';
  }

  @override
  String get removedTitle => 'This phone was removed by your administrator';

  @override
  String get removedBody =>
      'Its connection to the company has been deleted. Calls are no longer recorded. You can keep using this app as your Phone app, or choose another one.';

  @override
  String get pausedBanner => 'Syncing is paused by your administrator.';

  @override
  String get notDefaultBanner =>
      'This app is not the default SMS app. Messages can\'t be received or sent.';

  @override
  String get fixNow => 'Fix';

  @override
  String get conversations => 'Messages';

  @override
  String get archived => 'Archived';

  @override
  String get spamBlocked => 'Spam & blocked';

  @override
  String get starred => 'Starred';

  @override
  String get searchHint => 'Search conversations';

  @override
  String get startChat => 'Start chat';

  @override
  String get noConversations => 'No conversations yet';

  @override
  String get noConversationsBody =>
      'Text messages you send and receive appear here.';

  @override
  String selectedCount(int count) {
    return '$count selected';
  }

  @override
  String get markRead => 'Mark as read';

  @override
  String get markUnread => 'Mark as unread';

  @override
  String get pin => 'Pin';

  @override
  String get unpin => 'Unpin';

  @override
  String get mute => 'Mute';

  @override
  String get unmute => 'Unmute';

  @override
  String get archive => 'Archive';

  @override
  String get unarchive => 'Unarchive';

  @override
  String get delete => 'Delete';

  @override
  String get block => 'Block';

  @override
  String get unblock => 'Unblock';

  @override
  String get moveToSpam => 'Move to spam';

  @override
  String deleteConfirm(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count conversations',
      one: 'this conversation',
    );
    return 'Delete $_temp0 from this phone?';
  }

  @override
  String get cancel => 'Cancel';

  @override
  String get undo => 'Undo';

  @override
  String get today => 'Today';

  @override
  String get yesterday => 'Yesterday';

  @override
  String get messageHint => 'Text message';

  @override
  String get send => 'Send';

  @override
  String segments(int segments, int remaining) {
    return '$segments SMS · $remaining left';
  }

  @override
  String get mmsWillSend => 'Sends as MMS';

  @override
  String get sentByAdmin => 'Sent by admin';

  @override
  String sentByAdminNamed(String name) {
    return 'Sent by admin · $name';
  }

  @override
  String adminReplied(String name) {
    return 'Admin replied to $name';
  }

  @override
  String get statusSending => 'Sending…';

  @override
  String get statusSent => 'Sent';

  @override
  String get statusDelivered => 'Delivered';

  @override
  String get statusFailed => 'Not sent. Tap to retry';

  @override
  String get statusQueued => 'Queued';

  @override
  String get copy => 'Copy';

  @override
  String get copyCode => 'Copy code';

  @override
  String get codeCopied => 'Code copied';

  @override
  String get forward => 'Forward';

  @override
  String get share => 'Share';

  @override
  String get star => 'Star';

  @override
  String get unstar => 'Unstar';

  @override
  String get details => 'Details';

  @override
  String get detailsSent => 'Sent';

  @override
  String get detailsReceived => 'Received';

  @override
  String get detailsSim => 'SIM';

  @override
  String get detailsStatus => 'Status';

  @override
  String get detailsFrom => 'From';

  @override
  String get toHint => 'Name or number';

  @override
  String get newConversation => 'New conversation';

  @override
  String get scheduleSend => 'Schedule send';

  @override
  String scheduledFor(String time) {
    return 'Scheduled for $time';
  }

  @override
  String get attach => 'Attach';

  @override
  String get camera => 'Camera';

  @override
  String get gallery => 'Gallery';

  @override
  String get files => 'Files';

  @override
  String get quickReplies => 'Quick replies';

  @override
  String get chooseSim => 'Choose SIM';

  @override
  String get settings => 'Settings';

  @override
  String get defaultSim => 'Default SIM';

  @override
  String get deliveryReports => 'Delivery reports';

  @override
  String get mmsAutoDownload => 'Auto-download MMS';

  @override
  String get mmsWifiOnly => 'Wi-Fi only';

  @override
  String get mmsAlways => 'Always';

  @override
  String get mmsNever => 'Never';

  @override
  String get hideOnLockScreen => 'Hide message text on the lock screen';

  @override
  String get appLock => 'Lock with fingerprint or PIN';

  @override
  String get secureScreen => 'Block screenshots';

  @override
  String get textSize => 'Text size';

  @override
  String get appearance => 'Appearance';

  @override
  String get syncStatus => 'Sync status';

  @override
  String get syncNow => 'Sync now';

  @override
  String get server => 'Server';

  @override
  String get deviceCode => 'Device code';

  @override
  String get lastSync => 'Last sync';

  @override
  String get pendingUploads => 'Waiting to upload';

  @override
  String get connectivity => 'Connection';

  @override
  String get online => 'Online';

  @override
  String get offline => 'Offline';

  @override
  String get never => 'Never';

  @override
  String get about => 'About';

  @override
  String get aboutBody =>
      'Calls made and received on this company phone are recorded in your company\'s OCM (Office Communication Management): the number, time, duration and result, never the conversation. Authorised administrators can see these records and ask you to call customers back. All access is logged.';

  @override
  String get unlock => 'Unlock';

  @override
  String get locked => 'OCM is locked';

  @override
  String backfillProgress(int done, int total) {
    return 'Copying message history: $done of $total';
  }

  @override
  String get flashMessage => 'Flash message';

  @override
  String get startupErrorTitle => 'OCM could not start';

  @override
  String get startupErrorBody =>
      'Your calls and contacts are safe on this phone. Try again; if this keeps happening, restart the phone or contact your administrator.';

  @override
  String get tryAgain => 'Try again';

  @override
  String get sendRefused =>
      'Message not sent. Check that OCM Messages is the default SMS app and a SIM card is active, then try again.';

  @override
  String unreadConversations(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count unread conversations',
      one: '1 unread conversation',
    );
    return '$_temp0';
  }

  @override
  String get messagesSection => 'Messages';

  @override
  String get moreResults => 'More results';

  @override
  String get noResults => 'No results';

  @override
  String get contacts => 'Contacts';

  @override
  String get selectText => 'Select text';

  @override
  String get done => 'Done';

  @override
  String get appearanceHint => 'Style, theme, text size';

  @override
  String get keepFlowingTitle => 'Keep call records flowing';

  @override
  String get keepFlowingHint =>
      'Stop the phone from pausing this app in the background';

  @override
  String get keepFlowingBody =>
      'Phones save battery by pausing apps in the background. Allow this app to run so call records reach your company at once and call-backs arrive on time.';

  @override
  String get style => 'Style';

  @override
  String get matchMyPhone => 'Match my phone';

  @override
  String get skinOneUi => 'One UI style';

  @override
  String get skinPixel => 'Pixel / Material You style';

  @override
  String get skinHios => 'HiOS / XOS style';

  @override
  String get skinHyperOs => 'HyperOS / MIUI style';

  @override
  String get skinColorOs => 'ColorOS style';

  @override
  String get skinCompany => 'Company';

  @override
  String get theme => 'Theme';

  @override
  String get themeSystem => 'System';

  @override
  String get themeLight => 'Light';

  @override
  String get themeDark => 'Dark';

  @override
  String get bubbleColour => 'Bubble colour';

  @override
  String get listDensity => 'List density';

  @override
  String get densityComfortable => 'Comfortable';

  @override
  String get densityCompact => 'Compact';

  @override
  String get swipeActions => 'Swipe actions';

  @override
  String get swipeRight => 'Swipe right';

  @override
  String get swipeLeft => 'Swipe left';

  @override
  String get none => 'None';

  @override
  String get showContactPhotos => 'Show contact photos';

  @override
  String get checkBattery => 'Battery optimisation is off for this app';

  @override
  String get checkBackground => 'Background use is not restricted';

  @override
  String get checkStandby => 'Android is not holding the app back';

  @override
  String get allow => 'Allow';

  @override
  String get open => 'Open';

  @override
  String get oemSamsung => 'Samsung: add to \"Never sleeping apps\"';

  @override
  String get oemXiaomi => 'Xiaomi: allow Autostart';

  @override
  String get oemTranssion =>
      'Tecno / Infinix / itel: allow auto-start in Phone Master, and lock the app in recent apps';

  @override
  String get oemOppo => 'Oppo / Realme: allow auto-launch';

  @override
  String get oemOneplus => 'OnePlus: allow auto-launch';

  @override
  String get oemHuawei => 'Huawei: manage app launch manually and allow all';

  @override
  String get oemCannotCheck =>
      'The phone does not tell apps whether this is on: check it once.';

  @override
  String get forceStopWarning =>
      'Never use \"Force stop\" on this app: Android then stops it until it is opened again, and calls are not recorded meanwhile.';

  @override
  String get syncService => 'Sync service';

  @override
  String get running => 'Running';

  @override
  String get notRunning => 'Not running';

  @override
  String get welcomeTitle => 'Your company\'s Phone app';

  @override
  String get welcomeBody =>
      'Call and answer as usual. Your company sees the call records of this company phone and can ask you to call customers back.';

  @override
  String get getStarted => 'Get started';

  @override
  String get whyDefault =>
      'Android lets only the default SMS app receive messages, save them and send them. Your old Messages app keeps working as a normal app.';

  @override
  String get roleFallback =>
      'The dialog did not appear or was closed. Choose this app in Settings → Default apps → SMS app.';

  @override
  String get openDefaultApps => 'Open Default apps';

  @override
  String get whyPermissions =>
      'SMS: to read, save and send messages. Contacts: to show names instead of numbers (names are never uploaded except for numbers you message). Phone: to use the right SIM.';

  @override
  String get notificationsTitle => 'Know when messages arrive';

  @override
  String get whyNotifications =>
      'New messages, failed sends and admin replies show as notifications. Their text is hidden on the lock screen.';

  @override
  String get notNow => 'Not now';

  @override
  String get whyFlowing =>
      'Without this some phones stop the app minutes after the screen turns off, and messages reach your company hours late.';

  @override
  String get permissionDeniedForGood =>
      'Permission was refused. Allow it in the app settings.';

  @override
  String get openSettings => 'Open settings';

  @override
  String get why => 'Why?';

  @override
  String get torch => 'Torch';

  @override
  String get notAnEnrollCode =>
      'That is not an enrollment code for this app. Scan the code from Admin → Calls → Phones → Enroll OCM Phone.';

  @override
  String get noQrInPhoto => 'No QR code found in that photo.';

  @override
  String get pointAtQr => 'Point the camera at the administrator\'s QR code';

  @override
  String get scanFromPhoto => 'Scan from photo';

  @override
  String get cameraRationale =>
      'The camera is used only to read your administrator\'s QR code. Nothing is recorded.';

  @override
  String get whyEnroll =>
      'Connecting records this phone\'s calls (number, time, duration, never the conversation) for your company. You will see the monitoring notice before anything is connected.';

  @override
  String get orTypeCode => 'or type the code';

  @override
  String get shortCodeLabel => 'Code';

  @override
  String get noConnection =>
      'No connection to the server. Check the internet and try again.';

  @override
  String get tooManyAttempts =>
      'Too many attempts. Wait a few minutes and try again.';

  @override
  String get enrolledTitle => 'Connected';

  @override
  String get enrolledBody =>
      'Calls are now recorded for your company. Next, make this app your Phone app.';

  @override
  String get openMessages => 'Open messages';

  @override
  String get backfillDone => 'Message history copied';

  @override
  String backfillCopied(int count) {
    return '$count messages copied…';
  }

  @override
  String get phoneTitle => 'Phone';

  @override
  String get tabKeypad => 'Keypad';

  @override
  String get tabRecents => 'Recents';

  @override
  String get tabContacts => 'Contacts';

  @override
  String get tabCallbacks => 'Call-backs';

  @override
  String get favourites => 'Favourites';

  @override
  String get callAction => 'Call';

  @override
  String get messageAction => 'Message';

  @override
  String get addContact => 'Add contact';

  @override
  String get blockNumber => 'Block number';

  @override
  String get deleteFromRecents => 'Delete from recents';

  @override
  String get noRecents => 'No calls yet';

  @override
  String get noContacts => 'No contacts';

  @override
  String get noCallbacks =>
      'No call-backs. When the office asks you to call someone, it appears here.';

  @override
  String get searchContacts => 'Search contacts';

  @override
  String get companyDirectory => 'Company directory';

  @override
  String get voicemail => 'Voicemail';

  @override
  String get callWith => 'Call with';

  @override
  String get paste => 'Paste';

  @override
  String requestedBy(String name) {
    return 'Requested by $name';
  }

  @override
  String get snoozeAction => 'Snooze 1 h';

  @override
  String get doneAction => 'Done';

  @override
  String get resultMissed => 'Missed';

  @override
  String get resultAnswered => 'Answered';

  @override
  String get resultRejected => 'Declined';

  @override
  String get resultBlocked => 'Blocked';

  @override
  String get resultVoicemail => 'Voicemail';

  @override
  String get resultNoAnswer => 'No answer';

  @override
  String get resultElsewhere => 'Answered elsewhere';

  @override
  String get incomingCall => 'Incoming';

  @override
  String get outgoingCall => 'Outgoing';

  @override
  String get privateNumber => 'Private number';

  @override
  String get callFailedPermission => 'Allow phone calls for OCM first.';

  @override
  String get dialerTitle => 'Make OCM your Phone app';

  @override
  String get dialerBody =>
      'Your company enabled Calls on this phone. OCM becomes the phone\'s dialer: you call and answer as before, and calls are recorded in the company\'s call log (never the audio).';

  @override
  String get setDefaultDialer => 'Set as default Phone app';

  @override
  String get dialerFallback =>
      'The dialog did not appear or was dismissed. Choose OCM as the Phone app in settings.';

  @override
  String get callPermissionsTitle => 'Allow calls';

  @override
  String get callPermissionsBody =>
      'OCM needs these to place and answer calls, show your call history and who is calling.';

  @override
  String get fsiTitle => 'Show incoming calls';

  @override
  String get fsiBody =>
      'Allow OCM to show the incoming-call screen over the lock screen, so you can answer at once.';

  @override
  String get allowInSettings => 'Allow in settings';

  @override
  String get whyDialer =>
      'Android sends calls to one Phone app. Emergency calls always work, whatever happens to this app.';

  @override
  String get priorityHigh => 'High';

  @override
  String get priorityUrgent => 'Urgent';

  @override
  String callsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count calls',
      one: '1 call',
    );
    return '$_temp0';
  }

  @override
  String get wrongAppCode =>
      'This code is for OCM Messages. Open OCM Messages and scan it there, or ask for a code from Admin → Calls → Phones.';

  @override
  String get openKeypad => 'Open the keypad';

  @override
  String get choosePhoneApp => 'Choose another Phone app';

  @override
  String get enrollBanner =>
      'Calls on this phone are not recorded for your company yet.';

  @override
  String get enrollNow => 'Connect';

  @override
  String get notDefaultDialerBanner =>
      'This app is not your default Phone app. Incoming calls are not shown here.';

  @override
  String contactsWithNumbers(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count contacts with phone numbers',
      one: '1 contact with a phone number',
    );
    return '$_temp0';
  }

  @override
  String get allCalls => 'All calls';

  @override
  String get missedCalls => 'Missed calls';

  @override
  String get myProfile => 'My profile';
}
