import * as React from "react";
import { Input } from "./input";
import { Label } from "./label";
import { cn } from "../../lib/utils";
import {
  parseLatitude,
  parseLongitude,
  formatDecimalCoordinate,
  getCoordinateExamples,
} from "../../utils/coordinateParser";
import { AlertCircle, HelpCircle } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./tooltip";

interface CoordinateInputProps {
  type: 'latitude' | 'longitude';
  value: number | null | undefined;
  onChange: (value: number | null) => void;
  label?: string;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  required?: boolean;
  showHelp?: boolean;
}

export const CoordinateInput = React.forwardRef<HTMLInputElement, CoordinateInputProps>(
  ({ type, value, onChange, label, placeholder, className, disabled, required, showHelp = true }, ref) => {
    const [inputValue, setInputValue] = React.useState<string>('');
    const [error, setError] = React.useState<string>('');
    const [isFocused, setIsFocused] = React.useState(false);

    // Initialize input value from prop value
    React.useEffect(() => {
      if (!isFocused) {
        setInputValue(value !== null && value !== undefined ? formatDecimalCoordinate(value) : '');
      }
    }, [value, isFocused]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = e.target.value;
      setInputValue(newValue);

      // Clear error while typing
      if (error) {
        setError('');
      }
    };

    const handleBlur = () => {
      setIsFocused(false);

      if (!inputValue.trim()) {
        setError('');
        onChange(null);
        return;
      }

      // Parse the input
      const parseResult = type === 'latitude'
        ? parseLatitude(inputValue)
        : parseLongitude(inputValue);

      if (parseResult.isValid && parseResult.value !== null) {
        setError('');
        onChange(parseResult.value);
        // Format to decimal for display
        setInputValue(formatDecimalCoordinate(parseResult.value));
      } else {
        setError(parseResult.error || 'Invalid format');
        // Keep the invalid input visible so user can fix it
      }
    };

    const handleFocus = () => {
      setIsFocused(true);
    };

    const examples = getCoordinateExamples(type);
    const defaultPlaceholder = type === 'latitude'
      ? 'e.g., 48.12345678 or N48°52.01\''
      : 'e.g., 17.65432198 or E18°0.25\'';

    return (
      <div className={cn("space-y-2", className)}>
        {label && (
          <div className="flex items-center gap-2">
            <Label>
              {label}
              {required && <span className="text-destructive ml-1">*</span>}
            </Label>
            {showHelp && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <HelpCircle className="h-4 w-4 text-muted-foreground cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-xs">
                    <div className="space-y-1">
                      <p className="font-semibold text-xs">Supported formats:</p>
                      <ul className="text-xs space-y-0.5">
                        {examples.map((example, i) => (
                          <li key={i} className="font-mono">{example}</li>
                        ))}
                      </ul>
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>
        )}
        <div className="relative">
          <Input
            ref={ref}
            type="text"
            value={inputValue}
            onChange={handleChange}
            onBlur={handleBlur}
            onFocus={handleFocus}
            placeholder={placeholder || defaultPlaceholder}
            disabled={disabled}
            className={cn(
              error && "border-destructive focus-visible:ring-destructive",
              "font-mono"
            )}
          />
          {error && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <AlertCircle className="h-4 w-4 text-destructive" />
                  </TooltipTrigger>
                  <TooltipContent side="left">
                    <p className="text-xs">{error}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          )}
        </div>
        {error && (
          <p className="text-xs text-destructive">{error}</p>
        )}
      </div>
    );
  }
);

CoordinateInput.displayName = "CoordinateInput";

// Convenience components
interface LatitudeInputProps extends Omit<CoordinateInputProps, 'type'> {}
interface LongitudeInputProps extends Omit<CoordinateInputProps, 'type'> {}

export const LatitudeInput = React.forwardRef<HTMLInputElement, LatitudeInputProps>(
  (props, ref) => {
    return <CoordinateInput ref={ref} type="latitude" {...props} />;
  }
);

LatitudeInput.displayName = "LatitudeInput";

export const LongitudeInput = React.forwardRef<HTMLInputElement, LongitudeInputProps>(
  (props, ref) => {
    return <CoordinateInput ref={ref} type="longitude" {...props} />;
  }
);

LongitudeInput.displayName = "LongitudeInput";
