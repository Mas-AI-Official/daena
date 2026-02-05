/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                // Psychology-Optimized Colors
                primary: {
                    50: '#E6F0FF',
                    100: '#CCE0FF',
                    200: '#99C2FF',
                    300: '#66A3FF',
                    400: '#3385FF',
                    500: '#0070F3',  // Main
                    600: '#005ACC',
                    700: '#0045A6',
                    800: '#002F7A',
                    900: '#001A4D',
                    DEFAULT: '#0070F3',
                },
                success: {
                    500: '#00D68F',
                    bg: 'rgba(0, 214, 143, 0.1)',
                    DEFAULT: '#00D68F',
                },
                warning: {
                    500: '#FFB020',
                    bg: 'rgba(255, 176, 32, 0.1)',
                    DEFAULT: '#FFB020',
                },
                error: {
                    500: '#FF4757',
                    bg: 'rgba(255, 71, 87, 0.1)',
                    DEFAULT: '#FF4757',
                },
                premium: {
                    500: '#8B5CF6',
                    bg: 'rgba(139, 92, 246, 0.1)',
                    DEFAULT: '#8B5CF6',
                },
                // Preserving existing midnights for background compatibility
                midnight: {
                    100: 'rgb(var(--bg-glass) / <alpha-value>)',  // 020408
                    200: 'rgb(var(--bg-primary) / <alpha-value>)', // 0B0F17
                    300: 'rgb(var(--bg-secondary) / <alpha-value>)', // 161B26
                    400: 'rgb(22 27 38 / <alpha-value>)',
                    500: 'rgb(30 41 59 / <alpha-value>)',
                    800: 'rgb(var(--border-subtle) / <alpha-value>)',
                    900: 'rgb(var(--bg-tertiary) / <alpha-value>)',
                },
                starlight: {
                    100: 'rgb(var(--text-primary) / <alpha-value>)',
                    200: 'rgb(var(--text-secondary) / <alpha-value>)',
                    300: 'rgb(var(--text-tertiary) / <alpha-value>)',
                },
                cosmos: {
                    400: '#3385FF',
                    500: '#0070F3',
                    600: '#005ACC',
                },
                status: {
                    success: '#00D68F',
                    warning: '#FFB020',
                    error: '#FF4757',
                    info: '#0070F3',
                }
            },
            spacing: {
                xs: '4px',
                sm: '8px',
                md: '16px',
                lg: '24px',
                xl: '32px',
                '2xl': '48px',
                '3xl': '64px',
            },
            borderRadius: {
                sm: '4px',    // Pills, tags
                md: '8px',    // Buttons, inputs
                lg: '12px',   // Cards
                xl: '16px',   // Modals
                full: '9999px', // Avatars
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', 'sans-serif'],
                display: ['Outfit', 'Inter', 'sans-serif'],
                mono: ['JetBrains Mono', 'monospace'],
            },
            fontSize: {
                xs: '12px',
                sm: '14px',
                base: '16px',
                lg: '18px',
                xl: '24px',
                '2xl': '36px',
                '3xl': '48px',
            },
            animation: {
                fast: '150ms cubic-bezier(0.4, 0, 0.2, 1)',
                normal: '200ms cubic-bezier(0.4, 0, 0.2, 1)',
                slow: '300ms cubic-bezier(0.4, 0, 0.2, 1)',
                bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
            },
            boxShadow: {
                sm: '0 1px 2px rgba(0, 0, 0, 0.05)',
                md: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
                'glow-primary': '0 0 20px rgba(0, 112, 243, 0.3)',
                'glow-success': '0 0 20px rgba(0, 214, 143, 0.3)',
                'glow-error': '0 0 20px rgba(255, 71, 87, 0.3)',
                'glow-sm': '0 0 10px rgba(0, 112, 243, 0.2)', // Adjusted to match primary
                'glass': '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
            },
            backgroundImage: {
                'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
                'glass-gradient': 'linear-gradient(145deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.01) 100%)',
            }
        },
    },
    plugins: [],
}
