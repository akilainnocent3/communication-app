import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_sw.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('sw'),
  ];

  /// No description provided for @appTitle.
  ///
  /// In en, this message translates to:
  /// **'Messages'**
  String get appTitle;

  /// No description provided for @companyApp.
  ///
  /// In en, this message translates to:
  /// **'Communication Manager SMS'**
  String get companyApp;

  /// No description provided for @onboardingTitle.
  ///
  /// In en, this message translates to:
  /// **'Make this the phone\'s SMS app'**
  String get onboardingTitle;

  /// No description provided for @onboardingBody.
  ///
  /// In en, this message translates to:
  /// **'This company phone\'s text messages are managed by your company. To receive and send SMS, this app must be the default SMS app.'**
  String get onboardingBody;

  /// No description provided for @setDefault.
  ///
  /// In en, this message translates to:
  /// **'Set as default SMS app'**
  String get setDefault;

  /// No description provided for @permissionsTitle.
  ///
  /// In en, this message translates to:
  /// **'Allow access'**
  String get permissionsTitle;

  /// No description provided for @permissionsBody.
  ///
  /// In en, this message translates to:
  /// **'The app needs these permissions to receive, store and send text messages, show who is writing, and notify you.'**
  String get permissionsBody;

  /// No description provided for @permissionSms.
  ///
  /// In en, this message translates to:
  /// **'Text messages (receive, read, send)'**
  String get permissionSms;

  /// No description provided for @permissionContacts.
  ///
  /// In en, this message translates to:
  /// **'Contacts (names of people who write to you)'**
  String get permissionContacts;

  /// No description provided for @permissionPhone.
  ///
  /// In en, this message translates to:
  /// **'Phone and SIM (which SIM a message uses)'**
  String get permissionPhone;

  /// No description provided for @permissionNotifications.
  ///
  /// In en, this message translates to:
  /// **'Notifications (new messages)'**
  String get permissionNotifications;

  /// No description provided for @grant.
  ///
  /// In en, this message translates to:
  /// **'Allow'**
  String get grant;

  /// No description provided for @continueLabel.
  ///
  /// In en, this message translates to:
  /// **'Continue'**
  String get continueLabel;

  /// No description provided for @batteryTitle.
  ///
  /// In en, this message translates to:
  /// **'Keep messages flowing'**
  String get batteryTitle;

  /// No description provided for @batteryBody.
  ///
  /// In en, this message translates to:
  /// **'Some phones stop apps in the background. Turn off battery optimisation for this app so messages are never delayed.'**
  String get batteryBody;

  /// No description provided for @batterySamsung.
  ///
  /// In en, this message translates to:
  /// **'On Samsung: Settings → Battery → Background usage limits → Never sleeping apps → add Messages.'**
  String get batterySamsung;

  /// No description provided for @batteryOpen.
  ///
  /// In en, this message translates to:
  /// **'Open battery settings'**
  String get batteryOpen;

  /// No description provided for @enrollTitle.
  ///
  /// In en, this message translates to:
  /// **'Connect to your company'**
  String get enrollTitle;

  /// No description provided for @enrollBody.
  ///
  /// In en, this message translates to:
  /// **'Scan the QR code your administrator shows you, tap the link they sent, or type the 8-character code.'**
  String get enrollBody;

  /// No description provided for @scanQr.
  ///
  /// In en, this message translates to:
  /// **'Scan QR code'**
  String get scanQr;

  /// No description provided for @enterCode.
  ///
  /// In en, this message translates to:
  /// **'Enter code'**
  String get enterCode;

  /// No description provided for @codeLabel.
  ///
  /// In en, this message translates to:
  /// **'Enrollment code'**
  String get codeLabel;

  /// No description provided for @serverLabel.
  ///
  /// In en, this message translates to:
  /// **'Company server'**
  String get serverLabel;

  /// No description provided for @untrustedServer.
  ///
  /// In en, this message translates to:
  /// **'This QR code points to a server this app is not allowed to use. Ask your administrator.'**
  String get untrustedServer;

  /// No description provided for @noticeTitle.
  ///
  /// In en, this message translates to:
  /// **'Monitoring notice'**
  String get noticeTitle;

  /// No description provided for @noticeAccept.
  ///
  /// In en, this message translates to:
  /// **'I understand and accept'**
  String get noticeAccept;

  /// No description provided for @noticeDecline.
  ///
  /// In en, this message translates to:
  /// **'Not now'**
  String get noticeDecline;

  /// No description provided for @enrolling.
  ///
  /// In en, this message translates to:
  /// **'Connecting this phone…'**
  String get enrolling;

  /// No description provided for @enrolled.
  ///
  /// In en, this message translates to:
  /// **'This phone is connected as {code}.'**
  String enrolled(String code);

  /// No description provided for @removedTitle.
  ///
  /// In en, this message translates to:
  /// **'This phone was removed by your administrator'**
  String get removedTitle;

  /// No description provided for @removedBody.
  ///
  /// In en, this message translates to:
  /// **'Its connection to the company has been deleted. Your text messages are still on this phone.'**
  String get removedBody;

  /// No description provided for @pausedBanner.
  ///
  /// In en, this message translates to:
  /// **'Syncing is paused by your administrator.'**
  String get pausedBanner;

  /// No description provided for @notDefaultBanner.
  ///
  /// In en, this message translates to:
  /// **'This app is not the default SMS app. Messages can\'t be received or sent.'**
  String get notDefaultBanner;

  /// No description provided for @fixNow.
  ///
  /// In en, this message translates to:
  /// **'Fix'**
  String get fixNow;

  /// No description provided for @conversations.
  ///
  /// In en, this message translates to:
  /// **'Messages'**
  String get conversations;

  /// No description provided for @archived.
  ///
  /// In en, this message translates to:
  /// **'Archived'**
  String get archived;

  /// No description provided for @spamBlocked.
  ///
  /// In en, this message translates to:
  /// **'Spam & blocked'**
  String get spamBlocked;

  /// No description provided for @starred.
  ///
  /// In en, this message translates to:
  /// **'Starred'**
  String get starred;

  /// No description provided for @searchHint.
  ///
  /// In en, this message translates to:
  /// **'Search conversations'**
  String get searchHint;

  /// No description provided for @startChat.
  ///
  /// In en, this message translates to:
  /// **'Start chat'**
  String get startChat;

  /// No description provided for @noConversations.
  ///
  /// In en, this message translates to:
  /// **'No conversations yet'**
  String get noConversations;

  /// No description provided for @noConversationsBody.
  ///
  /// In en, this message translates to:
  /// **'Text messages you send and receive appear here.'**
  String get noConversationsBody;

  /// No description provided for @selectedCount.
  ///
  /// In en, this message translates to:
  /// **'{count} selected'**
  String selectedCount(int count);

  /// No description provided for @markRead.
  ///
  /// In en, this message translates to:
  /// **'Mark as read'**
  String get markRead;

  /// No description provided for @markUnread.
  ///
  /// In en, this message translates to:
  /// **'Mark as unread'**
  String get markUnread;

  /// No description provided for @pin.
  ///
  /// In en, this message translates to:
  /// **'Pin'**
  String get pin;

  /// No description provided for @unpin.
  ///
  /// In en, this message translates to:
  /// **'Unpin'**
  String get unpin;

  /// No description provided for @mute.
  ///
  /// In en, this message translates to:
  /// **'Mute'**
  String get mute;

  /// No description provided for @unmute.
  ///
  /// In en, this message translates to:
  /// **'Unmute'**
  String get unmute;

  /// No description provided for @archive.
  ///
  /// In en, this message translates to:
  /// **'Archive'**
  String get archive;

  /// No description provided for @unarchive.
  ///
  /// In en, this message translates to:
  /// **'Unarchive'**
  String get unarchive;

  /// No description provided for @delete.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get delete;

  /// No description provided for @block.
  ///
  /// In en, this message translates to:
  /// **'Block'**
  String get block;

  /// No description provided for @unblock.
  ///
  /// In en, this message translates to:
  /// **'Unblock'**
  String get unblock;

  /// No description provided for @moveToSpam.
  ///
  /// In en, this message translates to:
  /// **'Move to spam'**
  String get moveToSpam;

  /// No description provided for @deleteConfirm.
  ///
  /// In en, this message translates to:
  /// **'Delete {count, plural, =1{this conversation} other{{count} conversations}} from this phone?'**
  String deleteConfirm(int count);

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @undo.
  ///
  /// In en, this message translates to:
  /// **'Undo'**
  String get undo;

  /// No description provided for @today.
  ///
  /// In en, this message translates to:
  /// **'Today'**
  String get today;

  /// No description provided for @yesterday.
  ///
  /// In en, this message translates to:
  /// **'Yesterday'**
  String get yesterday;

  /// No description provided for @messageHint.
  ///
  /// In en, this message translates to:
  /// **'Text message'**
  String get messageHint;

  /// No description provided for @send.
  ///
  /// In en, this message translates to:
  /// **'Send'**
  String get send;

  /// No description provided for @segments.
  ///
  /// In en, this message translates to:
  /// **'{segments} SMS · {remaining} left'**
  String segments(int segments, int remaining);

  /// No description provided for @mmsWillSend.
  ///
  /// In en, this message translates to:
  /// **'Sends as MMS'**
  String get mmsWillSend;

  /// No description provided for @sentByAdmin.
  ///
  /// In en, this message translates to:
  /// **'Sent by admin'**
  String get sentByAdmin;

  /// No description provided for @sentByAdminNamed.
  ///
  /// In en, this message translates to:
  /// **'Sent by admin · {name}'**
  String sentByAdminNamed(String name);

  /// No description provided for @adminReplied.
  ///
  /// In en, this message translates to:
  /// **'Admin replied to {name}'**
  String adminReplied(String name);

  /// No description provided for @statusSending.
  ///
  /// In en, this message translates to:
  /// **'Sending…'**
  String get statusSending;

  /// No description provided for @statusSent.
  ///
  /// In en, this message translates to:
  /// **'Sent'**
  String get statusSent;

  /// No description provided for @statusDelivered.
  ///
  /// In en, this message translates to:
  /// **'Delivered'**
  String get statusDelivered;

  /// No description provided for @statusFailed.
  ///
  /// In en, this message translates to:
  /// **'Not sent. Tap to retry'**
  String get statusFailed;

  /// No description provided for @statusQueued.
  ///
  /// In en, this message translates to:
  /// **'Queued'**
  String get statusQueued;

  /// No description provided for @copy.
  ///
  /// In en, this message translates to:
  /// **'Copy'**
  String get copy;

  /// No description provided for @copyCode.
  ///
  /// In en, this message translates to:
  /// **'Copy code'**
  String get copyCode;

  /// No description provided for @codeCopied.
  ///
  /// In en, this message translates to:
  /// **'Code copied'**
  String get codeCopied;

  /// No description provided for @forward.
  ///
  /// In en, this message translates to:
  /// **'Forward'**
  String get forward;

  /// No description provided for @share.
  ///
  /// In en, this message translates to:
  /// **'Share'**
  String get share;

  /// No description provided for @star.
  ///
  /// In en, this message translates to:
  /// **'Star'**
  String get star;

  /// No description provided for @unstar.
  ///
  /// In en, this message translates to:
  /// **'Unstar'**
  String get unstar;

  /// No description provided for @details.
  ///
  /// In en, this message translates to:
  /// **'Details'**
  String get details;

  /// No description provided for @detailsSent.
  ///
  /// In en, this message translates to:
  /// **'Sent'**
  String get detailsSent;

  /// No description provided for @detailsReceived.
  ///
  /// In en, this message translates to:
  /// **'Received'**
  String get detailsReceived;

  /// No description provided for @detailsSim.
  ///
  /// In en, this message translates to:
  /// **'SIM'**
  String get detailsSim;

  /// No description provided for @detailsStatus.
  ///
  /// In en, this message translates to:
  /// **'Status'**
  String get detailsStatus;

  /// No description provided for @detailsFrom.
  ///
  /// In en, this message translates to:
  /// **'From'**
  String get detailsFrom;

  /// No description provided for @toHint.
  ///
  /// In en, this message translates to:
  /// **'Name or number'**
  String get toHint;

  /// No description provided for @newConversation.
  ///
  /// In en, this message translates to:
  /// **'New conversation'**
  String get newConversation;

  /// No description provided for @scheduleSend.
  ///
  /// In en, this message translates to:
  /// **'Schedule send'**
  String get scheduleSend;

  /// No description provided for @scheduledFor.
  ///
  /// In en, this message translates to:
  /// **'Scheduled for {time}'**
  String scheduledFor(String time);

  /// No description provided for @attach.
  ///
  /// In en, this message translates to:
  /// **'Attach'**
  String get attach;

  /// No description provided for @camera.
  ///
  /// In en, this message translates to:
  /// **'Camera'**
  String get camera;

  /// No description provided for @gallery.
  ///
  /// In en, this message translates to:
  /// **'Gallery'**
  String get gallery;

  /// No description provided for @files.
  ///
  /// In en, this message translates to:
  /// **'Files'**
  String get files;

  /// No description provided for @quickReplies.
  ///
  /// In en, this message translates to:
  /// **'Quick replies'**
  String get quickReplies;

  /// No description provided for @chooseSim.
  ///
  /// In en, this message translates to:
  /// **'Choose SIM'**
  String get chooseSim;

  /// No description provided for @settings.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get settings;

  /// No description provided for @defaultSim.
  ///
  /// In en, this message translates to:
  /// **'Default SIM'**
  String get defaultSim;

  /// No description provided for @deliveryReports.
  ///
  /// In en, this message translates to:
  /// **'Delivery reports'**
  String get deliveryReports;

  /// No description provided for @mmsAutoDownload.
  ///
  /// In en, this message translates to:
  /// **'Auto-download MMS'**
  String get mmsAutoDownload;

  /// No description provided for @mmsWifiOnly.
  ///
  /// In en, this message translates to:
  /// **'Wi-Fi only'**
  String get mmsWifiOnly;

  /// No description provided for @mmsAlways.
  ///
  /// In en, this message translates to:
  /// **'Always'**
  String get mmsAlways;

  /// No description provided for @mmsNever.
  ///
  /// In en, this message translates to:
  /// **'Never'**
  String get mmsNever;

  /// No description provided for @hideOnLockScreen.
  ///
  /// In en, this message translates to:
  /// **'Hide message text on the lock screen'**
  String get hideOnLockScreen;

  /// No description provided for @appLock.
  ///
  /// In en, this message translates to:
  /// **'Lock with fingerprint or PIN'**
  String get appLock;

  /// No description provided for @secureScreen.
  ///
  /// In en, this message translates to:
  /// **'Block screenshots'**
  String get secureScreen;

  /// No description provided for @textSize.
  ///
  /// In en, this message translates to:
  /// **'Text size'**
  String get textSize;

  /// No description provided for @appearance.
  ///
  /// In en, this message translates to:
  /// **'Appearance'**
  String get appearance;

  /// No description provided for @syncStatus.
  ///
  /// In en, this message translates to:
  /// **'Sync status'**
  String get syncStatus;

  /// No description provided for @syncNow.
  ///
  /// In en, this message translates to:
  /// **'Sync now'**
  String get syncNow;

  /// No description provided for @server.
  ///
  /// In en, this message translates to:
  /// **'Server'**
  String get server;

  /// No description provided for @deviceCode.
  ///
  /// In en, this message translates to:
  /// **'Device code'**
  String get deviceCode;

  /// No description provided for @lastSync.
  ///
  /// In en, this message translates to:
  /// **'Last sync'**
  String get lastSync;

  /// No description provided for @pendingUploads.
  ///
  /// In en, this message translates to:
  /// **'Waiting to upload'**
  String get pendingUploads;

  /// No description provided for @queueWaiting.
  ///
  /// In en, this message translates to:
  /// **'Admin messages waiting'**
  String get queueWaiting;

  /// No description provided for @connectivity.
  ///
  /// In en, this message translates to:
  /// **'Connection'**
  String get connectivity;

  /// No description provided for @online.
  ///
  /// In en, this message translates to:
  /// **'Online'**
  String get online;

  /// No description provided for @offline.
  ///
  /// In en, this message translates to:
  /// **'Offline'**
  String get offline;

  /// No description provided for @never.
  ///
  /// In en, this message translates to:
  /// **'Never'**
  String get never;

  /// No description provided for @about.
  ///
  /// In en, this message translates to:
  /// **'About'**
  String get about;

  /// No description provided for @aboutBody.
  ///
  /// In en, this message translates to:
  /// **'Messages on this company phone are copied to your company\'s Communication Manager. Authorised administrators can read them and send messages from this phone. All access is logged.'**
  String get aboutBody;

  /// No description provided for @unlock.
  ///
  /// In en, this message translates to:
  /// **'Unlock'**
  String get unlock;

  /// No description provided for @locked.
  ///
  /// In en, this message translates to:
  /// **'Messages is locked'**
  String get locked;

  /// No description provided for @backfillProgress.
  ///
  /// In en, this message translates to:
  /// **'Copying message history: {done} of {total}'**
  String backfillProgress(int done, int total);

  /// No description provided for @flashMessage.
  ///
  /// In en, this message translates to:
  /// **'Flash message'**
  String get flashMessage;

  /// No description provided for @startupErrorTitle.
  ///
  /// In en, this message translates to:
  /// **'Messages could not start'**
  String get startupErrorTitle;

  /// No description provided for @startupErrorBody.
  ///
  /// In en, this message translates to:
  /// **'Your text messages are safe on this phone. Try again; if this keeps happening, restart the phone or contact your administrator.'**
  String get startupErrorBody;

  /// No description provided for @tryAgain.
  ///
  /// In en, this message translates to:
  /// **'Try again'**
  String get tryAgain;

  /// No description provided for @sendRefused.
  ///
  /// In en, this message translates to:
  /// **'Message not sent. Check that Messages is the default SMS app and a SIM card is active, then try again.'**
  String get sendRefused;

  /// No description provided for @unreadConversations.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 unread conversation} other{{count} unread conversations}}'**
  String unreadConversations(int count);

  /// No description provided for @messagesSection.
  ///
  /// In en, this message translates to:
  /// **'Messages'**
  String get messagesSection;

  /// No description provided for @moreResults.
  ///
  /// In en, this message translates to:
  /// **'More results'**
  String get moreResults;

  /// No description provided for @noResults.
  ///
  /// In en, this message translates to:
  /// **'No results'**
  String get noResults;

  /// No description provided for @contacts.
  ///
  /// In en, this message translates to:
  /// **'Contacts'**
  String get contacts;

  /// No description provided for @selectText.
  ///
  /// In en, this message translates to:
  /// **'Select text'**
  String get selectText;

  /// No description provided for @done.
  ///
  /// In en, this message translates to:
  /// **'Done'**
  String get done;

  /// No description provided for @appearanceHint.
  ///
  /// In en, this message translates to:
  /// **'Style, theme, text size, swipe actions'**
  String get appearanceHint;

  /// No description provided for @keepFlowingTitle.
  ///
  /// In en, this message translates to:
  /// **'Keep messages flowing'**
  String get keepFlowingTitle;

  /// No description provided for @keepFlowingHint.
  ///
  /// In en, this message translates to:
  /// **'Stop the phone from pausing this app in the background'**
  String get keepFlowingHint;

  /// No description provided for @keepFlowingBody.
  ///
  /// In en, this message translates to:
  /// **'Phones save battery by pausing apps in the background. Allow this app to run so customer messages reach your company at once and replies go out on time.'**
  String get keepFlowingBody;

  /// No description provided for @style.
  ///
  /// In en, this message translates to:
  /// **'Style'**
  String get style;

  /// No description provided for @matchMyPhone.
  ///
  /// In en, this message translates to:
  /// **'Match my phone'**
  String get matchMyPhone;

  /// No description provided for @skinOneUi.
  ///
  /// In en, this message translates to:
  /// **'One UI style'**
  String get skinOneUi;

  /// No description provided for @skinPixel.
  ///
  /// In en, this message translates to:
  /// **'Pixel / Material You style'**
  String get skinPixel;

  /// No description provided for @skinHios.
  ///
  /// In en, this message translates to:
  /// **'HiOS / XOS style'**
  String get skinHios;

  /// No description provided for @skinHyperOs.
  ///
  /// In en, this message translates to:
  /// **'HyperOS / MIUI style'**
  String get skinHyperOs;

  /// No description provided for @skinColorOs.
  ///
  /// In en, this message translates to:
  /// **'ColorOS style'**
  String get skinColorOs;

  /// No description provided for @skinCompany.
  ///
  /// In en, this message translates to:
  /// **'Company'**
  String get skinCompany;

  /// No description provided for @theme.
  ///
  /// In en, this message translates to:
  /// **'Theme'**
  String get theme;

  /// No description provided for @themeSystem.
  ///
  /// In en, this message translates to:
  /// **'System'**
  String get themeSystem;

  /// No description provided for @themeLight.
  ///
  /// In en, this message translates to:
  /// **'Light'**
  String get themeLight;

  /// No description provided for @themeDark.
  ///
  /// In en, this message translates to:
  /// **'Dark'**
  String get themeDark;

  /// No description provided for @bubbleColour.
  ///
  /// In en, this message translates to:
  /// **'Bubble colour'**
  String get bubbleColour;

  /// No description provided for @listDensity.
  ///
  /// In en, this message translates to:
  /// **'List density'**
  String get listDensity;

  /// No description provided for @densityComfortable.
  ///
  /// In en, this message translates to:
  /// **'Comfortable'**
  String get densityComfortable;

  /// No description provided for @densityCompact.
  ///
  /// In en, this message translates to:
  /// **'Compact'**
  String get densityCompact;

  /// No description provided for @swipeActions.
  ///
  /// In en, this message translates to:
  /// **'Swipe actions'**
  String get swipeActions;

  /// No description provided for @swipeRight.
  ///
  /// In en, this message translates to:
  /// **'Swipe right'**
  String get swipeRight;

  /// No description provided for @swipeLeft.
  ///
  /// In en, this message translates to:
  /// **'Swipe left'**
  String get swipeLeft;

  /// No description provided for @none.
  ///
  /// In en, this message translates to:
  /// **'None'**
  String get none;

  /// No description provided for @showContactPhotos.
  ///
  /// In en, this message translates to:
  /// **'Show contact photos'**
  String get showContactPhotos;

  /// No description provided for @checkBattery.
  ///
  /// In en, this message translates to:
  /// **'Battery optimisation is off for this app'**
  String get checkBattery;

  /// No description provided for @checkBackground.
  ///
  /// In en, this message translates to:
  /// **'Background use is not restricted'**
  String get checkBackground;

  /// No description provided for @checkStandby.
  ///
  /// In en, this message translates to:
  /// **'Android is not holding the app back'**
  String get checkStandby;

  /// No description provided for @allow.
  ///
  /// In en, this message translates to:
  /// **'Allow'**
  String get allow;

  /// No description provided for @open.
  ///
  /// In en, this message translates to:
  /// **'Open'**
  String get open;

  /// No description provided for @oemSamsung.
  ///
  /// In en, this message translates to:
  /// **'Samsung: add to \"Never sleeping apps\"'**
  String get oemSamsung;

  /// No description provided for @oemXiaomi.
  ///
  /// In en, this message translates to:
  /// **'Xiaomi: allow Autostart'**
  String get oemXiaomi;

  /// No description provided for @oemTranssion.
  ///
  /// In en, this message translates to:
  /// **'Tecno / Infinix / itel: allow auto-start in Phone Master, and lock the app in recent apps'**
  String get oemTranssion;

  /// No description provided for @oemOppo.
  ///
  /// In en, this message translates to:
  /// **'Oppo / Realme: allow auto-launch'**
  String get oemOppo;

  /// No description provided for @oemOneplus.
  ///
  /// In en, this message translates to:
  /// **'OnePlus: allow auto-launch'**
  String get oemOneplus;

  /// No description provided for @oemHuawei.
  ///
  /// In en, this message translates to:
  /// **'Huawei: manage app launch manually and allow all'**
  String get oemHuawei;

  /// No description provided for @oemCannotCheck.
  ///
  /// In en, this message translates to:
  /// **'The phone does not tell apps whether this is on: check it once.'**
  String get oemCannotCheck;

  /// No description provided for @forceStopWarning.
  ///
  /// In en, this message translates to:
  /// **'Never use \"Force stop\" on this app: Android then blocks all incoming messages for it until it is opened again.'**
  String get forceStopWarning;

  /// No description provided for @syncService.
  ///
  /// In en, this message translates to:
  /// **'Sync service'**
  String get syncService;

  /// No description provided for @running.
  ///
  /// In en, this message translates to:
  /// **'Running'**
  String get running;

  /// No description provided for @notRunning.
  ///
  /// In en, this message translates to:
  /// **'Not running'**
  String get notRunning;

  /// No description provided for @welcomeTitle.
  ///
  /// In en, this message translates to:
  /// **'Your company Messages app'**
  String get welcomeTitle;

  /// No description provided for @welcomeBody.
  ///
  /// In en, this message translates to:
  /// **'Send and receive text messages as usual. Your company sees the messages of this company phone and can reply for you.'**
  String get welcomeBody;

  /// No description provided for @getStarted.
  ///
  /// In en, this message translates to:
  /// **'Get started'**
  String get getStarted;

  /// No description provided for @whyDefault.
  ///
  /// In en, this message translates to:
  /// **'Android lets only the default SMS app receive messages, save them and send them. Your old Messages app keeps working as a normal app.'**
  String get whyDefault;

  /// No description provided for @roleFallback.
  ///
  /// In en, this message translates to:
  /// **'The dialog did not appear or was closed. Choose this app in Settings → Default apps → SMS app.'**
  String get roleFallback;

  /// No description provided for @openDefaultApps.
  ///
  /// In en, this message translates to:
  /// **'Open Default apps'**
  String get openDefaultApps;

  /// No description provided for @whyPermissions.
  ///
  /// In en, this message translates to:
  /// **'SMS: to read, save and send messages. Contacts: to show names instead of numbers (names are never uploaded except for numbers you message). Phone: to use the right SIM.'**
  String get whyPermissions;

  /// No description provided for @notificationsTitle.
  ///
  /// In en, this message translates to:
  /// **'Know when messages arrive'**
  String get notificationsTitle;

  /// No description provided for @whyNotifications.
  ///
  /// In en, this message translates to:
  /// **'New messages, failed sends and admin replies show as notifications. Their text is hidden on the lock screen.'**
  String get whyNotifications;

  /// No description provided for @notNow.
  ///
  /// In en, this message translates to:
  /// **'Not now'**
  String get notNow;

  /// No description provided for @whyFlowing.
  ///
  /// In en, this message translates to:
  /// **'Without this some phones stop the app minutes after the screen turns off, and messages reach your company hours late.'**
  String get whyFlowing;

  /// No description provided for @permissionDeniedForGood.
  ///
  /// In en, this message translates to:
  /// **'Permission was refused. Allow it in the app settings.'**
  String get permissionDeniedForGood;

  /// No description provided for @openSettings.
  ///
  /// In en, this message translates to:
  /// **'Open settings'**
  String get openSettings;

  /// No description provided for @why.
  ///
  /// In en, this message translates to:
  /// **'Why?'**
  String get why;

  /// No description provided for @torch.
  ///
  /// In en, this message translates to:
  /// **'Torch'**
  String get torch;

  /// No description provided for @notAnEnrollCode.
  ///
  /// In en, this message translates to:
  /// **'That is not an enrollment code. Scan the code from Admin → SMS → Enroll phone.'**
  String get notAnEnrollCode;

  /// No description provided for @noQrInPhoto.
  ///
  /// In en, this message translates to:
  /// **'No QR code found in that photo.'**
  String get noQrInPhoto;

  /// No description provided for @pointAtQr.
  ///
  /// In en, this message translates to:
  /// **'Point the camera at the administrator\'s QR code'**
  String get pointAtQr;

  /// No description provided for @scanFromPhoto.
  ///
  /// In en, this message translates to:
  /// **'Scan from photo'**
  String get scanFromPhoto;

  /// No description provided for @cameraRationale.
  ///
  /// In en, this message translates to:
  /// **'The camera is used only to read your administrator\'s QR code. Nothing is recorded.'**
  String get cameraRationale;

  /// No description provided for @whyEnroll.
  ///
  /// In en, this message translates to:
  /// **'Connecting copies this phone\'s messages to your company so administrators can read and reply. You will see the monitoring notice before anything is connected.'**
  String get whyEnroll;

  /// No description provided for @orTypeCode.
  ///
  /// In en, this message translates to:
  /// **'or type the code'**
  String get orTypeCode;

  /// No description provided for @shortCodeLabel.
  ///
  /// In en, this message translates to:
  /// **'Code'**
  String get shortCodeLabel;

  /// No description provided for @noConnection.
  ///
  /// In en, this message translates to:
  /// **'No connection to the server. Check the internet and try again.'**
  String get noConnection;

  /// No description provided for @tooManyAttempts.
  ///
  /// In en, this message translates to:
  /// **'Too many attempts. Wait a few minutes and try again.'**
  String get tooManyAttempts;

  /// No description provided for @enrolledTitle.
  ///
  /// In en, this message translates to:
  /// **'Connected'**
  String get enrolledTitle;

  /// No description provided for @enrolledBody.
  ///
  /// In en, this message translates to:
  /// **'Messages now reach your company. The history is being copied in the background.'**
  String get enrolledBody;

  /// No description provided for @openMessages.
  ///
  /// In en, this message translates to:
  /// **'Open messages'**
  String get openMessages;

  /// No description provided for @backfillDone.
  ///
  /// In en, this message translates to:
  /// **'Message history copied'**
  String get backfillDone;

  /// No description provided for @backfillCopied.
  ///
  /// In en, this message translates to:
  /// **'{count} messages copied…'**
  String backfillCopied(int count);
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'sw'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'sw':
      return AppLocalizationsSw();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
