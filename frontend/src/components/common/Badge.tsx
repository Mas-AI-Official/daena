import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../utils/cn';

const badgeVariants = cva(
    "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2",
    {
        variants: {
            variant: {
                default:
                    "border-transparent bg-primary-500 text-white hover:bg-primary-600",
                secondary:
                    "border-transparent bg-dark-bg-elevated text-dark-text-primary hover:bg-dark-bg-elevated/80",
                destructive:
                    "border-transparent bg-error-500 text-white hover:bg-error-600",
                outline: "text-dark-text-primary border-dark-border",
                success: "border-transparent bg-success-500 text-white hover:bg-success-600",
                premium: "border-transparent bg-premium-500 text-white hover:bg-premium-600",
                warning: "border-transparent bg-warning-500 text-black hover:bg-warning-600",
            },
        },
        defaultVariants: {
            variant: "default",
        },
    }
);

export interface BadgeProps
    extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> { }

function Badge({ className, variant, ...props }: BadgeProps) {
    return (
        <div className={cn(badgeVariants({ variant }), className)} {...props} />
    );
}

export { Badge, badgeVariants };
