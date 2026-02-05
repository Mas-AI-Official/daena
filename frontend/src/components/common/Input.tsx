import React from 'react';
import { clsx } from 'clsx';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    label?: string;
    error?: string;
    leftIcon?: React.ReactNode;
    rightIcon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(({
    label,
    error,
    leftIcon,
    rightIcon,
    className,
    ...props
}, ref) => {
    return (
        <div className="w-full">
            {label && (
                <label className="block text-xs font-medium text-starlight-300 mb-1.5 ml-0.5">
                    {label}
                </label>
            )}
            <div className="relative">
                {leftIcon && (
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-starlight-400">
                        {leftIcon}
                    </div>
                )}
                <input
                    ref={ref}
                    className={clsx(
                        "w-full bg-midnight-900/50 border border-white/10 rounded-md py-2.5 text-sm text-starlight-100 placeholder-starlight-400 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50 transition-all",
                        leftIcon && "pl-10",
                        rightIcon && "pr-10",
                        error && "border-error-500 focus:ring-error-500/50 focus:border-error-500",
                        className
                    )}
                    {...props}
                />
                {rightIcon && (
                    <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-starlight-400">
                        {rightIcon}
                    </div>
                )}
            </div>
            {error && (
                <p className="mt-1 text-xs text-error-500 ml-0.5">{error}</p>
            )}
        </div>
    );
});

Input.displayName = 'Input';
