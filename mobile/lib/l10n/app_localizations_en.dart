// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'Messages';

  @override
  String get companyApp => 'Communication Manager SMS';

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
  String get batteryTitle => 'Keep messages flowing';

  @override
  String get batteryBody =>
      'Some phones stop apps in the background. Turn off battery optimisation for this app so messages are never delayed.';

  @override
  String get batterySamsung =>
      'On Samsung: Settings → Battery → Background usage limits → Never sleeping apps → add Messages.';

  @override
  String get batteryOpen => 'Open battery settings';

  @override
  String get enrollTitle => 'Connect to your company';

  @override
  String get enrollBody =>
      'Scan the QR code your administrator shows you, or paste the enrollment code.';

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
      'Its connection to the company has been deleted. Your text messages are still on this phone.';

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
  String get queueWaiting => 'Admin messages waiting';

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
      'Messages on this company phone are copied to your company\'s Communication Manager. Authorised administrators can read them and send messages from this phone. All access is logged.';

  @override
  String get unlock => 'Unlock';

  @override
  String get locked => 'Messages is locked';

  @override
  String backfillProgress(int done, int total) {
    return 'Copying message history: $done of $total';
  }

  @override
  String get flashMessage => 'Flash message';

  @override
  String get startupErrorTitle => 'Messages could not start';

  @override
  String get startupErrorBody =>
      'Your text messages are safe on this phone. Try again; if this keeps happening, restart the phone or contact your administrator.';

  @override
  String get tryAgain => 'Try again';

  @override
  String get sendRefused =>
      'Message not sent. Check that Messages is the default SMS app and a SIM card is active, then try again.';
}
