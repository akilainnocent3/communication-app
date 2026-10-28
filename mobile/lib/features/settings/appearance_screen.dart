import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../l10n/app_localizations.dart';
import '../../providers.dart';
import '../../ui/skin/skin.dart';
import '../../ui/skin/tokens.dart';
import '../../ui/widgets/skin_preview.dart';

/// Settings → Appearance. Every change applies at once (the theme is rebuilt from the settings), no restart.
class AppearanceScreen extends ConsumerWidget {
  const AppearanceScreen({super.key});

  static const bubbleColours = ['', 'FF3E7BFA', 'FF1A73E8', 'FF22A35A', 'FF0F766E', 'FF8E44AD', 'FFE8590C', 'FF3C4043'];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final values = ref.watch(settingsProvider);
    final settings = ref.read(settingsProvider.notifier);
    final startup = ref.watch(servicesProvider).startup;
    final chosen = values['skin'] ?? 'auto';
    final brightness = Theme.of(context).brightness;
    String skinName(String id) => switch (id) {
      'one_ui' => l10n.skinOneUi,
      'pixel' => l10n.skinPixel,
      'hios' => l10n.skinHios,
      'hyper_os' => l10n.skinHyperOs,
      'color_os' => l10n.skinColorOs,
      _ => l10n.skinCompany,
    };
    final matched = skinForPhone(startup.manufacturer, startup.brand);
    final scale = ref.watch(textScaleProvider);
    String swipeName(SwipeAction a) => switch (a) {
      SwipeAction.archive => l10n.archive,
      SwipeAction.delete => l10n.delete,
      SwipeAction.read => l10n.markRead,
      SwipeAction.none => l10n.none,
    };
    final tokens = SkinTokens.of(context);

    Widget option(String id, String label) {
      final spec = skinById(id == 'auto' ? matched : id);
      return Padding(
        padding: const EdgeInsets.fromLTRB(16, 6, 16, 6),
        child: Material(
          color: Theme.of(context).colorScheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(16),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: () => settings.set('skin', id),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                RadioListTile<String>(value: id, title: Text(label)),
                // A live preview: a list row and two bubbles in that skin's own theme.
                Theme(data: buildSkinTheme(spec, brightness), child: const SkinPreview()),
              ],
            ),
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: Text(l10n.appearance)),
      body: RadioGroup<String>(
        groupValue: chosen,
        onChanged: (v) => settings.set('skin', v ?? 'auto'),
        child: ListView(
          padding: const EdgeInsets.only(bottom: 32),
          children: [
            _Heading(l10n.style),
            option('auto', '${l10n.matchMyPhone} (${skinName(matched)})'),
            for (final spec in skins) option(spec.id, skinName(spec.id)),
            _Heading(l10n.theme),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: SegmentedButton<String>(
                segments: [
                  ButtonSegment(value: 'system', label: Text(l10n.themeSystem)),
                  ButtonSegment(value: 'light', label: Text(l10n.themeLight)),
                  ButtonSegment(value: 'dark', label: Text(l10n.themeDark)),
                ],
                selected: {values['theme_mode'] ?? 'system'},
                onSelectionChanged: (v) => settings.set('theme_mode', v.first),
              ),
            ),
            _Heading(l10n.bubbleColour),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  for (final hex in bubbleColours)
                    InkWell(
                      customBorder: const CircleBorder(),
                      onTap: () => settings.set('bubble_colour', hex),
                      child: Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: hex.isEmpty ? tokens.outgoing : Color(int.parse(hex, radix: 16)),
                          border: Border.all(width: (values['bubble_colour'] ?? '') == hex ? 3 : 1, color: Theme.of(context).colorScheme.onSurface),
                        ),
                        child: hex.isEmpty ? Icon(Icons.auto_awesome, size: 18, color: tokens.onOutgoing) : null,
                      ),
                    ),
                ],
              ),
            ),
            _Heading(l10n.textSize),
            Slider(min: 0.85, max: 1.4, divisions: 11, value: scale, label: '${(scale * 100).round()}%', onChanged: (v) => settings.set('text_scale', v.toStringAsFixed(2))),
            _Heading(l10n.listDensity),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: SegmentedButton<String>(
                segments: [
                  ButtonSegment(value: 'comfortable', label: Text(l10n.densityComfortable)),
                  ButtonSegment(value: 'compact', label: Text(l10n.densityCompact)),
                ],
                selected: {values['density'] == 'compact' ? 'compact' : 'comfortable'},
                onSelectionChanged: (v) => settings.set('density', v.first),
              ),
            ),
            _Heading(l10n.swipeActions),
            for (final (key, label, current) in [('swipe_right', l10n.swipeRight, tokens.swipeRight), ('swipe_left', l10n.swipeLeft, tokens.swipeLeft)])
              ListTile(
                title: Text(label),
                trailing: DropdownButton<SwipeAction>(
                  value: current,
                  items: [for (final a in SwipeAction.values) DropdownMenuItem(value: a, child: Text(swipeName(a)))],
                  onChanged: (a) => settings.set(key, a?.name ?? ''),
                ),
              ),
            SwitchListTile(title: Text(l10n.showContactPhotos), value: values['show_photos'] != '0', onChanged: (v) => settings.set('show_photos', v ? '1' : '0')),
          ],
        ),
      ),
    );
  }
}

class _Heading extends StatelessWidget {
  const _Heading(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
    child: Text(text, style: Theme.of(context).textTheme.titleSmall?.copyWith(color: Theme.of(context).colorScheme.primary)),
  );
}
