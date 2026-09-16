# Flutter Developer Guide: Video & Background Music Dual-Playback (Option A)

This guide provides the exact architecture and implementation code for playing vehicle reels with background music in the Flutter app (TikTok & Instagram Reels style).

---

## 1. How It Works (Option A Architecture)

Each reel in the newsfeed (`GET /api/vehicles/newsfeed/`) delivers two stream URLs:
1. `video_file`: The direct `.mp4` video (retains original car engine/exhaust/microphone sound).
2. `background_music`: An object containing the selected background audio track (`.mp3`), or `null` if the dealer chose not to add music.

```json
{
  "id": 4,
  "video_file": "https://api.yourdomain.com/media/reels/bmw_m3.mp4",
  "background_music": {
    "id": 1,
    "title": "Carnaval Drive",
    "file": "https://api.yourdomain.com/media/music/alec_koff-carnaval-484622.mp3"
  },
  "vehicle_details": {
    "name": "BMW M3",
    "year": 2023,
    "asking_price": "82000.00"
  }
}
```

---

## 2. All 4 Audio Scenarios Handled Automatically

| Scenario | `video_file` Audio | `background_music` | App Playback Behavior |
| :--- | :---: | :---: | :--- |
| **Engine Sound Only** | Genuine sound (engine/voice) | `null` | Plays `video_file` audio at **100% volume**. |
| **Engine Sound + Music** | Genuine sound | Present | **Mixes both!** Original sound ducks to 30%, music plays at 100%. |
| **Silent Video + Music** *(e.g. AI Video)* | Silent | Present | Plays music track in sync with the looping video. |
| **Silent Video** | Silent | `null` | Plays quietly as a normal silent video. |

---

## 3. Dart Models

```dart
class BackgroundMusicModel {
  final int id;
  final String title;
  final String file;

  BackgroundMusicModel({
    required this.id,
    required this.title,
    required this.file,
  });

  factory BackgroundMusicModel.fromJson(Map<String, dynamic> json) {
    return BackgroundMusicModel(
      id: json['id'] as int,
      title: json['title'] as String,
      file: json['file'] as String,
    );
  }
}

class ReelModel {
  final int id;
  final String videoFile;
  final BackgroundMusicModel? backgroundMusic;
  final int dealerId;
  final String dealerName;
  final bool isLiked;
  final bool isSaved;
  final int likesCount;

  ReelModel({
    required this.id,
    required this.videoFile,
    this.backgroundMusic,
    required this.dealerId,
    required this.dealerName,
    required this.isLiked,
    required this.isSaved,
    required this.likesCount,
  });

  factory ReelModel.fromJson(Map<String, dynamic> json) {
    return ReelModel(
      id: json['id'] as int,
      videoFile: json['video_file'] as String,
      backgroundMusic: json['background_music'] != null
          ? BackgroundMusicModel.fromJson(json['background_music'] as Map<String, dynamic>)
          : null,
      dealerId: json['dealer_id'] as int,
      dealerName: json['dealer_name'] as String? ?? '',
      isLiked: json['is_liked'] as bool? ?? false,
      isSaved: json['is_saved'] as bool? ?? false,
      likesCount: json['likes_count'] as int? ?? 0,
    );
  }
}
```

---

## 4. Flutter Reel Player Widget (`ReelVideoPlayerWidget`)

Using `video_player` for the video feed and `just_audio` for the background track:

### Dependencies (`pubspec.yaml`):
```yaml
dependencies:
  video_player: ^2.9.2
  just_audio: ^0.9.40
```

### Complete Widget Implementation:

