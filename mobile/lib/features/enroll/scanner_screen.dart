import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../core/enroll/enroll_uri.dart';
import '../../l10n/app_localizations.dart';
import '../../providers.dart';

/// The QR scanner: QR codes only, no duplicate detections, a scan window with an animated frame, torch, pinch to
/// zoom, a haptic tick and the camera stopped on the first valid code. A code that is not an enrollment code for an
/// allowed server shows a friendly message and scanning resumes after 2 s. "Scan from photo" reads a QR the holder
/// received as an image (often a WhatsApp photo on the same phone). Pops with the raw value; the enroll screen still
/// applies the allow-list and the monitoring notice.
class ScannerScreen extends ConsumerStatefulWidget {
  const ScannerScreen({super.key});
  @override
  ConsumerState<ScannerScreen> createState() => _ScannerScreenState();
}

class _ScannerScreenState extends ConsumerState<ScannerScreen> with WidgetsBindingObserver, SingleTickerProviderStateMixin {
  final _controller = MobileScannerController(formats: const [BarcodeFormat.qrCode], detectionSpeed: DetectionSpeed.noDuplicates, autoStart: false);
  late final _frame = AnimationController(vsync: this, duration: const Duration(milliseconds: 1600))..repeat(reverse: true);
  bool _cameraAllowed = false;
  bool _askedOnce = false;
  bool _done = false;
  String? _message;
  Timer? _resume;
  double _zoom = 0;
  double _zoomAtStart = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _checkCamera();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _resume?.cancel();
    _frame.dispose();
    _controller.dispose();
    super.dispose();
  }

  /// The camera follows the app's lifecycle: stopped in the background, started again on return.
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (!_cameraAllowed || _done) {
      if (state == AppLifecycleState.resumed) _checkCamera(request: false);
      return;
    }
    if (state == AppLifecycleState.resumed) {
      unawaited(_controller.start());
    } else if (state == AppLifecycleState.paused || state == AppLifecycleState.inactive) {
      unawaited(_controller.stop());
    }
  }

  Future<void> _checkCamera({bool request = true}) async {
    final host = ref.read(servicesProvider).host;
    var granted = (await host.permissions()).where((p) => p.name == 'CAMERA').firstOrNull?.granted ?? false;
    if (!granted && request && !_askedOnce) {
      _askedOnce = true;
      granted = (await host.requestPermissions(['CAMERA'])).where((p) => p.name == 'CAMERA').firstOrNull?.granted ?? false;
    }
    if (!mounted) return;
    setState(() => _cameraAllowed = granted);
    if (granted) unawaited(_controller.start());
  }

  void _handle(String? raw) {
    if (raw == null || _done) return;
    final hosts = ref.read(servicesProvider).config.allowedServerHosts;
    try {
      parseEnrollTarget(raw, allowedHosts: hosts);
    } on EnrollUriException catch (error) {
      final l10n = AppLocalizations.of(context);
      setState(() => _message = error.code == 'invalid' ? l10n.notAnEnrollCode : l10n.untrustedServer);
      _resume?.cancel();
      // Never stuck on a bad code: clear the message and keep scanning.
      _resume = Timer(const Duration(seconds: 2), () {
        if (mounted) setState(() => _message = null);
      });
      return;
    }
    _done = true;
    HapticFeedback.mediumImpact();
    unawaited(_controller.stop());
    context.pop(raw);
  }

  Future<void> _fromPhoto() async {
    final path = await ref.read(servicesProvider).host.pickImage();
    if (path == null || !mounted) return;
    final capture = await _controller.analyzeImage(path, formats: const [BarcodeFormat.qrCode]);
    if (!mounted) return;
    final raw = capture?.barcodes.firstOrNull?.rawValue;
    if (raw == null) {
      setState(() => _message = AppLocalizations.of(context).noQrInPhoto);
      _resume?.cancel();
      _resume = Timer(const Duration(seconds: 2), () {
        if (mounted) setState(() => _message = null);
      });
      return;
    }
    _handle(raw);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final size = MediaQuery.sizeOf(context);
    final side = (size.shortestSide * 0.7).clamp(200.0, 320.0);
    final window = Rect.fromCenter(center: Offset(size.width / 2, size.height * 0.42), width: side, height: side);
    return Scaffold(
      backgroundColor: Colors.black,
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        foregroundColor: Colors.white,
        title: Text(l10n.scanQr),
        actions: [
          if (_cameraAllowed)
            ValueListenableBuilder(
              valueListenable: _controller,
              builder: (context, state, _) => IconButton(
                tooltip: l10n.torch,
                icon: Icon(state.torchState == TorchState.on ? Icons.flash_on : Icons.flash_off),
                onPressed: () => _controller.toggleTorch(),
              ),
            ),
        ],
      ),
      body: !_cameraAllowed
          ? _CameraRationale(onAllow: () => _askedOnce ? ref.read(servicesProvider).host.openAppSettings() : _checkCamera(), denied: _askedOnce, onPhoto: _fromPhoto)
          : GestureDetector(
              onScaleStart: (_) => _zoomAtStart = _zoom,
              onScaleUpdate: (details) {
                _zoom = (_zoomAtStart + (details.scale - 1) * 0.5).clamp(0.0, 1.0);
                _controller.setZoomScale(_zoom);
              },
              child: Stack(children: [
                MobileScanner(
                  controller: _controller,
                  scanWindow: window,
                  onDetect: (capture) => _handle(capture.barcodes.firstOrNull?.rawValue),
                  errorBuilder: (context, error) => _CameraRationale(
                    denied: error.errorCode == MobileScannerErrorCode.permissionDenied, onPhoto: _fromPhoto,
                    onAllow: () => ref.read(servicesProvider).host.openAppSettings(),
                  ),
                ),
                AnimatedBuilder(animation: _frame, builder: (context, _) => CustomPaint(size: Size.infinite, painter: _WindowPainter(window, _frame.value))),
                Positioned(
                  left: 24, right: 24, top: window.bottom + 24,
                  child: Column(children: [
                    AnimatedSwitcher(
                      duration: const Duration(milliseconds: 200),
                      child: Text(_message ?? l10n.pointAtQr, key: ValueKey(_message), textAlign: TextAlign.center,
                          style: TextStyle(color: _message == null ? Colors.white : Colors.amberAccent, fontSize: 16)),
                    ),
                    const SizedBox(height: 24),
                    OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(foregroundColor: Colors.white, side: const BorderSide(color: Colors.white54)),
                      onPressed: _fromPhoto, icon: const Icon(Icons.photo_library_outlined), label: Text(l10n.scanFromPhoto),
                    ),
                  ]),
                ),
              ]),
            ),
    );
  }
}

