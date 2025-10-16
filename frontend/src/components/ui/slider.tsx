import * as React from "react"
import { cn } from "../../lib/utils"

export interface SliderProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  value?: number
  onValueChange?: (value: number) => void
}

const Slider = React.forwardRef<HTMLInputElement, SliderProps>(
  ({ className, value, onValueChange, onChange, ...props }, ref) => {
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = Number(e.target.value)
      onValueChange?.(newValue)
      onChange?.(e)
    }

    return (
      <input
        type="range"
        ref={ref}
        value={value}
        onChange={handleChange}
        className={cn(
          "w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer slider",
          "slider::-webkit-slider-thumb:appearance-none slider::-webkit-slider-thumb:h-4 slider::-webkit-slider-thumb:w-4",
          "slider::-webkit-slider-thumb:rounded-full slider::-webkit-slider-thumb:bg-primary slider::-webkit-slider-thumb:cursor-pointer",
          "slider::-moz-range-thumb:h-4 slider::-moz-range-thumb:w-4 slider::-moz-range-thumb:rounded-full",
          "slider::-moz-range-thumb:bg-primary slider::-moz-range-thumb:cursor-pointer slider::-moz-range-thumb:border-none",
          className
        )}
        {...props}
      />
    )
  }
)
Slider.displayName = "Slider"

export { Slider }