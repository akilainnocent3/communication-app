// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Swahili (`sw`).
class AppLocalizationsSw extends AppLocalizations {
  AppLocalizationsSw([String locale = 'sw']) : super(locale);

  @override
  String get appTitle => 'OCM Ujumbe';

  @override
  String get companyApp => 'Communication Manager SMS';

  @override
  String get onboardingTitle => 'Fanya hii iwe programu ya SMS ya simu';

  @override
  String get onboardingBody =>
      'Ujumbe wa simu hii ya kampuni unasimamiwa na kampuni yako. Ili kupokea na kutuma SMS, programu hii lazima iwe programu chaguo-msingi ya SMS.';

  @override
  String get setDefault => 'Weka kama programu chaguo-msingi ya SMS';

  @override
  String get permissionsTitle => 'Ruhusu ufikiaji';

  @override
  String get permissionsBody =>
      'Programu inahitaji ruhusa hizi ili kupokea, kuhifadhi na kutuma ujumbe, kuonyesha anayekuandikia, na kukuarifu.';

  @override
  String get permissionSms => 'Ujumbe mfupi (kupokea, kusoma, kutuma)';

  @override
  String get permissionContacts => 'Anwani (majina ya wanaokuandikia)';

  @override
  String get permissionPhone => 'Simu na SIM (SIM inayotumika kwa ujumbe)';

  @override
  String get permissionNotifications => 'Arifa (ujumbe mpya)';

  @override
  String get grant => 'Ruhusu';

  @override
  String get continueLabel => 'Endelea';

  @override
  String get batteryTitle => 'Ujumbe usichelewe';

  @override
  String get batteryBody =>
      'Baadhi ya simu husimamisha programu zikiwa nyuma. Zima uboreshaji wa betri kwa programu hii ili ujumbe usichelewe kamwe.';

  @override
  String get batterySamsung =>
      'Kwenye Samsung: Mipangilio → Betri → Vikomo vya matumizi ya chinichini → Programu zisizolala kamwe → ongeza OCM.';

  @override
  String get batteryOpen => 'Fungua mipangilio ya betri';

  @override
  String get enrollTitle => 'Unganisha na kampuni yako';

  @override
  String get enrollBody =>
      'Changanua msimbo wa QR anaoonyesha msimamizi wako, gusa kiungo alichotuma, au andika msimbo wa herufi 8.';

  @override
  String get scanQr => 'Changanua msimbo wa QR';

  @override
  String get enterCode => 'Ingiza msimbo';

  @override
  String get codeLabel => 'Msimbo wa kuunganisha';

  @override
  String get serverLabel => 'Seva ya kampuni';

  @override
  String get untrustedServer =>
      'Msimbo huu wa QR unaelekeza kwenye seva ambayo programu hii hairuhusiwi kutumia. Muulize msimamizi wako.';

  @override
  String get noticeTitle => 'Taarifa ya ufuatiliaji';

  @override
  String get noticeAccept => 'Nimeelewa na ninakubali';

  @override
  String get noticeDecline => 'Si sasa';

  @override
  String get enrolling => 'Inaunganisha simu hii…';

  @override
  String enrolled(String code) {
    return 'Simu hii imeunganishwa kama $code.';
  }

  @override
  String get removedTitle => 'Simu hii imeondolewa na msimamizi wako';

  @override
  String get removedBody =>
      'Muunganisho wake na kampuni umefutwa. Ujumbe wako bado upo kwenye simu hii.';

  @override
  String get pausedBanner => 'Usawazishaji umesimamishwa na msimamizi wako.';

  @override
  String get notDefaultBanner =>
      'Programu hii si programu chaguo-msingi ya SMS. Ujumbe hauwezi kupokelewa wala kutumwa.';

  @override
  String get fixNow => 'Rekebisha';

  @override
  String get conversations => 'Ujumbe';

  @override
  String get archived => 'Kumbukumbu';

  @override
  String get spamBlocked => 'Taka na waliozuiwa';

  @override
  String get starred => 'Zenye nyota';

  @override
  String get searchHint => 'Tafuta mazungumzo';

  @override
  String get startChat => 'Anza mazungumzo';

  @override
  String get noConversations => 'Bado hakuna mazungumzo';

  @override
  String get noConversationsBody =>
      'Ujumbe unaotuma na kupokea utaonekana hapa.';

  @override
  String selectedCount(int count) {
    return '$count zimechaguliwa';
  }

  @override
  String get markRead => 'Weka kuwa umesomwa';

  @override
  String get markUnread => 'Weka kuwa haujasomwa';

  @override
  String get pin => 'Bandika';