```dart
import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import 'package:just_audio/just_audio.dart';

class ReelVideoPlayerWidget extends StatefulWidget {
  final ReelModel reel;
  final bool isCurrentPage; // Pass true when this reel is active on screen

  const ReelVideoPlayerWidget({
    Key? key,
    required this.reel,
    required this.isCurrentPage,
  }) : super(key: key);

  @override
  State<ReelVideoPlayerWidget> createState() => _ReelVideoPlayerWidgetState();
}

class _ReelVideoPlayerWidgetState extends State<ReelVideoPlayerWidget> {
  late VideoPlayerController _videoController;
  AudioPlayer? _audioPlayer;
  bool _isInitialized = false;
  bool _isMuted = false;

  @override
  void initState() {
    super.initState();
    _initializePlayers();
  }

  Future<void> _initializePlayers() async {
    // 1. Initialize Video Controller
    _videoController = VideoPlayerController.networkUrl(
      Uri.parse(widget.reel.videoFile),
    );

    await _videoController.initialize();
    _videoController.setLooping(true);

    // 2. Initialize Background Music Player (if music track exists)
    if (widget.reel.backgroundMusic != null) {
      _audioPlayer = AudioPlayer();
      try {
        await _audioPlayer!.setUrl(widget.reel.backgroundMusic!.file);
        await _audioPlayer!.setLoopMode(LoopMode.one);

        // Mix: Duck original video audio to 30%, play music at 100%
        await _videoController.setVolume(0.3);
        await _audioPlayer!.setVolume(1.0);
      } catch (e) {
        debugPrint('Error loading background music: $e');
      }
    } else {
      // No background music: play video original audio at 100%
      await _videoController.setVolume(1.0);
    }

    if (mounted) {
      setState(() {
        _isInitialized = true;
      });

      if (widget.isCurrentPage) {
        _play();
      }
    }
  }

  @override
  void didUpdateWidget(covariant ReelVideoPlayerWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isCurrentPage != oldWidget.isCurrentPage) {
      if (widget.isCurrentPage) {
        _play();
      } else {
        _pause();
      }
    }
  }

  void _play() {
    if (!_isInitialized) return;
    _videoController.play();
    _audioPlayer?.play();
  }

  void _pause() {
    if (!_isInitialized) return;
    _videoController.pause();
    _audioPlayer?.pause();
  }

  void _togglePlayPause() {
    if (_videoController.value.isPlaying) {
      _pause();
    } else {
      _play();
    }
    setState(() {});
  }

  void _toggleMute() {
    setState(() {
      _isMuted = !_isMuted;
      if (_isMuted) {
        _videoController.setVolume(0.0);
        _audioPlayer?.setVolume(0.0);
      } else {
        if (widget.reel.backgroundMusic != null) {
          _videoController.setVolume(0.3);
          _audioPlayer?.setVolume(1.0);
        } else {
          _videoController.setVolume(1.0);
        }
      }
    });
  }

  @override
  void dispose() {
    _videoController.dispose();
    _audioPlayer?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_isInitialized) {
      return const Center(
        child: CircularProgressIndicator(color: Colors.white),
      );
    }

    return GestureDetector(
      onTap: _togglePlayPause,
      onDoubleTap: _toggleMute,
      child: Stack(
        fit: StackFit.expand,
        children: [
          // Video Player
          FittedBox(
            fit: BoxFit.contain,
            child: SizedBox(
              width: _videoController.value.size.width,
              height: _videoController.value.size.height,
              child: VideoPlayer(_videoController),
            ),
          ),

          // Music Track Pill (TikTok-style bottom badge)
          if (widget.reel.backgroundMusic != null)
            Positioned(
              bottom: 80,
              left: 16,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.black.withOpacity(0.5),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.music_note, color: Colors.white, size: 14),
                    const SizedBox(width: 4),
                    Text(
                      widget.reel.backgroundMusic!.title,
                      style: const TextStyle(color: Colors.white, fontSize: 12),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}
```

---

## 5. Endpoints Reference for Audio/Video

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `GET /api/vehicles/music/` | `GET` | Fetch list of available audio tracks for dealer to select |
| `POST /api/vehicles/create/` | `POST` | Post vehicle with optional `background_music: <id>` or omit if none |
| `GET /api/vehicles/newsfeed/` | `GET` | Public feed returning `video_file` + `background_music` |
| `GET /api/vehicles/inventory/` | `GET` | Dealer's inventory returning `video_file` + `background_music` |
