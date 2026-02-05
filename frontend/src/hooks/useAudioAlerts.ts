import { useCallback, useRef } from 'react';
import { Howl } from 'howler';

// Sounds can be added to /public/sounds/
const SOUND_MAP: Record<string, string> = {
    success: '/sounds/success.mp3',
    error: '/sounds/error.mp3',
    notification: '/sounds/notification.mp3',
    approval: '/sounds/approval-request.mp3',
    startup: '/sounds/startup.mp3'
};

export function useAudioAlerts() {
    const soundsRef = useRef<Record<string, Howl>>({});

    const play = useCallback((soundName: keyof typeof SOUND_MAP) => {
        if (!soundsRef.current[soundName]) {
            soundsRef.current[soundName] = new Howl({
                src: [SOUND_MAP[soundName]],
                volume: 0.5
            });
        }
        soundsRef.current[soundName].play();
    }, []);

    const speak = useCallback((text: string) => {
        if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 1.0;
            utterance.pitch = 1.0;
            utterance.volume = 0.8;
            // Use a specific voice if available
            const voices = window.speechSynthesis.getVoices();
            const preferredVoice = voices.find(v => v.name.includes('Google') || v.name.includes('Neural'));
            if (preferredVoice) utterance.voice = preferredVoice;

            window.speechSynthesis.speak(utterance);
        }
    }, []);

    return { play, speak };
}