  @override
  String get unpin => 'Bandua';

  @override
  String get mute => 'Nyamazisha';

  @override
  String get unmute => 'Washa sauti';

  @override
  String get archive => 'Weka kumbukumbu';

  @override
  String get unarchive => 'Ondoa kwenye kumbukumbu';

  @override
  String get delete => 'Futa';

  @override
  String get block => 'Zuia';

  @override
  String get unblock => 'Ondoa kizuizi';

  @override
  String get moveToSpam => 'Hamishia kwenye taka';

  @override
  String deleteConfirm(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'mazungumzo $count',
      one: 'mazungumzo haya',
    );
    return 'Futa $_temp0 kwenye simu hii?';
  }

  @override
  String get cancel => 'Ghairi';

  @override
  String get undo => 'Tendua';

  @override
  String get today => 'Leo';

  @override
  String get yesterday => 'Jana';

  @override
  String get messageHint => 'Ujumbe mfupi';

  @override
  String get send => 'Tuma';

  @override
  String segments(int segments, int remaining) {
    return 'SMS $segments · zimebaki $remaining';
  }

  @override
  String get mmsWillSend => 'Itatumwa kama MMS';

  @override
  String get sentByAdmin => 'Imetumwa na msimamizi';

  @override
  String sentByAdminNamed(String name) {
    return 'Imetumwa na msimamizi · $name';
  }

  @override
  String adminReplied(String name) {
    return 'Msimamizi amemjibu $name';
  }

  @override
  String get statusSending => 'Inatuma…';

  @override
  String get statusSent => 'Imetumwa';

  @override
  String get statusDelivered => 'Imefika';

  @override
  String get statusFailed => 'Haikutumwa. Gusa kujaribu tena';

  @override
  String get statusQueued => 'Kwenye foleni';

  @override
  String get copy => 'Nakili';

  @override
  String get copyCode => 'Nakili msimbo';

  @override
  String get codeCopied => 'Msimbo umenakiliwa';

  @override
  String get forward => 'Sambaza';

  @override
  String get share => 'Shiriki';

  @override
  String get star => 'Weka nyota';

  @override
  String get unstar => 'Ondoa nyota';

  @override
  String get details => 'Maelezo';

  @override
  String get detailsSent => 'Imetumwa';

  @override
  String get detailsReceived => 'Imepokelewa';

  @override
  String get detailsSim => 'SIM';

  @override
  String get detailsStatus => 'Hali';

  @override
  String get detailsFrom => 'Kutoka';

  @override
  String get toHint => 'Jina au namba';

  @override
  String get newConversation => 'Mazungumzo mapya';

  @override
  String get scheduleSend => 'Panga kutuma';

  @override
  String scheduledFor(String time) {
    return 'Imepangwa $time';
  }

  @override
  String get attach => 'Ambatisha';

  @override
  String get camera => 'Kamera';

  @override
  String get gallery => 'Picha';

  @override
  String get files => 'Faili';

  @override
  String get quickReplies => 'Majibu ya haraka';

  @override
  String get chooseSim => 'Chagua SIM';

  @override
  String get settings => 'Mipangilio';

  @override
  String get defaultSim => 'SIM chaguo-msingi';

  @override
  String get deliveryReports => 'Ripoti za kufika';

  @override
  String get mmsAutoDownload => 'Pakua MMS yenyewe';

  @override
  String get mmsWifiOnly => 'Wi-Fi pekee';

  @override
  String get mmsAlways => 'Kila mara';

  @override
  String get mmsNever => 'Kamwe';

  @override
  String get hideOnLockScreen =>
      'Ficha maandishi ya ujumbe kwenye skrini iliyofungwa';

  @override
  String get appLock => 'Funga kwa alama ya kidole au PIN';

  @override
  String get secureScreen => 'Zuia picha za skrini';

  @override
  String get textSize => 'Ukubwa wa maandishi';

  @override
  String get appearance => 'Mwonekano';

  @override
  String get syncStatus => 'Hali ya usawazishaji';

  @override
  String get syncNow => 'Sawazisha sasa';

  @override
  String get server => 'Seva';

  @override
  String get deviceCode => 'Msimbo wa kifaa';

  @override
  String get lastSync => 'Usawazishaji wa mwisho';

  @override
  String get pendingUploads => 'Zinasubiri kupakiwa';

  @override
  String get queueWaiting => 'Ujumbe wa msimamizi unaosubiri';

  @override
  String get connectivity => 'Muunganisho';

  @override
  String get online => 'Mtandaoni';

  @override
  String get offline => 'Nje ya mtandao';

  @override
  String get never => 'Bado';

  @override
  String get about => 'Kuhusu';

  @override
  String get aboutBody =>
      'Ujumbe kwenye simu hii ya kampuni unanakiliwa kwenye OCM ya kampuni yako. Wasimamizi walioidhinishwa wanaweza kuusoma na kutuma ujumbe kutoka simu hii. Kila ufikiaji unarekodiwa.';

  @override
  String get unlock => 'Fungua';

  @override
  String get locked => 'OCM imefungwa';

  @override
  String backfillProgress(int done, int total) {
    return 'Inanakili historia ya ujumbe: $done kati ya $total';
  }

  @override
  String get flashMessage => 'Ujumbe wa ghafla';

  @override
  String get startupErrorTitle => 'OCM haikuweza kuanza';

  @override
  String get startupErrorBody =>
      'Ujumbe wako uko salama kwenye simu hii. Jaribu tena; tatizo likiendelea, zima na uwashe simu au wasiliana na msimamizi wako.';

  @override
  String get tryAgain => 'Jaribu tena';

  @override
  String get sendRefused =>
      'Ujumbe haukutumwa. Hakikisha OCM Ujumbe ni programu chaguo-msingi ya SMS na SIM inafanya kazi, kisha ujaribu tena.';

  @override
  String unreadConversations(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Mazungumzo $count hayajasomwa',
      one: 'Mazungumzo 1 hayajasomwa',
    );
    return '$_temp0';
  }

  @override
  String get messagesSection => 'Ujumbe';

  @override
  String get moreResults => 'Matokeo zaidi';

  @override
  String get noResults => 'Hakuna matokeo';

  @override
  String get contacts => 'Anwani';

  @override
  String get selectText => 'Chagua maandishi';

  @override
  String get done => 'Imekamilika';

  @override
  String get appearanceHint =>
      'Mtindo, mandhari, ukubwa wa maandishi, kutelezesha';

  @override
  String get keepFlowingTitle => 'Ujumbe usichelewe';

  @override
  String get keepFlowingHint =>
      'Zuia simu isisimamishe programu hii ikiwa nyuma';

  @override
  String get keepFlowingBody =>
      'Simu huokoa betri kwa kusimamisha programu zilizo nyuma. Ruhusu programu hii ifanye kazi ili ujumbe wa wateja ufike kwa kampuni mara moja na majibu yatumwe kwa wakati.';

  @override
  String get style => 'Mtindo';

  @override
  String get matchMyPhone => 'Kama simu yangu';

  @override
  String get skinOneUi => 'Mtindo wa One UI';

  @override
  String get skinPixel => 'Mtindo wa Pixel / Material You';

  @override
  String get skinHios => 'Mtindo wa HiOS / XOS';

  @override
  String get skinHyperOs => 'Mtindo wa HyperOS / MIUI';

  @override
  String get skinColorOs => 'Mtindo wa ColorOS';

  @override
  String get skinCompany => 'Kampuni';

  @override
  String get theme => 'Mandhari';

  @override
  String get themeSystem => 'Kama mfumo';

  @override
  String get themeLight => 'Mwanga';

  @override
  String get themeDark => 'Giza';

  @override
  String get bubbleColour => 'Rangi ya kiputo';

  @override
  String get listDensity => 'Msongamano wa orodha';

  @override
  String get densityComfortable => 'Nafasi';

  @override
  String get densityCompact => 'Bana';

  @override
  String get swipeActions => 'Vitendo vya kutelezesha';

  @override
  String get swipeRight => 'Telezesha kulia';

  @override
  String get swipeLeft => 'Telezesha kushoto';

  @override
  String get none => 'Hakuna';

  @override
  String get showContactPhotos => 'Onyesha picha za anwani';

  @override
  String get checkBattery => 'Uboreshaji wa betri umezimwa kwa programu hii';

  @override
  String get checkBackground => 'Matumizi ya chinichini hayajazuiwa';

  @override
  String get checkStandby => 'Android haizuii programu';

  @override
  String get allow => 'Ruhusu';

  @override
  String get open => 'Fungua';

  @override
  String get oemSamsung =>
      'Samsung: ongeza kwenye \"Programu zisizolala kamwe\"';

  @override
  String get oemXiaomi => 'Xiaomi: ruhusu Kujianzisha (Autostart)';

  @override
  String get oemTranssion =>
      'Tecno / Infinix / itel: ruhusu kujianzisha kwenye Phone Master, na funga programu kwenye programu za hivi karibuni';

  @override
  String get oemOppo => 'Oppo / Realme: ruhusu kujianzisha';

  @override
  String get oemOneplus => 'OnePlus: ruhusu kujianzisha';

  @override
  String get oemHuawei =>
      'Huawei: simamia uanzishaji wa programu mwenyewe na ruhusu yote';

  @override
  String get oemCannotCheck =>
      'Simu haiambii programu kama hili limewashwa: liangalie mara moja.';

  @override
  String get forceStopWarning =>
      'Usitumie kamwe \"Lazimisha kusimama\" kwa programu hii: Android huzuia ujumbe wote unaoingia hadi programu ifunguliwe tena.';

  @override
  String get syncService => 'Huduma ya usawazishaji';

  @override
  String get running => 'Inafanya kazi';

  @override
  String get notRunning => 'Haifanyi kazi';

  @override
  String get welcomeTitle => 'OCM Ujumbe, programu ya ujumbe ya kampuni yako';

  @override
  String get welcomeBody =>
      'Tuma na upokee ujumbe kama kawaida. Kampuni yako inaona ujumbe wa simu hii ya kampuni na inaweza kukujibia.';

  @override
  String get getStarted => 'Anza';

  @override
  String get whyDefault =>
      'Android inaruhusu programu chaguo-msingi ya SMS pekee kupokea, kuhifadhi na kutuma ujumbe. Programu yako ya zamani ya Ujumbe inaendelea kufanya kazi kama programu ya kawaida.';

  @override
  String get roleFallback =>
      'Dirisha halikuonekana au lilifungwa. Chagua programu hii kwenye Mipangilio → Programu chaguo-msingi → Programu ya SMS.';

  @override
  String get openDefaultApps => 'Fungua Programu chaguo-msingi';

  @override
  String get whyPermissions =>
      'SMS: kusoma, kuhifadhi na kutuma ujumbe. Anwani: kuonyesha majina badala ya namba (majina hayapakiwi isipokuwa ya namba unazowasiliana nazo). Simu: kutumia SIM sahihi.';

  @override
  String get notificationsTitle => 'Jua ujumbe unapofika';

  @override
  String get whyNotifications =>
      'Ujumbe mpya, ujumbe usiotumwa na majibu ya msimamizi huonekana kama arifa. Maandishi yake yanafichwa kwenye skrini iliyofungwa.';

  @override
  String get notNow => 'Si sasa';

  @override
  String get whyFlowing =>
      'Bila hili baadhi ya simu husimamisha programu dakika chache baada ya skrini kuzima, na ujumbe hufika kwa kampuni saa kadhaa baadaye.';

  @override
  String get permissionDeniedForGood =>
      'Ruhusa imekataliwa. Iruhusu kwenye mipangilio ya programu.';

  @override
  String get openSettings => 'Fungua mipangilio';

  @override
  String get why => 'Kwa nini?';

  @override
  String get torch => 'Tochi';

  @override
  String get notAnEnrollCode =>
      'Huo si msimbo wa kuunganisha. Changanua msimbo kutoka Msimamizi → SMS → Unganisha simu.';

  @override
  String get noQrInPhoto => 'Hakuna msimbo wa QR kwenye picha hiyo.';

  @override
  String get pointAtQr => 'Elekeza kamera kwenye msimbo wa QR wa msimamizi';

  @override
  String get scanFromPhoto => 'Changanua kutoka picha';

  @override
  String get cameraRationale =>
      'Kamera inatumika kusoma msimbo wa QR wa msimamizi pekee. Hakuna kinachorekodiwa.';

  @override
  String get whyEnroll =>
      'Kuunganisha kunanakili ujumbe wa simu hii kwa kampuni yako ili wasimamizi wausome na kujibu. Utaona taarifa ya ufuatiliaji kabla ya chochote kuunganishwa.';

  @override
  String get orTypeCode => 'au andika msimbo';

  @override
  String get shortCodeLabel => 'Msimbo';

  @override
  String get noConnection =>
      'Hakuna muunganisho na seva. Angalia intaneti kisha ujaribu tena.';

  @override
  String get tooManyAttempts =>
      'Majaribio mengi mno. Subiri dakika chache kisha ujaribu tena.';

  @override
  String get enrolledTitle => 'Imeunganishwa';

  @override
  String get enrolledBody =>
      'Ujumbe sasa unafika kwa kampuni yako. Historia inanakiliwa chinichini.';

  @override
  String get openMessages => 'Fungua ujumbe';

  @override
  String get backfillDone => 'Historia ya ujumbe imenakiliwa';

  @override
  String backfillCopied(int count) {
    return 'Ujumbe $count umenakiliwa…';
  }
}
