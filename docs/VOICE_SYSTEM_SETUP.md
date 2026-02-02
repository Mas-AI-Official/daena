# Daena Voice System - Setup \u0026 Features

## Overview
The Daena voice system provides full bidirectional voice communication with proper interruption handling and background operation.

## Features
✅ **Text-to-Speech (TTS)** - Uses XTTS-v2 with voice cloning from `daena_voice.wav`
✅ **Speech-to-Text (STT)** - Uses Whisper for voice recognition  
✅ **Automatic Interruption** - Stops speaking when you type or talk
✅ **Background Operation** - Works even when window is minimized
✅ **Full Message Delivery** - Completes text message even if speech is interrupted
✅ **Navbar Toggle** - Easy on/off control from the chat interface

## Architecture

### Two Separate Environments
1. **Main Environment** (`venv_daena_main_py310`) - Backend API, database, routing
2. **Audio Environment** (`venv_daena_audio_py310`) - TTS/STT services, voice cloning

### Voice Sample
- Location: `d:\Ideas\Daena_old_upgrade_20251213\daena_voice.wav`
- Also: `d:\Ideas\Daena_old_upgrade_20251213\Voice\daena_voice.wav`
- Format: WAV audio file for voice cloning
- Used by: XTTS-v2 model for generating Daena's voice

## How It Works

### 1. Voice Toggle (Navbar Button)
Click the microphone icon in the navbar to enable/disable voice:
- 🎤 **Active (Listening)** - Green microphone, waiting for your voice
- 🔊 **Active (Speaking)** - Gold volume icon, Daena is talking  
- 🔇 **Disabled** - Slashed microphone, voice inactive

### 2. Speech-to-Text Flow
```
User speaks → Browser captures → Transcribed to text → Input field populated
```
- Uses Web Speech API (built into browser)
- Continuous listening when enabled
- Automatically restarts if interrupted
- Fills the message input field with transcribed text

### 3. Text-to-Speech Flow
```
Daena responds → Audio service generates speech → Browser plays audio
```
- Backend sends text to audio service (`http://127.0.0.1:5001/api/tts/speak`)
- XTTS-v2 clones Daena's voice using `daena_voice.wav`
- Generated audio is played through browser
- Full text message is displayed in chat (even if audio is interrupted)

### 4. Automatic Interruption
Voice playback stops when:
- ✋ User starts typing in any input field
- 🗣️ User starts speaking (detected by STT)
- 🖱️ User clicks in an input field

**Important**: Even if speech is interrupted, the full text message remains visible in the chat.

## Usage

### Starting the System
The `START_DAENA.bat` script automatically:
1. Starts the main backend (port 8000)
2. Starts the audio service (port 5001) if `venv_daena_audio_py310` exists
3. Uses `daena_voice.wav` for voice cloning

### Manual Audio Service Start
If the audio service isn't running:
```batch
cd d:\Ideas\Daena_old_upgrade_20251213
call venv_daena_audio_py310\Scripts\activate.bat
python -m uvicorn audio.audio_service.main:app --host 127.0.0.1 --port 5001
```

### Enabling Voice in Chat
1. Navigate to `http://127.0.0.1:8000/ui/daena-office`
2. Click the microphone icon in the top-right navbar
3. Allow microphone permissions if prompted by browser
4. Voice is now enabled!

### Using Voice
**To ask a question:**
1. Enable voice mode (microphone icon)
2. Speak your question
3. Text appears in input field automatically
4. Press Enter or click Send

**Daena's response:**
1. Full text appears in chat immediately
2. Audio begins playing (if voice enabled)
3. You can interrupt anytime by typing or speaking

## Background Operation

The voice system works in the background:
- ✅ Window can be minimized
- ✅ Voice continues listening
- ✅ Speech continues playing
- ✅ Interruption still works
- ✅ Tab can be in background