class _CameraRationale extends StatelessWidget {
  const _CameraRationale({required this.onAllow, required this.denied, required this.onPhoto});
  final VoidCallback onAllow;
  final bool denied;
  final VoidCallback onPhoto;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.photo_camera_outlined, size: 56, color: Colors.white),
          const SizedBox(height: 16),
          Text(l10n.cameraRationale, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontSize: 16)),
          const SizedBox(height: 24),
          FilledButton(onPressed: onAllow, child: Text(denied ? l10n.openSettings : l10n.allow)),
          TextButton(onPressed: onPhoto, child: Text(l10n.scanFromPhoto, style: const TextStyle(color: Colors.white))),
        ]),
      ),
    );
  }
}

/// Dims everything but the scan window and draws its corners, gently pulsing.
class _WindowPainter extends CustomPainter {
  _WindowPainter(this.window, this.t);
  final Rect window;
  final double t;

  @override
  void paint(Canvas canvas, Size size) {
    final hole = RRect.fromRectAndRadius(window, const Radius.circular(20));
    canvas.drawPath(Path.combine(PathOperation.difference, Path()..addRect(Offset.zero & size), Path()..addRRect(hole)), Paint()..color = Colors.black54);
    final inset = 4 * t;
    final r = window.deflate(inset);
    final paint = Paint()
      ..color = Colors.white
      ..strokeWidth = 4
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    const arm = 28.0;
    for (final (corner, dx, dy) in [(r.topLeft, 1.0, 1.0), (r.topRight, -1.0, 1.0), (r.bottomLeft, 1.0, -1.0), (r.bottomRight, -1.0, -1.0)]) {
      canvas.drawPath(Path()..moveTo(corner.dx, corner.dy + dy * arm)..lineTo(corner.dx, corner.dy)..lineTo(corner.dx + dx * arm, corner.dy), paint);
    }
  }

  @override
  bool shouldRepaint(_WindowPainter old) => old.t != t || old.window != window;
}
