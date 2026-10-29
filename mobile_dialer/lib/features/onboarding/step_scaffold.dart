import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';

class StepAction {
  const StepAction(this.label, this.onPressed);
  final String label;
  final VoidCallback onPressed;
}

/// One onboarding/enrollment step: a light vector illustration, one title, one sentence, an optional "Why?", a clear
/// done state, the main action at the bottom (in thumb reach) and progress dots.
class StepScaffold extends StatefulWidget {
  const StepScaffold({
    super.key, required this.index, required this.total, required this.illustration, required this.title, required this.body, required this.primary,
    this.secondary, this.why, this.done = false, this.extra,
  });
  final int index;
  final int total;
  final Widget illustration;
  final String title;
  final String body;
  final StepAction primary;
  final StepAction? secondary;
  final String? why;
  final bool done;
  final Widget? extra;

  @override
  State<StepScaffold> createState() => _StepScaffoldState();
}

class _StepScaffoldState extends State<StepScaffold> {
  bool _why = false;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: Column(children: [
          Expanded(
            child: ListView(padding: const EdgeInsets.fromLTRB(24, 32, 24, 16), children: [
              Center(child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 250),
                child: widget.done ? const StepIllustration(key: ValueKey('done'), icon: Icons.check_rounded, done: true) : widget.illustration,
              )),
              const SizedBox(height: 28),
              Text(widget.title, textAlign: TextAlign.center, style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w600)),
              if (widget.body.isNotEmpty) ...[
                const SizedBox(height: 12),
                Text(widget.body, textAlign: TextAlign.center, style: theme.textTheme.bodyLarge?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
              ],
              if (widget.why != null)
                Center(child: TextButton.icon(
                  onPressed: () => setState(() => _why = !_why),
                  icon: Icon(_why ? Icons.expand_less : Icons.help_outline, size: 18),
                  label: Text(l10n.why),
                )),
              AnimatedCrossFade(
                duration: const Duration(milliseconds: 200),
                crossFadeState: _why ? CrossFadeState.showSecond : CrossFadeState.showFirst,
                firstChild: const SizedBox(width: double.infinity),
                secondChild: Card(child: Padding(padding: const EdgeInsets.all(16), child: Text(widget.why ?? ''))),
              ),
              if (widget.extra != null) Padding(padding: const EdgeInsets.only(top: 12), child: widget.extra),
            ]),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 0, 24, 8),
            child: Column(children: [
              SizedBox(
                width: double.infinity,
                height: 52,
                child: FilledButton(onPressed: widget.done ? null : widget.primary.onPressed, child: Text(widget.done ? l10n.done : widget.primary.label)),
              ),
              if (widget.secondary != null && !widget.done) TextButton(onPressed: widget.secondary!.onPressed, child: Text(widget.secondary!.label)),
              const SizedBox(height: 12),
              StepDots(index: widget.index, total: widget.total),
            ]),
          ),
        ]),
      ),
    );
  }
}

class StepDots extends StatelessWidget {
  const StepDots({super.key, required this.index, required this.total});
  final int index;
  final int total;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Semantics(
      label: '${index + 1} / $total',
      child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
        for (var i = 0; i < total; i++)
          AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            margin: const EdgeInsets.symmetric(horizontal: 3),
            width: i == index ? 18 : 7,
            height: 7,
            decoration: BoxDecoration(color: i <= index ? scheme.primary : scheme.outlineVariant, borderRadius: BorderRadius.circular(4)),
          ),
      ]),
    );
  }
}

/// A light vector illustration (no images, no Lottie): soft rings around an icon, painted.
class StepIllustration extends StatelessWidget {
  const StepIllustration({super.key, required this.icon, this.done = false});
  final IconData icon;
  final bool done;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final colour = done ? Colors.green : scheme.primary;
    return SizedBox.square(
      dimension: 168,
      child: CustomPaint(
        painter: _Rings(colour),
        child: Center(
          child: Container(
            width: 88,
            height: 88,
            decoration: BoxDecoration(color: colour, shape: BoxShape.circle),
            child: Icon(icon, size: 44, color: Colors.white),
          ),
        ),
      ),
    );
  }
}

class _Rings extends CustomPainter {
  _Rings(this.colour);
  final Color colour;

  @override
  void paint(Canvas canvas, Size size) {
    final centre = size.center(Offset.zero);
    for (final (radius, alpha) in [(84.0, 0.08), (66.0, 0.14)]) {
      canvas.drawCircle(centre, radius, Paint()..color = colour.withValues(alpha: alpha));
    }
    final dot = Paint()..color = colour.withValues(alpha: 0.35);
    for (var i = 0; i < 5; i++) {
      final angle = i * 2 * math.pi / 5 - math.pi / 2;
      canvas.drawCircle(centre + Offset(math.cos(angle), math.sin(angle)) * 76, 4, dot);
    }
  }

  @override
  bool shouldRepaint(_Rings old) => old.colour != colour;
}
