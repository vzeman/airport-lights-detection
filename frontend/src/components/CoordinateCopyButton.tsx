import React, { useState } from 'react';
import { Button } from './ui/button';
import { Copy, Check } from 'lucide-react';

interface CoordinateCopyButtonProps {
  value: string;
  label?: string;
  variant?: 'default' | 'outline' | 'secondary' | 'ghost';
}

const CoordinateCopyButton: React.FC<CoordinateCopyButtonProps> = ({
  value,
  label = 'Copy',
  variant = 'outline'
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <Button
      type="button"
      size="sm"
      variant={variant}
      onClick={handleCopy}
      className="shrink-0"
    >
      {copied ? (
        <>
          <Check className="w-3 h-3 mr-1" />
          Copied
        </>
      ) : (
        <>
          <Copy className="w-3 h-3 mr-1" />
          {label}
        </>
      )}
    </Button>
  );
};

export default CoordinateCopyButton;
