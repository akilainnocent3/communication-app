import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';

import '../../core/text/otp.dart';
import '../../l10n/app_localizations.dart';
import '../../platform/telephony_api.g.dart';
import '../../ui/skin/tokens.dart';
import '../../ui/widgets/avatar.dart';

String statusText(AppLocalizations l10n, String status) => switch (status) {
      'sending' || 'queued' => l10n.statusSending,
      'sent' => l10n.statusSent,
      'delivered' => l10n.statusDelivered,
      'failed' => l10n.statusFailed,
      _ => '',
    };

/// One message in the skin's colours and shape. Admin-origin messages have their own colour and "Sent by admin ·
/// Name"; one-time codes get a "Copy code" chip; MMS images and videos show inline as small thumbnails. Plain Text
/// (selection is an action in the long-press sheet: a SelectableText per bubble made every bubble a text field).
/// Links are shown as text: automatic previews would leak them to third parties.
class MessageBubble extends StatelessWidget {
  const MessageBubble({super.key, required this.message, this.adminName, this.isAdmin = false, this.starred = false, required this.onLongPress, this.onRetry, this.onOpenImage});
  final ProviderMessage message;
  final bool isAdmin;
  final String? adminName;
  final bool starred;
  final VoidCallback onLongPress;
  final VoidCallback? onRetry;
  final void Function(MmsPartData part)? onOpenImage;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final tokens = SkinTokens.of(context);
    final scheme = Theme.of(context).colorScheme;
    final out = message.outbound;
    final background = !out ? tokens.incoming : isAdmin ? tokens.admin : tokens.outgoing;
    final foreground = !out ? tokens.onIncoming : isAdmin ? tokens.onAdmin : tokens.onOutgoing;
    final otp = out ? null : extractOtp(message.body);
    final time = DateFormat.Hm(Localizations.localeOf(context).toString()).format(DateTime.fromMillisecondsSinceEpoch(message.date));
    final media = message.parts.where((p) => p.uri != null && (p.contentType.startsWith('image/') || p.contentType.startsWith('video/'))).toList();
    final big = Radius.circular(tokens.bubbleRadius);
    final tail = Radius.circular(tokens.tailRadius);
    final px = (240 * MediaQuery.devicePixelRatioOf(context)).round();
    return Column(
      crossAxisAlignment: out ? CrossAxisAlignment.end : CrossAxisAlignment.start,
      children: [
        if (isAdmin)
          Padding(
            padding: const EdgeInsets.only(right: 8, bottom: 2),
            child: Text(adminName == null || adminName!.isEmpty ? l10n.sentByAdmin : l10n.sentByAdminNamed(adminName!), style: TextStyle(fontSize: 11, color: tokens.admin)),
          ),
        GestureDetector(
          onLongPress: () {
            HapticFeedback.mediumImpact();
            onLongPress();
          },
          onTap: message.status == 'failed' ? onRetry : null,
          child: Semantics(
            label: '${out ? (isAdmin ? l10n.sentByAdmin : l10n.detailsSent) : l10n.detailsReceived}, $time',
            child: Container(
              constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * tokens.bubbleMaxWidth),
              padding: EdgeInsets.symmetric(horizontal: media.isNotEmpty && message.body.isEmpty ? 4 : 14, vertical: media.isNotEmpty && message.body.isEmpty ? 4 : 9),
              decoration: BoxDecoration(
                color: background,
                borderRadius: BorderRadius.only(topLeft: big, topRight: big, bottomLeft: out ? big : tail, bottomRight: out ? tail : big),
                border: message.status == 'failed' ? Border.all(color: scheme.error, width: 1.5) : null,
              ),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                for (final part in media)
                  Padding(
                    padding: EdgeInsets.only(bottom: message.body.isEmpty ? 0 : 6),
                    child: GestureDetector(
                      onTap: onOpenImage == null ? null : () => onOpenImage!(part),
                      // Its own layer: a decoded image never repaints with the text around it.
                      child: RepaintBoundary(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(tokens.bubbleRadius - 4),
                          child: Stack(alignment: Alignment.center, children: [
                            ThumbnailImage(
                              uri: part.uri!, px: px, fit: BoxFit.contain,
                              placeholder: Container(width: 240, height: 160, color: foreground.withValues(alpha: 0.08), child: Icon(Icons.image_outlined, color: foreground)),
                            ),
                            if (part.contentType.startsWith('video/')) const Icon(Icons.play_circle_fill, size: 48, color: Colors.white70),
                          ]),
                        ),
                      ),
                    ),
                  ),
                if (message.body.isNotEmpty) Text(message.body, style: TextStyle(color: foreground, fontSize: 15.5, height: 1.3)),
              ]),
            ),
          ),
        ),
        if (otp != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: ActionChip(
              avatar: const Icon(Icons.copy, size: 16), label: Text('${l10n.copyCode} $otp'),
              onPressed: () {
                Clipboard.setData(ClipboardData(text: otp));
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(l10n.codeCopied)));
              },
            ),
          ),
        Padding(
          padding: const EdgeInsets.only(top: 2, left: 4, right: 4),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            if (starred) const Icon(Icons.star, size: 12, color: Colors.amber),
            Text(time, style: Theme.of(context).textTheme.labelSmall?.copyWith(color: scheme.onSurfaceVariant)),
            if (out) ...[
              const SizedBox(width: 4),
              Text(statusText(l10n, message.status), style: Theme.of(context).textTheme.labelSmall?.copyWith(color: message.status == 'failed' ? scheme.error : scheme.onSurfaceVariant)),
            ],
          ]),
        ),
      ],
    );
  }
}