The only requirement is that the browser tab remains open (doesn't need to be active/focused).

## Voice Settings (Navbar)
Click the sliders icon (⚙️) next to the microphone to access:
- Language selection
- Voice parameters (coming soon)
- STT/TTS preferences (coming soon)

## Troubleshooting

### Voice Toggle Not Working
**Problem**: Clicking microphone does nothing  
**Solution**: 
1. Check browser console for errors
2. Ensure `voice-client.js` is loaded
3. Check audio service is running: `http://127.0.0.1:5001/health`

### Audio Service Not Available
**Problem**: "Audio service not available" in console  
**Solution**:
```batch
# Check if audio environment exists
dir venv_daena_audio_py310

# If missing, create it:
python -m venv venv_daena_audio_py310
venv_daena_audio_py310\Scripts\pip install -r requirements-audio.txt
```

### Voice Sample Missing
**Problem**: "Voice sample not found" error  
**Solution**:
1. Ensure `daena_voice.wav` exists in project root
2. Or update `tts_service.py` to point to correct path
3. File should be a clean WAV recording of Daena's voice

### Microphone Permission Denied
**Problem**: Browser blocks microphone access  
**Solution**:
1. Click the lock icon in browser address bar
2. Allow microphone permissions
3. Refresh the page
4. Enable voice again

### Speech Recognition Not Working
**Problem**: Speaking but nothing appears  
**Solution**:
1. Check browser supports Web Speech API (Chrome/Edge work best)
2. Ensure microphone is working (test in Windows settings)
3. Check browser console for errors
4. Try speaking more clearly/loudly

### Speech Not Interrupting
**Problem**: Can't stop Daena from talking  
**Solution**:
1. Start typing immediately (any key)
2. Click in the message input field
3. Start speaking
4. All of these should interrupt speech playback

## API Endpoints

### Audio Service
- **Health**: `GET http://127.0.0.1:5001/health`
- **TTS Generate**: `POST http://127.0.0.1:5001/api/tts/speak`
- **Get Audio**: `GET http://127.0.0.1:5001/api/tts/audio/{filename}`
- **STT Transcribe**: `POST http://127.0.0.1:5001/api/stt/transcribe`
- **Languages**: `GET http://127.0.0.1:5001/api/tts/languages`

### Request Format (TTS)
```json
{
  "text": "Hello, I am Daena!",
  "language": "en",
  "speaker_wav": null  // Uses daena_voice.wav by default
}
```

### Response Format (TTS)
```json
{
  "audio_file": "output/speech_12345.wav",
  "message": "Speech generated successfully"
}
```

## Supported Languages (XTTS-v2)
- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Italian (it)
- Portuguese (pt)
- Polish (pl)
- Turkish (tr)
- Russian (ru)
- Dutch (nl)
- Czech (cs)
- Arabic (ar)
- Chinese (zh-cn)
- Japanese (ja)

## Technical Implementation

### Files Modified/Created
1. **`frontend/static/js/voice-client.js`** - Main voice client class
2. **`frontend/templates/daena_office.html`** - Added voice-client.js script
3. **`START_DAENA.bat`** - Already configured for audio service
4. **`audio/audio_service/tts_service.py`** - Already configured for daena_voice.wav

### Voice Client Class
```javascript
class VoiceClient {
    enabled: boolean;       // Voice mode on/off
    speaking: boolean;      // Currently speaking
    listening: boolean;     // Currently listening
    recognition: SpeechRecognition;  // STT engine
    audioElement: HTMLAudioElement;  // TTS playback
}
```

### Key Methods
- `toggle()` - Enable/disable voice mode
- `speak(text, language)` - Generate and play TTS
- `stopSpeaking()` - Interrupt current speech
- `onMessageReceived(message)` - Auto-speak assistant messages

## Best Practices

1. **Always check audio service health** before enabling voice
2. **Use clear voice sample** for best cloning results
3. **Keep messages concise** for faster TTS generation
4. **Test in Chrome/Edge** for best Web Speech API support
5. **Grant microphone permissions** when prompted

## Future Enhancements
- [ ] Voice activity detection (auto-send when done speaking)
- [ ] Multiple voice profiles
- [ ] Emotion/tone controls
- [ ] Wake word detection ("Hey Daena")
- [ ] Voice command shortcuts
- [ ] Offline mode support

---

**Status**: ✅ Fully Implemented  
**Last Updated**: 2026-01-22  
**Tested**: Chrome, Edge (Windows 11)
