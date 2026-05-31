// /home/ram/school_edition_lms/frontend/components/ui/LoadingSpinner.jsx

import { Loader2 } from 'lucide-react';

// Optional: If you are using shadcn/ui and have the `cn` utility from `lib/utils.js`
import { cn } from '@/lib/utils';

export const LoadingSpinner = ({ className, size = 18 }) => {
    // If you're using the `cn` utility from shadcn/ui for class merging:
    const combinedClassName = cn('animate-spin text-primary', className);

    // If you are NOT using `cn` or want a simpler version:
    // const defaultSpinnerClasses = 'animate-spin text-blue-500'; // text-primary is common with shadcn
    // const combinedClassName = `${defaultSpinnerClasses} ${className || ''}`.trim();

    return (
        <Loader2
            className={combinedClassName}
            size={size}
            aria-label="Loading" // Good for accessibility
        />
    );
};

// If you intended for it to be a default export, you would write:
// export default LoadingSpinner;
// But your original import `import { LoadingSpinner } ...` suggests a named export.