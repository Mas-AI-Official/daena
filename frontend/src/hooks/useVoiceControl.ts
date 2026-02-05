import { useState, useCallback, useRef, useEffect } from 'react';

interface VoiceControlOptions {
    onCommand?: (command: string) => void;
    commands?: Record<string, () => void>;
    language?: string;
}

export function useVoiceControl({ onCommand, commands, language = 'en-US' }: VoiceControlOptions = {}) {
    const [isListening, setIsListening] = useState(false);
    const [transcript, setTranscript] = useState('');
    const recognitionRef = useRef<any>(null);

    useEffect(() => {
        const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
        if (SpeechRecognition) {
            const recognition = new SpeechRecognition();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = language;

            recognition.onresult = (event: any) => {
                const current = event.resultIndex;
                const result = event.results[current];
                const text = result[0].transcript.toLowerCase().trim();

                if (result.isFinal) {
                    setTranscript(text);
                    onCommand?.(text);

                    // Match commands
                    if (commands) {
                        Object.keys(commands).forEach(cmd => {
                            if (text.includes(cmd.toLowerCase())) {
                                commands[cmd]();
                            }
                        });
                    }
                }
            };

            recognition.onerror = (event: any) => {
                console.error('Speech recognition error:', event.error);
                setIsListening(false);
            };

            recognition.onend = () => {
                if (isListening) {
                    recognition.start(); // Auto-restart if we're supposed to be listening
                }
            };

            recognitionRef.current = recognition;
        }
    }, [commands, language, onCommand, isListening]);

    const startListening = useCallback(() => {
        if (recognitionRef.current) {
            recognitionRef.current.start();
            setIsListening(true);
        }
    }, []);

    const stopListening = useCallback(() => {
        if (recognitionRef.current) {
            recognitionRef.current.stop();
            setIsListening(false);
        }
    }, []);

    const toggleListening = useCallback(() => {
        if (isListening) {
            stopListening();
        } else {
            startListening();
        }
    }, [isListening, startListening, stopListening]);

    return {
        isListening,
        transcript,
        startListening,
        stopListening,
        toggleListening,
        hasSupport: !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition)
    };
}
