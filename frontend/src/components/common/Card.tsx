import React from 'react';
import { motion } from 'framer-motion';
import type { HTMLMotionProps } from 'framer-motion';

interface CardProps extends HTMLMotionProps<"div"> {
    children: React.ReactNode;
    variant?: 'default' | 'glass' | 'elevated' | 'outline';
    noPadding?: boolean;
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(({
    children,
    variant = 'default',
    noPadding = false,
    className = '',
    ...props
}, ref) => {

    const variants = {
        default: "bg-midnight-300 border border-white/5",
        glass: "bg-midnight-300/40 backdrop-blur-lg border border-white/10 shadow-glass",
        elevated: "bg-midnight-400 border border-white/5 shadow-lg",
        outline: "bg-transparent border border-white/10"
    };

    const padding = noPadding ? "" : "p-5";

    return (
        <motion.div
            ref={ref}
            className={`rounded-lg ${variants[variant]} ${padding} ${className}`}
            {...props}
        >
            {children}
        </motion.div>
    );
});

export const CardHeader = ({ children, className = "", ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div className={`p-5 pb-2 ${className}`} {...props}>
        {children}
    </div>
);

export const CardTitle = ({ children, className = "", ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h3 className={`font-display font-medium text-lg text-white ${className}`} {...props}>
        {children}
    </h3>
);

export const CardContent = ({ children, className = "", ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div className={`p-5 pt-2 ${className}`} {...props}>
        {children}
    </div>
);

Card.displayName = 'Card';
