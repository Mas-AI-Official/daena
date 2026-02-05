import { useNavigate } from 'react-router-dom';
import { useVoiceControl } from '../../hooks/useVoiceControl';
import { useUIStore } from '../../store/uiStore';
import { useAudioAlerts } from '../../hooks/useAudioAlerts';
import { useEffect } from 'react';

export function VoiceNavigator() {
    const navigate = useNavigate();
    const { addNotification } = useUIStore();
    const { speak } = useAudioAlerts();

    const commands = {
        'dashboard': () => {
            navigate('/');
            speak('Navigating to dashboard');
        },
        'control room': () => {
            navigate('/');
            speak('Entering control room');
        },
        'chat': () => {
            navigate('/chat');
            speak('Opening executive communication link');
        },
        'daena': () => {
            navigate('/chat');
            speak('Daena is online');
        },
        'departments': () => {
            navigate('/departments');
            speak('Viewing sector topology');
        },
        'skills': () => {
            navigate('/skills');
            speak('Opening skill registry');
        },
        'governance': () => {
            navigate('/governance');
            speak('Opening governance console');
        },
        'brain': () => {
            navigate('/brain');
            speak('Accessing neural infrastructure');
        },
        'vault': () => {
            navigate('/vault');
            speak('Entering secure vault. Authorization confirmed.');
        },
        'logout': () => {
            addNotification({
                title: 'Voice Command',
                message: 'Logout requested via voice.',
                type: 'warning'
            });
            speak('Session termination requested');
        }
    };

    const { isListening, toggleListening } = useVoiceControl({
        commands,
        onCommand: (text) => {
            console.log('[Voice Navigator] Command detected:', text);
        }
    });

    // We keep it invisible as it's a global listener if started, 
    // but maybe we add a keyboard shortcut to toggle global listening
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'v' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                toggleListening();
                if (!isListening) {
                    addNotification({
                        title: 'Voice Control',
                        message: 'Global voice navigation active.',
                        type: 'info'
                    });
                }
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [toggleListening, isListening, addNotification]);

    return null;
}
