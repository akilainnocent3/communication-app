import '../../platform/telephony_api.g.dart';

/// The Phone screens' view of the native dialer (Pigeon). Tests use a fake.
abstract class DialerGateway {
  Future<CallsStatus> status();
  Future<String> placeCall(String number, {int? subscriptionId, String origin = 'manual', String? callbackTask});
  Future<List<RecentCall>> recent(int limit, int offset);
  Future<List<PhoneContact>> contacts(int limit);
  /// The owner's own card (Contacts → My profile), null when none.
  Future<PhoneContact?> myProfile();
  Future<void> openProfile();
  Future<List<CallbackTaskData>> callbacks();
  Future<void> reportCallback(String id, String state);
  Future<void> deleteRecent(int id);
  Future<List<SimInfo>> sims();
  Future<void> addContact(String number);
  /// Opens the phone's SMS app (OCM Messages on company phones) to write to [number].
  Future<void> message(String number);
  /// The keypad's tone for [key], when the phone's "Dial pad tones" setting is on.
  Future<void> dialTone(String key);
}

class PlatformDialerGateway implements DialerGateway {
  PlatformDialerGateway(this.api);
  final TelephonyHostApi api;

  @override
  Future<CallsStatus> status() => api.callsStatus();
  @override
  Future<String> placeCall(String number, {int? subscriptionId, String origin = 'manual', String? callbackTask}) => api.placeCall(number, subscriptionId, origin, callbackTask);
  @override
  Future<List<RecentCall>> recent(int limit, int offset) => api.recentCalls(limit, offset);
  @override
  Future<List<PhoneContact>> contacts(int limit) => api.phoneContacts(limit);
  @override
  Future<PhoneContact?> myProfile() => api.myProfile();
  @override
  Future<void> openProfile() => api.openProfile();
  @override
  Future<List<CallbackTaskData>> callbacks() => api.callbackTasks();
  @override
  Future<void> reportCallback(String id, String state) => api.reportCallback(id, state);
  @override
  Future<void> deleteRecent(int id) => api.deleteRecentCall(id);
  @override
  Future<List<SimInfo>> sims() => api.sims();
  @override
  Future<void> addContact(String number) => api.addContact(number);
  @override
  Future<void> message(String number) => api.messageNumber(number);
  @override
  Future<void> dialTone(String key) => api.playDialTone(key);
}
